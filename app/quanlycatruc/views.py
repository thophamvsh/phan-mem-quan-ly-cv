from io import BytesIO
from pathlib import Path
from datetime import date, datetime, time, timedelta
import uuid

import xlsxwriter
from django_filters.rest_framework import DjangoFilterBackend
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from core.models import User
from tochuc.models import BoPhan, DonViToChuc, NhanSu
from .models import ChiTietPhuongAnPhanCongCa, DieuChinhNhanSuCaTruc, KipTruc, LichTrucCa, MauChuKyCaTruc, NgayTrucCa, NhomLichTruc, PhamViNhanSuCaTruc, PhuongAnPhanCongCa, ThanhVienKipTruc
from .permissions import LegacyStaffPermission, RosterPermission, ShiftAdjustmentPermission, ShiftSchedulePermission, can_access_plant, has_profile_permission
from .serializers import BoPhanSerializer, ChiTietPhuongAnPhanCongCaSerializer, DieuChinhNhanSuCaTrucSerializer, DonViToChucSerializer, KipTrucSerializer, LichTrucCaSerializer, MauChuKyCaTrucSerializer, NgayTrucCaSerializer, NhanSuSerializer, NhomLichTrucSerializer, PhamViNhanSuCaTrucSerializer, PhuongAnPhanCongCaSerializer, ThanhVienKipTrucSerializer, TransitionSerializer
from .services import _snapshot_staff, actual_shift_staff, custom_schedule_staff_labels, generate_monthly_schedule, transition_schedule, validate_operation_staffing, validate_replacement_availability


def _scope(queryset, user, field="nha_may_id"):
    if user.is_superuser or getattr(getattr(user, "profile", None), "is_all_factories", False):
        return queryset
    plant_id = getattr(getattr(user, "profile", None), "nha_may_id", None)
    return queryset.filter(**{field: plant_id}) if plant_id else queryset.none()


def _translate_validation(error):
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(error.messages)


def _custom_staff_value(day, period, labels):
    values = [labels[day.id][period]]
    if period == "ca_ngay" and day.la_ngay_chuyen_kip:
        values.insert(0, labels[day.id]["ca_dem"])
    names = list(dict.fromkeys(name for value in values for name in value.splitlines() if name))
    return "\n".join(names) or "Chưa phân công"


def _shift_time_labels(schedule):
    plant_code = (schedule.nha_may.ma_nha_may or "").strip().upper()
    plant_name = (schedule.nha_may.ten_nha_may or "").strip().lower()
    if plant_code == "VS" or "vĩnh sơn" in plant_name:
        return "07:00-19:00", "19:00-07:00"
    return "08:00-20:00", "20:00-08:00"


def _export_roster(schedule):
    teams = KipTruc.objects.filter(
        nha_may=schedule.nha_may,
        dang_hoat_dong=True,
    )
    if schedule.nhom_lich_id:
        teams = teams.filter(nhom_lich=schedule.nhom_lich)
    teams = list(teams.order_by("loai_kip", "thu_tu", "ma_kip"))
    snapshot = schedule.snapshot_nhan_su or _snapshot_staff(schedule)
    core_roles = [
        ("truong_ca", "Trưởng ca"),
        ("truc_chinh", "Trực chính"),
        ("truc_phu", "Trực phụ"),
    ]
    optional_roles = [
        ("ky_thuat_vien", "Kỹ thuật viên"),
        ("nhan_vien", "Nhân viên"),
    ]
    active_roles = {
        member.get("vai_tro") or "nhan_vien"
        for members in snapshot.values()
        for member in members
    }
    roles = core_roles + [item for item in optional_roles if item[0] in active_roles]
    return teams, snapshot, roles


def _export_team_label(team):
    if team.ma_kip in {"HC1", "1"}:
        return "Ca KT-HC1"
    if team.ma_kip in {"HC2", "2"}:
        return "Ca KT-HC2"
    if team.loai_kip == KipTruc.LoaiKip.HANH_CHINH:
        return f"Ca KT-HC ({team.ma_kip})"
    return f"Ca {team.ma_kip}"


class KipTrucViewSet(viewsets.ModelViewSet):
    serializer_class = KipTrucSerializer
    permission_classes = [RosterPermission]
    pagination_class = None
    filterset_fields = ["nha_may", "nhom_lich", "loai_kip", "dang_hoat_dong"]
    ordering = ["loai_kip", "thu_tu"]

    def get_queryset(self):
        return _scope(KipTruc.objects.select_related("nha_may").prefetch_related("thanh_vien__nhan_su", "thanh_vien__user", "thanh_vien__user__profile"), self.request.user)

    def perform_create(self, serializer):
        plant = serializer.validated_data["nha_may"]
        if not can_access_plant(self.request.user, plant.id):
            raise PermissionDenied("Bạn không có quyền quản lý nhà máy này.")
        serializer.save()

    def perform_update(self, serializer):
        plant = serializer.validated_data.get("nha_may", serializer.instance.nha_may)
        if not plant or not can_access_plant(self.request.user, plant.id):
            raise PermissionDenied("Bạn không có quyền chuyển kíp sang nhà máy này.")
        serializer.save()

    @action(detail=False, methods=["get"], url_path="nhan-su-options")
    def nhan_su_options(self, request):
        if not has_profile_permission(request.user, "can_manage_shift_roster"):
            raise PermissionDenied("Bạn không có quyền quản lý thành viên kíp.")
        requested_plant = request.query_params.get("nha_may")
        profile = getattr(request.user, "profile", None)
        plant_id = requested_plant if (request.user.is_superuser or getattr(profile, "is_all_factories", False)) else getattr(profile, "nha_may_id", None)
        if not plant_id or (requested_plant and not can_access_plant(request.user, requested_plant)):
            raise PermissionDenied("Bạn không có quyền xem nhân sự của nhà máy này.")
        queryset = NhanSu.objects.filter(don_vi__nha_may_id=plant_id, dang_lam_viec=True).select_related("don_vi", "bo_phan", "user")
        group_id = request.query_params.get("nhom_lich")
        if group_id:
            queryset = queryset.filter(pham_vi_ca_truc__nhom_lich_id=group_id, pham_vi_ca_truc__dang_hoat_dong=True).distinct()
        return Response(NhanSuSerializer(queryset, many=True).data)


class NhomLichTrucViewSet(viewsets.ModelViewSet):
    serializer_class = NhomLichTrucSerializer
    permission_classes = [RosterPermission]
    pagination_class = None
    filterset_fields = ["nha_may", "don_vi", "bo_phan", "dang_hoat_dong"]

    def get_queryset(self):
        return _scope(NhomLichTruc.objects.select_related("nha_may", "don_vi", "bo_phan"), self.request.user)

    def perform_create(self, serializer):
        plant = serializer.validated_data["nha_may"]
        if not can_access_plant(self.request.user, plant.id):
            raise PermissionDenied("Bạn không có quyền tạo nhóm lịch cho nhà máy này.")
        serializer.save()

    def perform_update(self, serializer):
        plant = serializer.validated_data.get("nha_may", serializer.instance.nha_may)
        if not can_access_plant(self.request.user, plant.id):
            raise PermissionDenied("Bạn không có quyền sửa nhóm lịch của nhà máy này.")
        serializer.save()

    def perform_destroy(self, instance):
        dependencies = []
        if instance.pham_vi_nhan_su.exists():
            dependencies.append("nhân sự nhóm")
        if instance.kip_truc.exists():
            dependencies.append("kíp trực")
        if instance.phuong_an_phan_cong.exists():
            dependencies.append("phương án phân công")
        if instance.mau_chu_ky.exists():
            dependencies.append("mẫu chu kỳ")
        if instance.lich_truc.exists():
            dependencies.append("lịch trực")
        if dependencies:
            raise ValidationError({
                "detail": "Không thể xóa nhóm lịch đang có " + ", ".join(dependencies) + ". Hãy xóa hoặc chuyển các dữ liệu liên quan trước."
            })
        instance.delete()


class PhamViNhanSuCaTrucViewSet(viewsets.ModelViewSet):
    serializer_class = PhamViNhanSuCaTrucSerializer
    permission_classes = [RosterPermission]
    pagination_class = None
    filterset_fields = ["nhom_lich", "nhan_su", "dang_hoat_dong"]

    def get_queryset(self):
        return _scope(PhamViNhanSuCaTruc.objects.select_related("nhom_lich", "nhan_su", "nhan_su__bo_phan"), self.request.user, "nhom_lich__nha_may_id")

    def perform_create(self, serializer):
        group = serializer.validated_data["nhom_lich"]
        if not can_access_plant(self.request.user, group.nha_may_id):
            raise PermissionDenied("Bạn không có quyền thêm nhân sự vào nhóm lịch này.")
        personnel = serializer.validated_data["nhan_su"]
        existing = PhamViNhanSuCaTruc.objects.filter(
            nhom_lich=group,
            nhan_su=personnel,
        ).first()
        if existing:
            for field in ("tu_ngay", "den_ngay", "dang_hoat_dong"):
                if field in serializer.validated_data:
                    setattr(existing, field, serializer.validated_data[field])
            existing.dang_hoat_dong = True
            existing.save()
            serializer.instance = existing
            return
        serializer.save()


class DonViToChucViewSet(viewsets.ModelViewSet):
    serializer_class = DonViToChucSerializer
    permission_classes = [RosterPermission]
    pagination_class = None
    filterset_fields = ["nha_may", "don_vi_cha", "loai_don_vi", "dang_hoat_dong"]

    def get_queryset(self):
        return _scope(DonViToChuc.objects.select_related("nha_may", "don_vi_cha"), self.request.user)

    def perform_create(self, serializer):
        plant = serializer.validated_data.get("nha_may")
        parent = serializer.validated_data.get("don_vi_cha")
        plant_id = plant.id if plant else (parent.nha_may_pham_vi_id if parent else None)
        if not plant_id and not self.request.user.is_superuser:
            raise PermissionDenied("Chỉ quản trị viên hệ thống được tạo đơn vị cấp công ty.")
        if plant_id and not can_access_plant(self.request.user, plant_id):
            raise PermissionDenied("Bạn không có quyền tạo đơn vị trong phạm vi này.")
        serializer.save()

    def perform_update(self, serializer):
        plant = serializer.validated_data.get("nha_may", serializer.instance.nha_may)
        if not plant and not self.request.user.is_superuser:
            raise PermissionDenied("Chỉ quản trị viên hệ thống được quản lý đơn vị cấp công ty.")
        if plant and not can_access_plant(self.request.user, plant.id):
            raise PermissionDenied("Bạn không có quyền chuyển đơn vị sang nhà máy này.")
        serializer.save()


class BoPhanViewSet(viewsets.ModelViewSet):
    serializer_class = BoPhanSerializer
    permission_classes = [RosterPermission]
    pagination_class = None
    filterset_fields = ["don_vi", "loai_bo_phan", "dang_hoat_dong"]

    def get_queryset(self):
        queryset = _scope(BoPhan.objects.select_related("don_vi", "don_vi__nha_may"), self.request.user, "don_vi__nha_may_id")
        plant_id = self.request.query_params.get("nha_may")
        return queryset.filter(don_vi__nha_may_id=plant_id) if plant_id else queryset

    def perform_create(self, serializer):
        unit = serializer.validated_data["don_vi"]
        if not can_access_plant(self.request.user, unit.nha_may_pham_vi_id):
            raise PermissionDenied("Bạn không có quyền tạo bộ phận trong đơn vị này.")
        serializer.save()

    def perform_update(self, serializer):
        unit = serializer.validated_data.get("don_vi", serializer.instance.don_vi)
        if not can_access_plant(self.request.user, unit.nha_may_pham_vi_id):
            raise PermissionDenied("Bạn không có quyền chuyển bộ phận sang đơn vị này.")
        serializer.save()


class NhanSuViewSet(viewsets.ModelViewSet):
    serializer_class = NhanSuSerializer
    permission_classes = [LegacyStaffPermission]
    pagination_class = None
    filterset_fields = ["don_vi", "bo_phan", "user", "dang_lam_viec"]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["ho_ten", "ma_nhan_vien", "chuc_danh"]

    def get_queryset(self):
        return _scope(NhanSu.objects.select_related("don_vi", "bo_phan", "user"), self.request.user, "don_vi__nha_may_id")

    def perform_create(self, serializer):
        unit = serializer.validated_data["don_vi"]
        if not can_access_plant(self.request.user, unit.nha_may_pham_vi_id):
            raise PermissionDenied("Bạn không có quyền tạo nhân sự trong đơn vị này.")
        person = serializer.save()
        plant_id = unit.nha_may_pham_vi_id
        if plant_id:
            groups = NhomLichTruc.objects.filter(nha_may_id=plant_id, dang_hoat_dong=True)
            for g in groups:
                PhamViNhanSuCaTruc.objects.get_or_create(
                    nhom_lich=g, nhan_su=person,
                    defaults={"dang_hoat_dong": True}
                )
            draft_plans = PhuongAnPhanCongCa.objects.filter(
                nha_may_id=plant_id,
                trang_thai=PhuongAnPhanCongCa.TrangThai.DU_THAO
            )
            for plan in draft_plans:
                ChiTietPhuongAnPhanCongCa.objects.get_or_create(
                    phuong_an=plan,
                    nhan_su=person,
                    defaults={"kip_truc": None, "vai_tro": "", "thu_tu_hien_thi": 1}
                )

    def perform_update(self, serializer):
        unit = serializer.validated_data.get("don_vi", serializer.instance.don_vi)
        if not can_access_plant(self.request.user, unit.nha_may_pham_vi_id):
            raise PermissionDenied("Bạn không có quyền chuyển nhân sự sang đơn vị này.")
        serializer.save()

    def perform_destroy(self, instance):
        instance.dang_lam_viec = False
        instance.den_ngay = instance.den_ngay or max(date.today(), instance.tu_ngay)
        instance.save(update_fields=["dang_lam_viec", "den_ngay", "updated_at"])

    @action(detail=False, methods=["get"], url_path="tai-khoan-options")
    def tai_khoan_options(self, request):
        plant_id = request.query_params.get("nha_may")
        if not plant_id or not can_access_plant(request.user, plant_id):
            raise PermissionDenied("Bạn không có quyền xem tài khoản của nhà máy này.")
        queryset = User.objects.filter(is_active=True, profile__nha_may_id=plant_id).select_related("profile").order_by("username")
        return Response([{"id": item.id, "username": item.username, "full_name": getattr(item.profile, "full_name", "") or item.get_full_name() or item.username} for item in queryset])


class ThanhVienKipTrucViewSet(viewsets.ModelViewSet):
    serializer_class = ThanhVienKipTrucSerializer
    permission_classes = [RosterPermission]
    filterset_fields = ["kip_truc", "nhan_su", "user", "dang_hoat_dong"]

    def get_queryset(self):
        return _scope(ThanhVienKipTruc.objects.select_related("kip_truc", "nhan_su", "nhan_su__don_vi", "user", "user__profile"), self.request.user, "kip_truc__nha_may_id")

    def perform_create(self, serializer):
        team = serializer.validated_data["kip_truc"]
        if not can_access_plant(self.request.user, team.nha_may_id):
            raise PermissionDenied("Bạn không có quyền quản lý kíp của nhà máy này.")
        serializer.save()

    def perform_update(self, serializer):
        team = serializer.validated_data.get("kip_truc", serializer.instance.kip_truc)
        if not can_access_plant(self.request.user, team.nha_may_id):
            raise PermissionDenied("Bạn không có quyền chuyển thành viên sang kíp này.")
        serializer.save()


def _assignment_plan_issues(plan):
    required = {"truong_ca", "truc_chinh", "truc_phu"}
    issues = []
    rows = list(plan.chi_tiet.select_related("kip_truc", "nhan_su"))
    teams = KipTruc.objects.filter(
        nha_may=plan.nha_may,
        loai_kip=KipTruc.LoaiKip.VAN_HANH,
        dang_hoat_dong=True,
    )
    if plan.nhom_lich_id:
        teams = teams.filter(nhom_lich=plan.nhom_lich)
    for team in teams:
        team_rows = [row for row in rows if row.kip_truc_id == team.id]
        roles = {row.vai_tro for row in team_rows}
        if len(team_rows) < 3:
            issues.append(f"Kíp {team.ma_kip} phải có tối thiểu 3 người.")
        missing = required - roles
        if missing:
            labels = dict(ThanhVienKipTruc.VaiTro.choices)
            issues.append(f"Kíp {team.ma_kip} còn thiếu: {', '.join(labels[item] for item in sorted(missing))}.")
    return issues


def _assignment_plan_warnings(plan):
    warnings = []
    rows = list(plan.chi_tiet.select_related("kip_truc"))
    operational_teams = KipTruc.objects.filter(
        nha_may=plan.nha_may,
        loai_kip=KipTruc.LoaiKip.VAN_HANH,
        dang_hoat_dong=True,
    )
    if plan.nhom_lich_id:
        operational_teams = operational_teams.filter(nhom_lich=plan.nhom_lich)
    for team in operational_teams:
        member_count = sum(row.kip_truc_id == team.id for row in rows)
        if member_count > 3:
            warnings.append(
                f"Kíp {team.ma_kip} đang có {member_count} người, vượt biên chế chuẩn 3 người."
            )
    return warnings


def _handover_summary(day):
    incoming = []
    leaving = []
    if day.la_ngay_chuyen_kip:
        working = list(dict.fromkeys(filter(None, [day.kip_ca_ngay.ma_kip, day.kip_ca_dem.ma_kip])))
        incoming.extend(working)
        leaving.extend(team for team in ["A", "B", "C", "D"] if team not in working)
    if day.la_ngay_chuyen_ca_hc:
        current_admin = day.kip_hanh_chinh.ma_kip.removeprefix("HC")
        resting_admin = (
            "2" if current_admin == "1" else
            "1" if current_admin == "2" else
            "F" if current_admin == "E" else
            "E" if current_admin == "F" else ""
        )
        if current_admin:
            incoming.append(current_admin)
        if resting_admin:
            leaving.append(resting_admin)
    return ", ".join(incoming), ", ".join(leaving)


def _sync_draft_assignment_plan(plan):
    """
    Đồng bộ nhân sự của nhà máy/nhóm lịch vào phương án phân công đang ở trạng thái dự thảo.
    """
    if plan.trang_thai != PhuongAnPhanCongCa.TrangThai.DU_THAO:
        return
    plant = plan.nha_may
    group = plan.nhom_lich
    if group:
        scoped_ids = set(PhamViNhanSuCaTruc.objects.filter(
            nhom_lich=group, dang_hoat_dong=True
        ).values_list("nhan_su_id", flat=True))
        unit_personnel = NhanSu.objects.filter(don_vi__nha_may=plant, dang_lam_viec=True)
        if group.don_vi_id:
            unit_personnel = unit_personnel.filter(don_vi=group.don_vi)
        if group.bo_phan_id:
            unit_personnel = unit_personnel.filter(bo_phan=group.bo_phan)
        all_ids = scoped_ids | set(unit_personnel.values_list("id", flat=True))
        personnel = NhanSu.objects.filter(id__in=all_ids, dang_lam_viec=True)
    else:
        personnel = NhanSu.objects.filter(don_vi__nha_may=plant, dang_lam_viec=True)

    existing_ids = set(plan.chi_tiet.values_list("nhan_su_id", flat=True))
    missing = [p for p in personnel if p.id not in existing_ids]
    if missing:
        if group:
            for p in missing:
                PhamViNhanSuCaTruc.objects.get_or_create(
                    nhom_lich=group, nhan_su=p,
                    defaults={"dang_hoat_dong": True}
                )
        ChiTietPhuongAnPhanCongCa.objects.bulk_create([
            ChiTietPhuongAnPhanCongCa(
                phuong_an=plan,
                nhan_su=person,
                kip_truc=None,
                vai_tro="",
                thu_tu_hien_thi=1,
            ) for person in missing
        ])


class PhuongAnPhanCongCaViewSet(viewsets.ModelViewSet):
    serializer_class = PhuongAnPhanCongCaSerializer
    permission_classes = [RosterPermission]
    pagination_class = None
    filterset_fields = ["nha_may", "nhom_lich", "lich_truc", "thang", "nam", "trang_thai"]

    def get_queryset(self):
        queryset = PhuongAnPhanCongCa.objects.select_related("nha_may", "nguoi_tao", "nguoi_ap_dung").prefetch_related(
            "chi_tiet__nhan_su__bo_phan", "chi_tiet__kip_truc"
        )
        return _scope(queryset, self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        for plan in queryset:
            if plan.trang_thai == PhuongAnPhanCongCa.TrangThai.DU_THAO:
                _sync_draft_assignment_plan(plan)
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.trang_thai == PhuongAnPhanCongCa.TrangThai.DU_THAO:
            _sync_draft_assignment_plan(instance)
            instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_create(self, serializer):
        plant = serializer.validated_data["nha_may"]
        if not can_access_plant(self.request.user, plant.id):
            raise PermissionDenied("Bạn không có quyền lập phương án cho nhà máy này.")
        month = serializer.validated_data["thang"]
        year = serializer.validated_data["nam"]
        effective = serializer.validated_data["ngay_hieu_luc"]
        group = serializer.validated_data.get("nhom_lich")
        schedule = serializer.validated_data.get("lich_truc")
        if schedule and (schedule.nha_may_id != plant.id or schedule.nhom_lich_id != getattr(group, "id", None)):
            raise ValidationError({"lich_truc": "Lịch áp dụng không thuộc nhà máy/nhóm lịch đã chọn."})
        if group and group.nha_may_id != plant.id:
            raise ValidationError({"nhom_lich": "Nhóm lịch phải thuộc nhà máy của phương án."})
        if effective.year != year or effective.month != month:
            raise ValidationError({"ngay_hieu_luc": "Ngày hiệu lực phải thuộc tháng của phương án."})
        version = (PhuongAnPhanCongCa.objects.filter(nha_may=plant, nhom_lich=group, thang=month, nam=year).aggregate(value=Max("phien_ban"))["value"] or 0) + 1
        with transaction.atomic():
            plan = serializer.save(nguoi_tao=self.request.user, phien_ban=version)
            inherited_date = effective - timedelta(days=1)
            memberships = ThanhVienKipTruc.objects.filter(
                kip_truc__nha_may=plant, dang_hoat_dong=True, tu_ngay__lte=inherited_date,
            ).filter(Q(den_ngay__isnull=True) | Q(den_ngay__gte=inherited_date)).select_related("nhan_su", "kip_truc")
            if group:
                memberships = memberships.filter(kip_truc__nhom_lich=group)
                scoped_ids = set(PhamViNhanSuCaTruc.objects.filter(
                    nhom_lich=group, dang_hoat_dong=True
                ).values_list("nhan_su_id", flat=True))
                unit_personnel = NhanSu.objects.filter(don_vi__nha_may=plant, dang_lam_viec=True)
                if group.don_vi_id:
                    unit_personnel = unit_personnel.filter(don_vi=group.don_vi)
                if group.bo_phan_id:
                    unit_personnel = unit_personnel.filter(bo_phan=group.bo_phan)
                all_ids = scoped_ids | set(unit_personnel.values_list("id", flat=True))
                personnel = NhanSu.objects.filter(id__in=all_ids, dang_lam_viec=True).distinct().select_related("don_vi")
                for p in personnel:
                    if p.id not in scoped_ids:
                        PhamViNhanSuCaTruc.objects.get_or_create(
                            nhom_lich=group, nhan_su=p,
                            defaults={"dang_hoat_dong": True}
                        )
            else:
                personnel = NhanSu.objects.filter(don_vi__nha_may=plant, dang_lam_viec=True).select_related("don_vi")
            inherited = {item.nhan_su_id: item for item in memberships if item.nhan_su_id}
            ChiTietPhuongAnPhanCongCa.objects.bulk_create([
                ChiTietPhuongAnPhanCongCa(
                    phuong_an=plan, nhan_su=person,
                    kip_truc=inherited.get(person.id).kip_truc if person.id in inherited else None,
                    vai_tro=inherited.get(person.id).vai_tro if person.id in inherited else "",
                    thu_tu_hien_thi=inherited.get(person.id).thu_tu_hien_thi if person.id in inherited else 1,
                ) for person in personnel
            ])

    def perform_update(self, serializer):
        if not can_access_plant(self.request.user, serializer.instance.nha_may_id):
            raise PermissionDenied("Bạn không có quyền sửa phương án này.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.trang_thai != PhuongAnPhanCongCa.TrangThai.DU_THAO:
            raise ValidationError("Chỉ được xóa phương án đang ở trạng thái dự thảo.")
        instance.delete()

    @action(detail=True, methods=["get"], url_path="kiem-tra")
    def kiem_tra(self, request, pk=None):
        plan = self.get_object()
        issues = _assignment_plan_issues(plan)
        return Response({
            "hop_le": not issues,
            "loi": issues,
            "canh_bao": _assignment_plan_warnings(plan),
        })

    @action(detail=True, methods=["post"], url_path="ap-dung")
    def ap_dung(self, request, pk=None):
        plan = self.get_object()
        if plan.trang_thai not in {
            PhuongAnPhanCongCa.TrangThai.DU_THAO,
            PhuongAnPhanCongCa.TrangThai.DA_AP_DUNG,
        }:
            raise ValidationError("Chỉ được áp dụng phương án đang ở trạng thái dự thảo.")
        issues = _assignment_plan_issues(plan)
        if issues:
            raise ValidationError({"chi_tiet": issues})
        effective = plan.ngay_hieu_luc
        with transaction.atomic():
            if plan.lich_truc_id and plan.lich_truc.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE:
                teams = KipTruc.objects.filter(nha_may=plan.nha_may, dang_hoat_dong=True)
                if plan.nhom_lich_id:
                    teams = teams.filter(nhom_lich=plan.nhom_lich)
                # Giữ cả khóa có danh sách rỗng để phân biệt "chủ động không
                # bố trí nhân sự" với lịch cũ chưa có snapshot phân công.
                snapshot = {team.ma_kip: [] for team in teams}
                for row in plan.chi_tiet.select_related("nhan_su", "kip_truc"):
                    if row.kip_truc_id:
                        snapshot.setdefault(row.kip_truc.ma_kip, []).append({
                            "user_id": row.nhan_su.user_id,
                            "nhan_su_id": row.nhan_su_id,
                            "ho_ten": row.nhan_su.ho_ten,
                            "vai_tro": row.vai_tro,
                        })
                plan.lich_truc.snapshot_nhan_su = snapshot
                plan.lich_truc.save(update_fields=["snapshot_nhan_su", "updated_at"])
                plan.trang_thai = PhuongAnPhanCongCa.TrangThai.DA_AP_DUNG
                plan.nguoi_ap_dung = request.user
                plan.ngay_ap_dung = timezone.now()
                plan.save(update_fields=["trang_thai", "nguoi_ap_dung", "ngay_ap_dung", "updated_at"])
                return Response(self.get_serializer(plan).data)
            for row in plan.chi_tiet.select_related("nhan_su", "kip_truc"):
                future = ThanhVienKipTruc.objects.filter(nhan_su=row.nhan_su, tu_ngay__gt=effective)
                if plan.nhom_lich_id:
                    future = future.filter(kip_truc__nhom_lich=plan.nhom_lich)
                if future.exists():
                    raise ValidationError(f"{row.nhan_su.ho_ten} đã có phân công tương lai; cần xử lý trước khi áp dụng.")
                active_query = ThanhVienKipTruc.objects.select_for_update().filter(
                    nhan_su=row.nhan_su, tu_ngay__lte=effective,
                ).filter(Q(den_ngay__isnull=True) | Q(den_ngay__gte=effective))
                if plan.nhom_lich_id:
                    active_query = active_query.filter(kip_truc__nhom_lich=plan.nhom_lich)
                active = list(active_query)
                unchanged = row.kip_truc_id and any(item.kip_truc_id == row.kip_truc_id and item.vai_tro == row.vai_tro for item in active)
                if unchanged:
                    continue
                for membership in active:
                    if membership.tu_ngay == effective:
                        membership.delete()
                    else:
                        membership.den_ngay = effective - timedelta(days=1)
                        membership.save(update_fields=["den_ngay", "updated_at"])
                if row.kip_truc_id:
                    ThanhVienKipTruc.objects.create(
                        kip_truc=row.kip_truc, nhan_su=row.nhan_su, vai_tro=row.vai_tro,
                        tu_ngay=effective, thu_tu_hien_thi=row.thu_tu_hien_thi, dang_hoat_dong=True,
                    )
            plan.trang_thai = PhuongAnPhanCongCa.TrangThai.DA_AP_DUNG
            plan.nguoi_ap_dung = request.user
            plan.ngay_ap_dung = timezone.now()
            plan.save(update_fields=["trang_thai", "nguoi_ap_dung", "ngay_ap_dung", "updated_at"])
        return Response(self.get_serializer(plan).data)

    @action(detail=True, methods=["post"], url_path="khoa")
    def khoa(self, request, pk=None):
        plan = self.get_object()
        if plan.trang_thai != PhuongAnPhanCongCa.TrangThai.DA_AP_DUNG:
            raise ValidationError("Chỉ được khóa phương án đã áp dụng.")
        plan.trang_thai = PhuongAnPhanCongCa.TrangThai.DA_KHOA
        plan.save(update_fields=["trang_thai", "updated_at"])
        return Response(self.get_serializer(plan).data)


class ChiTietPhuongAnPhanCongCaViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = ChiTietPhuongAnPhanCongCaSerializer
    permission_classes = [RosterPermission]
    filterset_fields = ["phuong_an", "nhan_su", "kip_truc"]

    def get_queryset(self):
        queryset = ChiTietPhuongAnPhanCongCa.objects.select_related("phuong_an", "nhan_su__bo_phan", "kip_truc")
        return _scope(queryset, self.request.user, "phuong_an__nha_may_id")

    def perform_update(self, serializer):
        if not can_access_plant(self.request.user, serializer.instance.phuong_an.nha_may_id):
            raise PermissionDenied("Bạn không có quyền sửa phương án này.")
        serializer.save()


class MauChuKyCaTrucViewSet(viewsets.ModelViewSet):
    serializer_class = MauChuKyCaTrucSerializer
    permission_classes = [RosterPermission]
    pagination_class = None
    filterset_fields = ["nha_may", "nhom_lich", "dang_hoat_dong"]

    def get_queryset(self):
        return _scope(MauChuKyCaTruc.objects.select_related("nha_may"), self.request.user)

    def perform_create(self, serializer):
        plant = serializer.validated_data["nha_may"]
        if not can_access_plant(self.request.user, plant.id):
            raise PermissionDenied("Bạn không có quyền tạo mẫu cho nhà máy này.")
        serializer.save()


class NgayTrucCaViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = NgayTrucCaSerializer
    permission_classes = [ShiftSchedulePermission]
    filterset_fields = ["lich_truc", "ngay"]

    def get_queryset(self):
        queryset = NgayTrucCa.objects.select_related("lich_truc", "kip_ca_ngay", "kip_ca_dem", "kip_hanh_chinh", "kip_hanh_chinh_truoc")
        return _scope(queryset, self.request.user, "lich_truc__nha_may_id")

    def perform_update(self, serializer):
        try:
            serializer.save()
        except DjangoValidationError as error:
            raise _translate_validation(error) from error


class DieuChinhNhanSuCaTrucViewSet(viewsets.ModelViewSet):
    serializer_class = DieuChinhNhanSuCaTrucSerializer
    permission_classes = [ShiftAdjustmentPermission]
    filterset_fields = ["ngay_truc", "loai_ca", "loai_dieu_chinh", "trang_thai"]

    def get_queryset(self):
        queryset = DieuChinhNhanSuCaTruc.objects.select_related(
            "ngay_truc__lich_truc", "ngay_truc_doi__lich_truc", "nhan_su_vang", "nhan_su_thay", "nguoi_tao", "nguoi_duyet"
        )
        return _scope(queryset, self.request.user, "ngay_truc__lich_truc__nha_may_id")

    @action(detail=False, methods=["post"], url_path="tao-theo-khoang")
    def tao_theo_khoang(self, request):
        try:
            start = date.fromisoformat(str(request.data.get("tu_ngay") or ""))
            end = date.fromisoformat(str(request.data.get("den_ngay") or ""))
            start_time = time.fromisoformat(str(request.data.get("tu_gio") or "00:00"))
            end_time = time.fromisoformat(str(request.data.get("den_gio") or "23:59:59"))
        except ValueError as error:
            raise ValidationError("Khoảng ngày giờ không hợp lệ.") from error
        starts_at = datetime.combine(start, start_time)
        ends_at = datetime.combine(end, end_time)
        if ends_at <= starts_at or (ends_at - starts_at) > timedelta(days=6):
            raise ValidationError("Khoảng điều chỉnh phải từ 1 đến tối đa 6 ngày.")
        try:
            schedule = self.request.user.is_authenticated and LichTrucCa.objects.get(pk=request.data.get("lich_truc"))
        except (LichTrucCa.DoesNotExist, TypeError, ValueError) as error:
            raise ValidationError("Lịch trực cần điều chỉnh không hợp lệ.") from error
        if not can_access_plant(request.user, schedule.nha_may_id):
            raise PermissionDenied("Bạn không có quyền điều chỉnh nhân sự nhà máy này.")
        adjustment_type = str(request.data.get("loai_dieu_chinh") or "")
        if adjustment_type == DieuChinhNhanSuCaTruc.LoaiDieuChinh.DOI_CA:
            raise ValidationError("Đổi ca hai chiều phải chọn từng cặp ca đối ứng.")
        raw_absent_ids = request.data.get("nhan_su_vang_ids") or [request.data.get("nhan_su_vang")]
        try:
            absent_ids = {int(value) for value in raw_absent_ids if value not in (None, "")}
        except (TypeError, ValueError) as error:
            raise ValidationError("Danh sách nhân sự vắng không hợp lệ.") from error
        if not absent_ids:
            raise ValidationError("Phải chọn ít nhất một nhân sự vắng.")
        replacement_id = request.data.get("nhan_su_thay")
        replacement = NhanSu.objects.filter(pk=replacement_id).first() if replacement_id else None
        optional_replacement_types = {
            DieuChinhNhanSuCaTruc.LoaiDieuChinh.NGHI_PHEP,
            DieuChinhNhanSuCaTruc.LoaiDieuChinh.NGHI_BU,
        }
        if adjustment_type not in optional_replacement_types and not replacement:
            raise ValidationError("Phải chọn người trực thay.")
        period_value = str(request.data.get("loai_ca") or "theo_lich")
        periods = [period_value] if period_value in DieuChinhNhanSuCaTruc.LoaiCa.values else list(DieuChinhNhanSuCaTruc.LoaiCa.values)
        reason = str(request.data.get("ly_do") or "").strip()
        if not reason:
            raise ValidationError("Phải nhập lý do điều chỉnh.")
        batch_id = uuid.uuid4()
        created = []
        days = schedule.danh_sach_ngay.filter(ngay__range=(start, end)).select_related("lich_truc", "kip_ca_ngay", "kip_ca_dem", "kip_hanh_chinh")
        with transaction.atomic():
            for day in days:
                for period in periods:
                    shift_hour = 20 if period == DieuChinhNhanSuCaTruc.LoaiCa.CA_DEM else 8
                    if period == DieuChinhNhanSuCaTruc.LoaiCa.CA_NGAY and day.la_ngay_chuyen_kip:
                        shift_hour = 12
                    shift_starts_at = datetime.combine(day.ngay, time(hour=shift_hour))
                    if not (starts_at <= shift_starts_at < ends_at):
                        continue
                    source_staff = actual_shift_staff(day, period)
                    selected_staff = [
                        item for item in source_staff
                        if item["nhan_su_id"] and item["nhan_su_id"] in absent_ids
                    ]
                    for source_person in selected_staff:
                        absent = NhanSu.objects.get(pk=source_person["nhan_su_id"])
                        if DieuChinhNhanSuCaTruc.objects.filter(
                            ngay_truc=day, loai_ca=period, nhan_su_vang=absent,
                            trang_thai__in=[DieuChinhNhanSuCaTruc.TrangThai.DU_THAO, DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET],
                        ).exists():
                            raise ValidationError(f"Ngày {day.ngay:%d/%m/%Y} đã có điều chỉnh cho {absent.ho_ten}.")
                        item = DieuChinhNhanSuCaTruc(
                            ma_phieu=batch_id, ngay_truc=day, loai_ca=period,
                            loai_dieu_chinh=adjustment_type, nhan_su_vang=absent,
                            nhan_su_thay=replacement, vai_tro_thay=source_person["vai_tro"] if replacement else "",
                            ly_do=reason, nguoi_tao=request.user,
                        )
                        item.save()
                        created.append(item)
            if not created:
                raise ValidationError("Nhân sự không có ca trực nào trong khoảng đã chọn.")
        return Response({"ma_phieu": str(batch_id), "so_ca": len(created), "chi_tiet": self.get_serializer(created, many=True).data}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="phe-duyet-phieu")
    def phe_duyet_phieu(self, request, pk=None):
        current = self.get_object()
        items = list(self.get_queryset().filter(ma_phieu=current.ma_phieu).order_by("ngay_truc__ngay", "loai_ca"))
        if not items or any(item.trang_thai != DieuChinhNhanSuCaTruc.TrangThai.DU_THAO for item in items):
            raise ValidationError("Chỉ được duyệt phiếu khi toàn bộ chi tiết còn ở trạng thái dự thảo.")
        for item in items:
            source_ids = {staff["nhan_su_id"] for staff in actual_shift_staff(item.ngay_truc, item.loai_ca) if staff["nhan_su_id"]}
            if item.nhan_su_vang_id not in source_ids:
                raise ValidationError(f"Nhân sự không còn thuộc ca ngày {item.ngay_truc.ngay:%d/%m/%Y}.")
            if item.nhan_su_thay_id and item.nhan_su_thay_id in source_ids:
                raise ValidationError(f"Người trực thay đã có trong ca ngày {item.ngay_truc.ngay:%d/%m/%Y}.")
            validate_replacement_availability(item)
            validate_operation_staffing(item)
        from django.utils import timezone
        with transaction.atomic():
            for item in items:
                item.trang_thai = DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET
                item.nguoi_duyet = request.user
                item.ngay_duyet = timezone.now()
                item.ly_do_tu_choi = ""
                item.save()
        return Response({"ma_phieu": str(current.ma_phieu), "so_ca": len(items), "chi_tiet": self.get_serializer(items, many=True).data})

    @action(detail=True, methods=["post"], url_path="tu-choi-phieu")
    def tu_choi_phieu(self, request, pk=None):
        current = self.get_object()
        reason = str(request.data.get("ly_do") or "").strip()
        items = list(self.get_queryset().filter(ma_phieu=current.ma_phieu, trang_thai=DieuChinhNhanSuCaTruc.TrangThai.DU_THAO))
        if not reason or not items:
            raise ValidationError("Phải nhập lý do và phiếu phải đang ở trạng thái dự thảo.")
        from django.utils import timezone
        with transaction.atomic():
            for item in items:
                item.trang_thai = DieuChinhNhanSuCaTruc.TrangThai.TU_CHOI
                item.nguoi_duyet = request.user
                item.ngay_duyet = timezone.now()
                item.ly_do_tu_choi = reason
                item.save()
        return Response({"ma_phieu": str(current.ma_phieu), "so_ca": len(items)})

    @action(detail=True, methods=["delete"], url_path="xoa-phieu")
    def xoa_phieu(self, request, pk=None):
        current = self.get_object()
        if not current.ma_phieu:
            current.delete()
            return Response({"ma_phieu": None, "so_ca": 1}, status=status.HTTP_200_OK)
        items = self.get_queryset().filter(ma_phieu=current.ma_phieu)
        count = items.count()
        items.delete()
        return Response({"ma_phieu": str(current.ma_phieu), "so_ca": count}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        day = serializer.validated_data["ngay_truc"]
        if not can_access_plant(self.request.user, day.lich_truc.nha_may_id):
            raise PermissionDenied("Bạn không có quyền điều chỉnh nhân sự nhà máy này.")
        try:
            serializer.save(nguoi_tao=self.request.user)
        except DjangoValidationError as error:
            raise _translate_validation(error) from error

    def perform_update(self, serializer):
        try:
            serializer.save()
        except DjangoValidationError as error:
            raise _translate_validation(error) from error

    def perform_destroy(self, instance):
        instance.delete()

    @action(detail=True, methods=["post"], url_path="phe-duyet")
    def phe_duyet(self, request, pk=None):
        adjustment = self.get_object()
        if adjustment.trang_thai != DieuChinhNhanSuCaTruc.TrangThai.DU_THAO:
            raise ValidationError("Chỉ được duyệt điều chỉnh đang ở trạng thái dự thảo.")
        if adjustment.nhan_su_thay_id and DieuChinhNhanSuCaTruc.objects.filter(
            ngay_truc=adjustment.ngay_truc,
            loai_ca=adjustment.loai_ca,
            nhan_su_thay=adjustment.nhan_su_thay,
            trang_thai=DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET,
        ).exclude(pk=adjustment.pk).exists():
            raise ValidationError("Nhân sự này đã được phân công trong ca trực.")
        source_ids = {item["nhan_su_id"] for item in actual_shift_staff(adjustment.ngay_truc, adjustment.loai_ca) if item["nhan_su_id"]}
        if adjustment.nhan_su_vang_id and adjustment.nhan_su_vang_id not in source_ids:
            raise ValidationError("Người vắng/được thay không thuộc nhân sự thực tế của ca nguồn.")
        if adjustment.loai_dieu_chinh == DieuChinhNhanSuCaTruc.LoaiDieuChinh.DOI_CA:
            target_ids = {item["nhan_su_id"] for item in actual_shift_staff(adjustment.ngay_truc_doi, adjustment.loai_ca_doi) if item["nhan_su_id"]}
            if adjustment.nhan_su_thay_id not in target_ids:
                raise ValidationError("Người đổi ca không thuộc nhân sự thực tế của ca đối ứng.")
        try:
            validate_replacement_availability(adjustment)
            validate_operation_staffing(adjustment)
        except DjangoValidationError as error:
            raise _translate_validation(error) from error
        from django.utils import timezone
        adjustment.trang_thai = DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET
        adjustment.nguoi_duyet = request.user
        adjustment.ngay_duyet = timezone.now()
        adjustment.ly_do_tu_choi = ""
        adjustment.save()
        return Response(self.get_serializer(adjustment).data)

    @action(detail=True, methods=["post"], url_path="tu-choi")
    def tu_choi(self, request, pk=None):
        adjustment = self.get_object()
        reason = str(request.data.get("ly_do") or "").strip()
        if adjustment.trang_thai != DieuChinhNhanSuCaTruc.TrangThai.DU_THAO or not reason:
            raise ValidationError("Phải nhập lý do và chỉ được từ chối điều chỉnh dự thảo.")
        adjustment.trang_thai = DieuChinhNhanSuCaTruc.TrangThai.TU_CHOI
        adjustment.nguoi_duyet = request.user
        adjustment.ly_do_tu_choi = reason
        adjustment.save()
        return Response(self.get_serializer(adjustment).data)


class LichTrucCaViewSet(viewsets.ModelViewSet):
    serializer_class = LichTrucCaSerializer
    permission_classes = [ShiftSchedulePermission]
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["nha_may", "nhom_lich", "thang", "nam", "trang_thai"]
    ordering_fields = ["nam", "thang", "created_at"]
    ordering = ["-nam", "-thang", "-phien_ban"]

    def get_queryset(self):
        queryset = LichTrucCa.objects.select_related("nha_may", "mau_chu_ky", "nguoi_tao", "nguoi_duyet").prefetch_related(
            "danh_sach_ngay__kip_ca_ngay", "danh_sach_ngay__kip_ca_dem", "danh_sach_ngay__kip_hanh_chinh",
            "danh_sach_ngay__dieu_chinh_nhan_su__nhan_su_vang", "danh_sach_ngay__dieu_chinh_nhan_su__nhan_su_thay",
            "danh_sach_ngay__dieu_chinh_doi_den__nhan_su_vang", "danh_sach_ngay__dieu_chinh_doi_den__nhan_su_thay",
            "lich_su__nguoi_thuc_hien"
        )
        return _scope(queryset, self.request.user)

    def perform_create(self, serializer):
        plant = serializer.validated_data["nha_may"]
        if not can_access_plant(self.request.user, plant.id):
            raise PermissionDenied("Bạn không có quyền tạo lịch cho nhà máy này.")
        month = serializer.validated_data["thang"]
        year = serializer.validated_data["nam"]
        group = serializer.validated_data.get("nhom_lich")
        template = serializer.validated_data["mau_chu_ky"]
        if group and group.nha_may_id != plant.id:
            raise ValidationError({"nhom_lich": "Nhóm lịch phải thuộc nhà máy đã chọn."})
        if group and template.nhom_lich_id and template.nhom_lich_id != group.id:
            raise ValidationError({"mau_chu_ky": "Mẫu chu kỳ phải thuộc nhóm lịch đã chọn."})
        # Lock the plant while allocating a version. Locking only existing
        # schedules would not protect the first version of a new month.
        with transaction.atomic():
            type(plant).objects.select_for_update().get(pk=plant.pk)
            version = LichTrucCa.objects.filter(
                nha_may=plant, nhom_lich=group, thang=month, nam=year
            ).aggregate(value=Max("phien_ban"))["value"] or 0
            serializer.save(nguoi_tao=self.request.user, phien_ban=version + 1)

    def perform_update(self, serializer):
        if not serializer.instance.co_the_chinh_sua:
            raise ValidationError("Chỉ được sửa lịch dự thảo hoặc bị từ chối.")
        serializer.save()

    def perform_destroy(self, instance):
        if not instance.co_the_chinh_sua:
            raise ValidationError("Chỉ được xóa lịch dự thảo hoặc bị từ chối.")
        with transaction.atomic():
            PhuongAnPhanCongCa.objects.filter(
                lich_truc=instance,
                trang_thai=PhuongAnPhanCongCa.TrangThai.DU_THAO,
            ).delete()
            instance.delete()

    @action(detail=True, methods=["post"], url_path="sinh-lich")
    def sinh_lich(self, request, pk=None):
        try:
            schedule = generate_monthly_schedule(pk, request.user)
        except DjangoValidationError as error:
            raise _translate_validation(error) from error
        return Response(self.get_serializer(schedule).data)

    def _transition(self, request, pk, action_name):
        data = TransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            schedule = transition_schedule(pk, request.user, action_name, data.validated_data["ly_do"])
        except DjangoValidationError as error:
            raise _translate_validation(error) from error
        return Response(self.get_serializer(schedule).data)

    @action(detail=True, methods=["post"], url_path="gui-duyet")
    def gui_duyet(self, request, pk=None):
        return self._transition(request, pk, "gui_duyet")

    @action(detail=True, methods=["post"], url_path="phe-duyet")
    def phe_duyet(self, request, pk=None):
        return self._transition(request, pk, "phe_duyet")

    @action(detail=True, methods=["post"], url_path="tu-choi")
    def tu_choi(self, request, pk=None):
        return self._transition(request, pk, "tu_choi")

    @action(detail=True, methods=["post"], url_path="ap-dung")
    def ap_dung(self, request, pk=None):
        return self._transition(request, pk, "ap_dung")

    @action(detail=True, methods=["post"], url_path="khoa")
    def khoa(self, request, pk=None):
        return self._transition(request, pk, "khoa")

    def _ensure_exportable(self, schedule):
        if schedule.trang_thai not in {LichTrucCa.TrangThai.DA_DUYET, LichTrucCa.TrangThai.DANG_AP_DUNG, LichTrucCa.TrangThai.DA_KHOA}:
            raise ValidationError("Chỉ được xuất lịch đã duyệt, đang áp dụng hoặc đã khóa.")

    @action(detail=True, methods=["get"], url_path="xuat-excel")
    def xuat_excel(self, request, pk=None):
        schedule = self.get_object()
        self._ensure_exportable(schedule)
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Lịch trực ca")

        # Style formats for Administrative / National Header
        company_header = workbook.add_format({"bold": True, "align": "center", "font_size": 10, "font_color": "#1E3A8A"})
        plant_header = workbook.add_format({"bold": True, "align": "center", "font_size": 10, "font_color": "#334151"})
        dept_header = workbook.add_format({"italic": True, "align": "center", "font_size": 9.5, "font_color": "#64748B"})
        country_header = workbook.add_format({"bold": True, "align": "center", "font_size": 10, "font_color": "#0F172A"})
        motto_header = workbook.add_format({"bold": True, "align": "center", "font_size": 10, "font_color": "#334151"})
        line_header = workbook.add_format({"align": "center", "font_size": 9, "font_color": "#94A3B8"})

        title = workbook.add_format({"bold": True, "align": "center", "font_size": 14, "font_color": "#1E3A8A"})
        header = workbook.add_format({"bold": True, "align": "center", "border": 1, "bg_color": "#D1D5DB", "font_color": "#374151"})
        cell = workbook.add_format({"align": "center", "border": 1})
        staff_cell = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1, "text_wrap": True, "font_size": 9})
        transition_cell = workbook.add_format({
            "align": "center", "border": 1, "bold": True,
            "font_color": "#3730A3", "bg_color": "#E0E7FF",
        })
        transition_staff_cell = workbook.add_format({
            "align": "center", "valign": "vcenter", "border": 1, "bold": True,
            "text_wrap": True, "font_size": 9, "font_color": "#3730A3", "bg_color": "#E0E7FF",
        })
        combined_transition_cell = workbook.add_format({
            "align": "center", "border": 1, "bold": True,
            "font_color": "#A16207", "bg_color": "#FEF9C3",
        })
        roster_cell = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1, "text_wrap": True})
        note_format = workbook.add_format({
            "bold": False, "text_wrap": True, "valign": "top",
            "border": 1, "bg_color": "#EEF2FF", "font_color": "#3730A3",
        })

        days = list(schedule.danh_sach_ngay.all())
        custom_staff = custom_schedule_staff_labels(days) if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE else {}

        # Plant name resolution
        plant_raw = schedule.nha_may.ten_nha_may.upper() if schedule.nha_may else "SÔNG HINH"
        plant_display = plant_raw if plant_raw.startswith("NHÀ MÁY") else f"NHÀ MÁY THỦY ĐIỆN {plant_raw}"

        if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE:
            schedule_main_title = f"{schedule.ten_lich.upper()} - THÁNG {schedule.thang:02d}/{schedule.nam} - {plant_display}"
        else:
            schedule_main_title = f"LỊCH TRỰC CA THÁNG {schedule.thang:02d} NĂM {schedule.nam} - {plant_display}"

        total_cols = max(len(days), 7)
        mid_col = max(3, total_cols // 2)

        # Left Header
        sheet.merge_range(0, 0, 0, mid_col, "CÔNG TY CỔ PHẦN THỦY ĐIỆN VĨNH SƠN - SÔNG HINH", company_header)
        sheet.merge_range(1, 0, 1, mid_col, plant_display, plant_header)
        sheet.merge_range(2, 0, 2, mid_col, "Phân xưởng Vận hành", dept_header)

        # Right Header
        sheet.merge_range(0, mid_col + 1, 0, total_cols, "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", country_header)
        sheet.merge_range(1, mid_col + 1, 1, total_cols, "Độc lập - Tự do - Hạnh phúc", motto_header)
        sheet.merge_range(2, mid_col + 1, 2, total_cols, "—————————", line_header)

        # Main Title (Row 4)
        sheet.merge_range(4, 0, 4, total_cols, schedule_main_title, title)

        handover_summaries = [_handover_summary(day) for day in days]
        day_label, night_label = _shift_time_labels(schedule)
        rows = [("Thứ", ["CN" if d.ngay.weekday() == 6 else str(d.ngay.weekday() + 2) for d in days]), ("Ngày DL", [d.ngay.day for d in days]), (day_label, [d.hien_thi_ca_ngay for d in days]), (night_label, [d.kip_ca_dem.ma_kip for d in days]), ("Ca KT-HC", [d.hien_thi_ca_hanh_chinh for d in days]), ("Vào làm việc", [summary[0] for summary in handover_summaries]), ("Nghỉ ca", [summary[1] for summary in handover_summaries])]
        if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE:
            rows.insert(2, ("Ngày ÂL", [f"{d.ngay_am}/{d.thang_am}" if d.ngay_am else "" for d in days]))
            for index, (label, values) in enumerate(rows):
                period = {day_label: "ca_ngay", night_label: "ca_dem", "Ca KT-HC": "hanh_chinh"}.get(label)
                if period:
                    rows[index] = (label, [_custom_staff_value(d, period, custom_staff) for d in days])
        for row_index, (label, values) in enumerate(rows, start=6):
            sheet.write(row_index, 0, label, header)
            for column, value in enumerate(values, start=1):
                day = days[column - 1]
                is_transition = (
                    (label in {day_label, night_label} and day.la_ngay_chuyen_kip)
                    or (label == "Ca KT-HC" and day.la_ngay_chuyen_ca_hc)
                    or (label in {"Vào làm việc", "Nghỉ ca"} and (day.la_ngay_chuyen_kip or day.la_ngay_chuyen_ca_hc))
                )
                is_combined_header = label in {"Thứ", "Ngày DL", "Ngày ÂL"} and day.la_ngay_chuyen_kip and day.la_ngay_chuyen_ca_hc
                is_staff_row = schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE and label in {day_label, night_label, "Ca KT-HC"}
                output_format = combined_transition_cell if is_combined_header else transition_staff_cell if is_staff_row and is_transition else staff_cell if is_staff_row else transition_cell if is_transition else cell
                sheet.write(row_index, column, value, output_format)
            if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE and label in {day_label, night_label, "Ca KT-HC"}:
                sheet.set_row(row_index, 48)

        if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE:
            note = schedule.ghi_chu.strip() or "Chưa có ghi chú."
            note_row = len(rows) + 7
            sheet.merge_range(note_row, 0, note_row + 1, max(len(days), 6), f"Ghi chú lịch: {note}", note_format)
            sheet.set_column(0, 0, 16)
            sheet.set_column(1, len(days), 8)
            sheet.freeze_panes(6, 1)
            sheet.set_landscape()
            sheet.fit_to_pages(1, 0)
            sheet.set_margins(left=0.25, right=0.25, top=0.4, bottom=0.4)
            sheet.print_area(0, 0, note_row + 1, max(len(days), 6))
            workbook.close()
            response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f'attachment; filename="lich-chuyen-de-thang-{schedule.thang:02d}-{schedule.nam}.xlsx"'
            return response

        roster_title_row = len(rows) + 7
        sheet.merge_range(roster_title_row, 0, roster_title_row, 6, "DANH SÁCH NHÂN SỰ CA TRỰC", header)
        export_teams, snapshot, role_rows = _export_roster(schedule)
        team_codes = [team.ma_kip for team in export_teams]
        team_labels = [_export_team_label(team) for team in export_teams]
        col_ranges = [
            (1 + (index * len(days)) // len(export_teams), ((index + 1) * len(days)) // len(export_teams))
            for index in range(len(export_teams))
        ]
        current_row = roster_title_row + 1
        sheet.write(current_row, 0, "Chức danh", header)
        for index, label in enumerate(team_labels):
            start_col, end_col = col_ranges[index]
            if start_col == end_col:
                sheet.write(current_row, start_col, label, header)
            else:
                sheet.merge_range(current_row, start_col, current_row, end_col, label, header)
        for role, label in role_rows:
            current_row += 1
            sheet.write(current_row, 0, label, header)
            for index, code in enumerate(team_codes):
                start_col, end_col = col_ranges[index]
                names = "\n".join(
                    str(member.get("ho_ten") or "")
                    for member in snapshot.get(code, [])
                    if member.get("vai_tro") == role and member.get("ho_ten")
                ) or "—"
                if start_col == end_col:
                    sheet.write(current_row, start_col, names, roster_cell)
                else:
                    sheet.merge_range(current_row, start_col, current_row, end_col, names, roster_cell)

        adjustments = list(DieuChinhNhanSuCaTruc.objects.filter(
            ngay_truc__lich_truc=schedule,
            trang_thai=DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET,
        ).select_related("ngay_truc", "ngay_truc_doi", "nhan_su_vang", "nhan_su_thay"))
        if adjustments:
            adj_title_row = current_row + 2
            sheet.merge_range(adj_title_row, 0, adj_title_row, 6, "ĐIỀU CHỈNH NHÂN SỰ ĐÃ DUYỆT", header)
            headers = ["Ngày", "Ca", "Hình thức", "Người vắng", "Người thay", "Ca đối ứng", "Vai trò", "Lý do"]
            adj_col_ranges = [(1 + (idx * len(days)) // 8, ((idx + 1) * len(days)) // 8) for idx in range(8)]
            adj_header_row = adj_title_row + 1
            for idx, h_text in enumerate(headers):
                if idx == 0:
                    sheet.write(adj_header_row, 0, h_text, header)
                else:
                    s_col, e_col = adj_col_ranges[idx]
                    if s_col == e_col:
                        sheet.write(adj_header_row, s_col, h_text, header)
                    else:
                        sheet.merge_range(adj_header_row, s_col, adj_header_row, e_col, h_text, header)
            current_row = adj_header_row
            for item in adjustments:
                current_row += 1
                row_vals = [
                    item.ngay_truc.ngay.strftime("%d/%m/%Y"), item.get_loai_ca_display(), item.get_loai_dieu_chinh_display(),
                    item.nhan_su_vang.ho_ten if item.nhan_su_vang_id else "—", item.nhan_su_thay.ho_ten if item.nhan_su_thay_id else "—",
                    f"{item.ngay_truc_doi.ngay:%d/%m/%Y} · {item.get_loai_ca_doi_display()}" if item.ngay_truc_doi_id else "—",
                    item.get_vai_tro_thay_display() if item.vai_tro_thay else "—", item.ly_do,
                ]
                for idx, val in enumerate(row_vals):
                    if idx == 0:
                        sheet.write(current_row, 0, val, cell)
                    else:
                        s_col, e_col = adj_col_ranges[idx]
                        if s_col == e_col:
                            sheet.write(current_row, s_col, val, cell)
                        else:
                            sheet.merge_range(current_row, s_col, current_row, e_col, val, cell)

        note = schedule.ghi_chu.strip() or "Chưa có ghi chú."
        note_row = current_row + 2
        sheet.merge_range(note_row, 0, note_row + 1, max(len(days), 6), f"Ghi chú lịch: {note}", note_format)

        sheet.set_column(0, 0, 16)
        sheet.set_column(1, len(days), 8)
        sheet.freeze_panes(6, 1)
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.set_margins(left=0.25, right=0.25, top=0.4, bottom=0.4)
        sheet.print_area(0, 0, note_row + 1, max(len(days), 6))
        workbook.close()
        response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="lich-truc-thang-{schedule.thang:02d}-{schedule.nam}.xlsx"'
        return response

    @action(detail=True, methods=["get"], url_path="xuat-pdf")
    def xuat_pdf(self, request, pk=None):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape

        schedule = self.get_object()
        self._ensure_exportable(schedule)
        output = BytesIO()
        font_name = "Helvetica"
        font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("DejaVu", str(font_path)))
            font_name = "DejaVu"

        document = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            leftMargin=20,
            rightMargin=20,
            topMargin=20,
            bottomMargin=20,
        )
        styles = getSampleStyleSheet()
        styles["Title"].fontName = font_name
        styles["Title"].fontSize = 13
        styles["Title"].leading = 16
        styles["Title"].spaceAfter = 6
        styles["Heading3"].fontName = font_name

        pdf_header_left_style = ParagraphStyle(
            "PdfHeaderLeft", parent=styles["Normal"], fontName=font_name,
            fontSize=8, leading=11.5, alignment=1, textColor=colors.HexColor("#1E3A8A"),
        )
        pdf_header_right_style = ParagraphStyle(
            "PdfHeaderRight", parent=styles["Normal"], fontName=font_name,
            fontSize=8, leading=11.5, alignment=1, textColor=colors.HexColor("#0F172A"),
        )

        plant_raw = schedule.nha_may.ten_nha_may.upper() if schedule.nha_may else "SÔNG HINH"
        plant_display = plant_raw if plant_raw.startswith("NHÀ MÁY") else f"NHÀ MÁY THỦY ĐIỆN {plant_raw}"

        header_left_p = Paragraph(
            f"<b>CÔNG TY CỔ PHẦN THỦY ĐIỆN VĨNH SƠN - SÔNG HINH</b><br/>"
            f"<font color='#334151'><b>{plant_display}</b></font><br/>"
            f"<font color='#64748B'><i>Phân xưởng Vận hành</i></font>",
            pdf_header_left_style,
        )
        header_right_p = Paragraph(
            "<b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b><br/>"
            "<font color='#334151'><b>Độc lập - Tự do - Hạnh phúc</b></font><br/>"
            "<font color='#94A3B8'>—————————</font>",
            pdf_header_right_style,
        )
        avail_width = landscape(A4)[0] - document.leftMargin - document.rightMargin
        admin_header_table = Table([[header_left_p, header_right_p]], colWidths=[avail_width / 2, avail_width / 2])
        admin_header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        body_style = ParagraphStyle(
            "RosterBody", parent=styles["BodyText"], fontName=font_name,
            fontSize=7.5, leading=10, alignment=1,
        )
        note_style = ParagraphStyle(
            "ScheduleNote", parent=styles["BodyText"], fontName=font_name,
            fontSize=9, leading=13, borderColor=colors.HexColor("#C7D2FE"),
            borderWidth=0.5, borderPadding=7, backColor=colors.HexColor("#EEF2FF"),
        )

        days = list(schedule.danh_sach_ngay.all())
        custom_staff = custom_schedule_staff_labels(days) if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE else {}
        handover_summaries = [_handover_summary(day) for day in days]
        day_label, night_label = _shift_time_labels(schedule)
        data = [
            ["Thứ"] + ["CN" if day.ngay.weekday() == 6 else str(day.ngay.weekday() + 2) for day in days],
            ["Ngày DL"] + [str(day.ngay.day) for day in days],
            [day_label.replace("-", "–")] + [day.hien_thi_ca_ngay for day in days],
            [night_label.replace("-", "–")] + [day.kip_ca_dem.ma_kip for day in days],
            ["Ca KT–HC"] + [day.hien_thi_ca_hanh_chinh for day in days],
            ["Vào làm việc"] + [summary[0] for summary in handover_summaries],
            ["Nghỉ ca"] + [summary[1] for summary in handover_summaries],
        ]
        if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE:
            data.insert(2, ["Ngày ÂL"] + [f"{day.ngay_am}/{day.thang_am}" if day.ngay_am else "" for day in days])
            for index, row in enumerate(data):
                period = {day_label.replace("-", "–"): "ca_ngay", night_label.replace("-", "–"): "ca_dem", "Ca KT–HC": "hanh_chinh"}.get(row[0])
                if period:
                    data[index] = [row[0]] + [
                        Paragraph("<br/>".join(escape(name) for name in _custom_staff_value(day, period, custom_staff).splitlines()), body_style)
                        for day in days
                    ]
        header_row_count = 3 if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE else 2
        schedule_table = Table(data, repeatRows=header_row_count, colWidths=[62] + [22] * len(days))
        commands = [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 6.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, header_row_count - 1), colors.HexColor("#F3F4F6")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2FF")),
        ]
        for column, day in enumerate(days, start=1):
            shift_offset = 1 if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE else 0
            if day.la_ngay_chuyen_kip and day.la_ngay_chuyen_ca_hc:
                commands.extend([
                    ("BACKGROUND", (column, 0), (column, header_row_count - 1), colors.HexColor("#FEF9C3")),
                    ("TEXTCOLOR", (column, 0), (column, header_row_count - 1), colors.HexColor("#A16207")),
                ])
            if day.la_ngay_chuyen_kip or day.la_ngay_chuyen_ca_hc:
                commands.extend([
                    ("BACKGROUND", (column, 5 + shift_offset), (column, 6 + shift_offset), colors.HexColor("#E0E7FF")),
                    ("TEXTCOLOR", (column, 5 + shift_offset), (column, 6 + shift_offset), colors.HexColor("#3730A3")),
                ])
            if day.la_ngay_chuyen_kip:
                commands.extend([
                    ("BACKGROUND", (column, 2 + shift_offset), (column, 3 + shift_offset), colors.HexColor("#E0E7FF")),
                    ("TEXTCOLOR", (column, 2 + shift_offset), (column, 3 + shift_offset), colors.HexColor("#3730A3")),
                ])
            if day.la_ngay_chuyen_ca_hc:
                commands.extend([
                    ("BACKGROUND", (column, 4 + shift_offset), (column, 4 + shift_offset), colors.HexColor("#E0E7FF")),
                    ("TEXTCOLOR", (column, 4 + shift_offset), (column, 4 + shift_offset), colors.HexColor("#3730A3")),
                ])
        schedule_table.setStyle(TableStyle(commands))

        export_teams, snapshot, role_rows = _export_roster(schedule)
        team_codes = [team.ma_kip for team in export_teams]
        roster_data = [["Chức danh"] + [_export_team_label(team) for team in export_teams]]
        for role, label in role_rows:
            row = [label]
            for code in team_codes:
                names = [
                    escape(str(member.get("ho_ten") or ""))
                    for member in snapshot.get(code, [])
                    if member.get("vai_tro") == role and member.get("ho_ten")
                ]
                row.append(Paragraph("<br/>".join(names) if names else "—", body_style))
            roster_data.append(row)
        available_roster_width = landscape(A4)[0] - document.leftMargin - document.rightMargin - 75
        roster_column_width = available_roster_width / max(len(export_teams), 1)
        roster_table = Table(roster_data, colWidths=[75] + [roster_column_width] * len(export_teams), repeatRows=1)
        roster_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E7FF")),
            ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F3F4F6")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        adjustments = list(DieuChinhNhanSuCaTruc.objects.filter(
            ngay_truc__lich_truc=schedule,
            trang_thai=DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET,
        ).select_related("ngay_truc", "ngay_truc_doi", "nhan_su_vang", "nhan_su_thay"))
        adjustment_table = None
        if adjustments:
            adjustment_data = [["Ngày", "Ca", "Hình thức", "Người vắng", "Người thay", "Ca đối ứng", "Vai trò", "Lý do"]]
            for item in adjustments:
                adjustment_data.append([
                    item.ngay_truc.ngay.strftime("%d/%m/%Y"), item.get_loai_ca_display(), item.get_loai_dieu_chinh_display(),
                    item.nhan_su_vang.ho_ten if item.nhan_su_vang_id else "—", item.nhan_su_thay.ho_ten if item.nhan_su_thay_id else "—",
                    f"{item.ngay_truc_doi.ngay:%d/%m/%Y} · {item.get_loai_ca_doi_display()}" if item.ngay_truc_doi_id else "—",
                    item.get_vai_tro_thay_display() if item.vai_tro_thay else "—", item.ly_do,
                ] )
            adjustment_table = Table(adjustment_data, colWidths=[60, 72, 64, 90, 90, 104, 75, 170], repeatRows=1)
            adjustment_table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font_name), ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0E7FF")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))

        if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE:
            pdf_title = f"{schedule.ten_lich.upper()} - THÁNG {schedule.thang:02d}/{schedule.nam} - {plant_display}"
        else:
            pdf_title = f"LỊCH TRỰC CA THÁNG {schedule.thang:02d} NĂM {schedule.nam} - {plant_display}"

        story = [
            admin_header_table,
            Spacer(1, 6),
            Paragraph(escape(pdf_title), styles["Title"]),
            Spacer(1, 6),
            schedule_table,
        ]
        if schedule.loai_lich != LichTrucCa.LoaiLich.CHUYEN_DE:
            story.extend([Spacer(1, 14), KeepTogether([
                Paragraph("DANH SÁCH NHÂN SỰ CA TRỰC", styles["Heading3"]),
                Spacer(1, 5), roster_table,
            ])])
        if adjustment_table:
            story.extend([Spacer(1, 14), Paragraph("ĐIỀU CHỈNH NHÂN SỰ ĐÃ DUYỆT", styles["Heading3"]), Spacer(1, 5), adjustment_table])
        note = escape(schedule.ghi_chu.strip()) if schedule.ghi_chu.strip() else "Chưa có ghi chú."
        story.extend([
            Spacer(1, 14),
            Paragraph(f"<b>Ghi chú lịch:</b> {note}", note_style),
        ])
        document.build(story)
        response = HttpResponse(output.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="lich-truc-thang-{schedule.thang:02d}-{schedule.nam}.pdf"'
        return response

    @action(detail=True, methods=["get"], url_path="xuat-excel-danh-sach-ngay")
    def xuat_excel_danh_sach_ngay(self, request, pk=None):
        schedule = self.get_object()
        self._ensure_exportable(schedule)

        tu_ngay_str = request.query_params.get("tu_ngay")
        den_ngay_str = request.query_params.get("den_ngay")

        schedule_days = list(schedule.danh_sach_ngay.all().order_by("ngay"))
        if not schedule_days:
            raise ValidationError("Lịch trực chưa có danh sách ngày.")

        first_schedule_date = schedule_days[0].ngay
        last_schedule_date = schedule_days[-1].ngay

        def parse_query_date(value, field_name, default):
            if not value:
                return default
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError as error:
                raise ValidationError({
                    field_name: "Ngày phải đúng định dạng YYYY-MM-DD.",
                }) from error

        tu_ngay = parse_query_date(tu_ngay_str, "tu_ngay", first_schedule_date)
        den_ngay = parse_query_date(
            den_ngay_str,
            "den_ngay",
            min(tu_ngay + timedelta(days=2), last_schedule_date),
        )

        if tu_ngay > den_ngay:
            raise ValidationError({
                "den_ngay": "Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.",
            })
        if tu_ngay < first_schedule_date or den_ngay > last_schedule_date:
            raise ValidationError({
                "detail": (
                    "Khoảng ngày phải nằm trong lịch từ "
                    f"{first_schedule_date:%d/%m/%Y} đến {last_schedule_date:%d/%m/%Y}."
                ),
            })

        selected_days = [d for d in schedule_days if tu_ngay <= d.ngay <= den_ngay]
        if not selected_days:
            raise ValidationError("Không tìm thấy ngày trực trong khoảng đã chọn.")

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet_title = f"DS ca {tu_ngay.day:02d}.{tu_ngay.month:02d}-{den_ngay.day:02d}.{den_ngay.month:02d}"
        sheet = workbook.add_worksheet(sheet_title[:31])

        # Style formats
        company_header = workbook.add_format({"bold": True, "align": "center", "font_size": 9.5, "font_color": "#1E3A8A"})
        plant_header = workbook.add_format({"bold": True, "align": "center", "font_size": 9.5, "font_color": "#334151"})
        dept_header = workbook.add_format({"italic": True, "align": "center", "font_size": 9, "font_color": "#64748B"})
        country_header = workbook.add_format({"bold": True, "align": "center", "font_size": 9.5, "font_color": "#0F172A"})
        motto_header = workbook.add_format({"bold": True, "align": "center", "font_size": 9.5, "font_color": "#334151"})
        line_header = workbook.add_format({"align": "center", "font_size": 9, "font_color": "#94A3B8"})

        title_format = workbook.add_format({"bold": True, "align": "center", "font_size": 13, "font_color": "#1E3A8A"})
        table_header = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#F1F5F9", "font_color": "#0F172A", "font_size": 10.5})
        date_header_format = workbook.add_format({"bold": True, "italic": True, "align": "left", "valign": "vcenter", "border": 1, "bg_color": "#F8FAFC", "font_color": "#0F172A", "font_size": 10.5, "indent": 1})
        area_format = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1, "text_wrap": True, "font_size": 10.5})
        shift_cell = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1, "font_size": 9.5})
        staff_cell = workbook.add_format({"align": "left", "valign": "vcenter", "border": 1, "text_wrap": True, "font_size": 9.5, "indent": 1})

        # Summary table formats
        summary_title_format = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#E0E7FF", "font_color": "#1E3A8A", "font_size": 11})
        summary_stt_cell = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1, "font_size": 9.5})
        summary_name_cell = workbook.add_format({"align": "left", "valign": "vcenter", "border": 1, "font_size": 9.5, "indent": 1})
        summary_shifts_cell = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1, "font_size": 9.5})
        summary_hours_cell = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#F8FAFC", "font_color": "#1E3A8A", "font_size": 10})
        summary_total_label = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#E2E8F0", "font_size": 10})
        summary_total_val = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#E2E8F0", "font_color": "#1E3A8A", "font_size": 10.5})

        # Plant names
        plant_raw = schedule.nha_may.ten_nha_may.strip() if schedule.nha_may else "Sông Hinh"
        plant_display = plant_raw.upper() if plant_raw.upper().startswith("NHÀ MÁY") else f"NHÀ MÁY THỦY ĐIỆN {plant_raw.upper()}"

        if plant_raw.upper().startswith("NMTĐ"):
            plant_area = plant_raw
        elif plant_raw.lower().startswith("nhà máy thủy điện"):
            plant_area = f"NMTĐ {plant_raw[17:].strip()}"
        elif plant_raw.lower().startswith("thủy điện"):
            plant_area = f"NMTĐ {plant_raw[9:].strip()}"
        else:
            plant_area = f"NMTĐ {plant_raw}"

        plant_code = (schedule.nha_may.ma_nha_may or "").strip().upper() if schedule.nha_may else ""
        plant_name_lower = plant_raw.lower()
        is_vinh_son = (plant_code == "VS" or "vĩnh sơn" in plant_name_lower)

        if is_vinh_son:
            night_end_label = "00h00'-07h00'"
            day_full_label = "07h00'-19h00'"
            day_morning_label = "07h00'-11h00'"
            day_afternoon_label = "11h00'-19h00'"
            night_start_label = "19h00'-24h00'"
            hc_full_label = "Ca KT-HC"
            hc_morning_label = "Ca KT-HC (07h30'-11h30')"
            hc_afternoon_label = "Ca KT-HC (11h30'-16h30')"
        else:
            night_end_label = "00h00'-08h00'"
            day_full_label = "08h00'-20h00'"
            day_morning_label = "08h00'-12h00'"
            day_afternoon_label = "12h00'-20h00'"
            night_start_label = "20h00'-24h00'"
            hc_full_label = "Ca KT-HC"
            hc_morning_label = "Ca KT-HC (08h00'-12h00')"
            hc_afternoon_label = "Ca KT-HC (12h00'-17h00')"

        def _get_shift_hours(label):
            if "00h00'-07h00'" in label: return 7.0
            if "00h00'-08h00'" in label: return 8.0
            if "07h00'-19h00'" in label or "08h00'-20h00'" in label: return 12.0
            if "07h00'-11h00'" in label or "08h00'-12h00'" in label: return 4.0
            if "11h00'-19h00'" in label or "12h00'-20h00'" in label: return 8.0
            if "19h00'-24h00'" in label: return 5.0
            if "20h00'-24h00'" in label: return 4.0
            if "Ca KT-HC (08h00'-12h00')" in label or "Ca KT-HC (07h30'-11h30')" in label: return 4.0
            if "Ca KT-HC (12h00'-17h00')" in label or "Ca KT-HC (11h30'-16h30')" in label: return 4.0
            if "Ca KT-HC" in label: return 8.0
            return 8.0

        # Left Header (Col 0 and Col 1)
        sheet.merge_range(0, 0, 0, 1, "CÔNG TY CỔ PHẦN THỦY ĐIỆN VĨNH SƠN - SÔNG HINH", company_header)
        sheet.merge_range(1, 0, 1, 1, plant_display, plant_header)
        sheet.merge_range(2, 0, 2, 1, "Phân xưởng Vận hành", dept_header)

        # Right Header (Col 2)
        sheet.write(0, 2, "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", country_header)
        sheet.write(1, 2, "Độc lập - Tự do - Hạnh phúc", motto_header)
        sheet.write(2, 2, "—————————", line_header)

        # Main Title (Row 4)
        main_title = f"DANH SÁCH CA TRỰC TỪ NGÀY {tu_ngay.strftime('%d/%m/%Y')} ĐẾN NGÀY {den_ngay.strftime('%d/%m/%Y')}"
        sheet.merge_range(4, 0, 4, 2, main_title, title_format)

        # Summary Table Title (Row 4, Col 4 to 7)
        sheet.merge_range(4, 4, 4, 7, "TỔNG HỢP SỐ GIỜ LÀM VIỆC", summary_title_format)

        # Table Header (Row 6)
        sheet.write(6, 0, "Khu vực", table_header)
        sheet.write(6, 1, "Ca trực", table_header)
        sheet.write(6, 2, "Họ và tên", table_header)

        # Summary Table Headers (Row 6, Col 4 to 7)
        sheet.write(6, 4, "STT", table_header)
        sheet.write(6, 5, "Họ và tên", table_header)
        sheet.write(6, 6, "Số ca", table_header)
        sheet.write(6, 7, "Tổng giờ (h)", table_header)
        sheet.set_row(6, 26)

        def _format_member_names(members):
            names = [m.get("ho_ten") for m in members if m.get("ho_ten")]
            return ", ".join(names) if names else "—"

        def _get_hc_prev_staff(d):
            if d.kip_hanh_chinh_truoc:
                p_date = d.ngay - timedelta(days=1)
                p_day = NgayTrucCa.objects.filter(lich_truc=schedule, ngay=p_date).first()
                if not p_day and schedule.loai_lich == LichTrucCa.LoaiLich.THANG:
                    p_day = NgayTrucCa.objects.filter(
                        lich_truc__nha_may=schedule.nha_may,
                        lich_truc__nhom_lich_id=schedule.nhom_lich_id,
                        lich_truc__loai_lich=LichTrucCa.LoaiLich.THANG,
                        lich_truc__trang_thai__in={
                            LichTrucCa.TrangThai.DA_DUYET,
                            LichTrucCa.TrangThai.DANG_AP_DUNG,
                            LichTrucCa.TrangThai.DA_KHOA,
                        },
                        ngay=p_date,
                    ).order_by("-lich_truc__phien_ban").first()
                if p_day and p_day.kip_hanh_chinh_id == d.kip_hanh_chinh_truoc_id:
                    return actual_shift_staff(p_day, DieuChinhNhanSuCaTruc.LoaiCa.HANH_CHINH)
                s_snap = schedule.snapshot_nhan_su or {}
                t_code = d.kip_hanh_chinh_truoc.ma_kip
                s_members = s_snap.get(t_code) or s_snap.get(f"HC{t_code}")
                if s_members:
                    return s_members
                m_ships = ThanhVienKipTruc.objects.filter(
                    kip_truc=d.kip_hanh_chinh_truoc,
                    dang_hoat_dong=True,
                    tu_ngay__lte=d.ngay,
                ).filter(Q(den_ngay__isnull=True) | Q(den_ngay__gte=d.ngay)).select_related("nhan_su", "user", "user__profile")
                return [
                    {"ho_ten": m.nhan_su.ho_ten if m.nhan_su_id else (m.user.get_full_name() or m.user.username)}
                    for m in m_ships
                ]
            return []

        person_stats = {}
        current_row = 7

        for day in selected_days:
            # Date separator row
            weekday_num = day.ngay.weekday()
            thu_str = "Chủ nhật" if weekday_num == 6 else f"Thứ {weekday_num + 2}"
            date_header_text = f"Ngày {day.ngay.day:02d}/{day.ngay.month}/{day.ngay.year} - ({thu_str})"
            sheet.merge_range(current_row, 0, current_row, 2, date_header_text, date_header_format)
            sheet.set_row(current_row, 22)
            current_row += 1

            # Get shift 1 (night shift from previous day ending in this morning)
            prev_date = day.ngay - timedelta(days=1)
            prev_day = NgayTrucCa.objects.filter(lich_truc=schedule, ngay=prev_date).first()
            if not prev_day and schedule.loai_lich == LichTrucCa.LoaiLich.THANG:
                prev_day = NgayTrucCa.objects.filter(
                    lich_truc__nha_may=schedule.nha_may,
                    lich_truc__nhom_lich_id=schedule.nhom_lich_id,
                    lich_truc__loai_lich=LichTrucCa.LoaiLich.THANG,
                    lich_truc__trang_thai__in={
                        LichTrucCa.TrangThai.DA_DUYET,
                        LichTrucCa.TrangThai.DANG_AP_DUNG,
                        LichTrucCa.TrangThai.DA_KHOA,
                    },
                    ngay=prev_date,
                ).order_by("-lich_truc__phien_ban").first()

            staff_shift_1 = actual_shift_staff(prev_day, DieuChinhNhanSuCaTruc.LoaiCa.CA_DEM) if prev_day else actual_shift_staff(day, DieuChinhNhanSuCaTruc.LoaiCa.CA_DEM)
            staff_shift_2 = actual_shift_staff(day, DieuChinhNhanSuCaTruc.LoaiCa.CA_NGAY)
            staff_shift_3 = actual_shift_staff(day, DieuChinhNhanSuCaTruc.LoaiCa.CA_DEM)
            staff_shift_hc = actual_shift_staff(day, DieuChinhNhanSuCaTruc.LoaiCa.HANH_CHINH)

            # Build list of shifts for this day
            shifts_for_day = []

            # 1. Ca đêm chuyển tiếp sang sáng
            shifts_for_day.append((night_end_label, staff_shift_1))

            # 2. Ca ngày (nếu ngày chuyển kíp thì chia 2 ca sáng / chiều)
            if day.la_ngay_chuyen_kip:
                shifts_for_day.append((day_morning_label, staff_shift_3))
                shifts_for_day.append((day_afternoon_label, staff_shift_2))
            else:
                shifts_for_day.append((day_full_label, staff_shift_2))

            # 3. Ca đêm bắt đầu từ tối nay
            shifts_for_day.append((night_start_label, staff_shift_3))

            # 4. Ca KT-HC (nếu ngày chuyển ca KT-HC thì chia 2 ca giao / nhận)
            if day.la_ngay_chuyen_ca_hc and day.kip_hanh_chinh_truoc:
                staff_hc_prev = _get_hc_prev_staff(day)
                shifts_for_day.append((hc_morning_label, staff_hc_prev))
                shifts_for_day.append((hc_afternoon_label, staff_shift_hc))
            else:
                shifts_for_day.append((hc_full_label, staff_shift_hc))

            # Area merged across all shifts of the day
            sheet.merge_range(current_row, 0, current_row + len(shifts_for_day) - 1, 0, plant_area, area_format)

            for shift_label, shift_staff in shifts_for_day:
                sheet.write(current_row, 1, shift_label, shift_cell)
                sheet.write(current_row, 2, _format_member_names(shift_staff), staff_cell)
                sheet.set_row(current_row, 24)

                # Accumulate individual hours
                shift_hours = _get_shift_hours(shift_label)
                for member in shift_staff:
                    name = member.get("ho_ten")
                    if name:
                        if name not in person_stats:
                            person_stats[name] = {"hours": 0.0, "shift_count": 0}
                        person_stats[name]["hours"] += shift_hours
                        person_stats[name]["shift_count"] += 1

                current_row += 1

        # Render Summary Table (Cols 4 to 7)
        sorted_stats = sorted(person_stats.items(), key=lambda x: (-x[1]["hours"], x[0]))
        summary_row = 7
        total_shifts_all = 0
        total_hours_all = 0.0

        for idx, (p_name, p_data) in enumerate(sorted_stats, start=1):
            sheet.write(summary_row, 4, idx, summary_stt_cell)
            sheet.write(summary_row, 5, p_name, summary_name_cell)
            sheet.write(summary_row, 6, p_data["shift_count"], summary_shifts_cell)

            hours_val = int(p_data["hours"]) if p_data["hours"].is_integer() else p_data["hours"]
            sheet.write(summary_row, 7, hours_val, summary_hours_cell)
            sheet.set_row(summary_row, 24)

            total_shifts_all += p_data["shift_count"]
            total_hours_all += p_data["hours"]
            summary_row += 1

        # Total row in summary table
        sheet.merge_range(summary_row, 4, summary_row, 5, "TỔNG CỘNG", summary_total_label)
        sheet.write(summary_row, 6, total_shifts_all, summary_total_val)
        final_hours = int(total_hours_all) if total_hours_all.is_integer() else total_hours_all
        sheet.write(summary_row, 7, final_hours, summary_total_val)
        sheet.set_row(summary_row, 25)
        summary_row += 1

        # Set column widths
        sheet.set_column(0, 0, 16)
        sheet.set_column(1, 1, 25)
        sheet.set_column(2, 2, 40)
        sheet.set_column(3, 3, 3)  # Separator column
        sheet.set_column(4, 4, 6)  # STT
        sheet.set_column(5, 5, 27) # Họ và tên
        sheet.set_column(6, 6, 10) # Số ca
        sheet.set_column(7, 7, 15) # Tổng giờ

        max_sheet_row = max(current_row, summary_row)
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)
        sheet.set_margins(left=0.3, right=0.3, top=0.4, bottom=0.4)
        sheet.print_area(0, 0, max_sheet_row - 1, 7)

        workbook.close()
        response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="danh-sach-ca-truc-{tu_ngay.strftime("%d%m%Y")}-{den_ngay.strftime("%d%m%Y")}.xlsx"'
        return response
