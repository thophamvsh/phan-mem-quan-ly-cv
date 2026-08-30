import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied
from django.db import transaction

from django.utils import timezone

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory, get_user_factory
from nhatkyvanhanh.models import MauChuyenDoiThietBi, SoChuyenDoiThietBiTuan, LanChuyenDoiThietBi, ChiTietChuyenDoiThietBi
from nhatkyvanhanh.serializers import (
    MauChuyenDoiThietBiSerializer,
    SoChuyenDoiThietBiTuanSerializer,
    LanChuyenDoiThietBiSerializer,
)
from nhatkyvanhanh.permissions import (
    CanViewOperationLogbooks,
    CanCreateOperationLogbooks,
    CanViewWeeklyEquipmentSwitchLogs,
    CanCreateWeeklyEquipmentSwitchLogs,
    CanEditWeeklyEquipmentSwitchLogs,
    CanDeleteWeeklyEquipmentSwitchLogs,
    CanConfirmWeeklyEquipmentSwitchLogs,
    has_profile_permission,
)
from .helpers import (
    _weekly_switch_log_locked,
    _can_confirm_weekly_equipment_switch_log,
    _can_unlock_weekly_equipment_switch_log,
    _can_edit_weekly_equipment_switch_log,
    _can_delete_weekly_equipment_switch_log,
    _get_song_hinh_factory,
    _is_song_hinh_factory,
    _create_default_switch_templates,
    _get_previous_weekly_switch_log,
    _can_view_weekly_equipment_switch_template,
    _can_create_weekly_equipment_switch_template,
    _can_edit_weekly_equipment_switch_template,
    _can_delete_weekly_equipment_switch_template,
    _can_delete_weekly_equipment_switch_entry,
    _can_edit_weekly_equipment_switch_entry,
)


class MauChuyenDoiThietBiFilterSet(django_filters.FilterSet):
    class Meta:
        model = MauChuyenDoiThietBi
        fields = ["nha_may", "to_may", "dang_su_dung", "thiet_bi"]


class MauChuyenDoiThietBiViewSet(viewsets.ModelViewSet):
    serializer_class = MauChuyenDoiThietBiSerializer
    pagination_class = None
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MauChuyenDoiThietBiFilterSet
    search_fields = [
        "nhom_thiet_bi",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["to_may", "thu_tu", "created_at", "updated_at"]
    ordering = ["to_may", "thu_tu", "created_at"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        if not _can_view_weekly_equipment_switch_template(request.user):
            return Response(
                {"detail": "Bạn không có quyền xem mẫu chuyển đổi thiết bị tuần."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        if not _can_view_weekly_equipment_switch_template(request.user):
            return Response(
                {"detail": "Bạn không có quyền xem mẫu chuyển đổi thiết bị tuần."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        if not _can_create_weekly_equipment_switch_template(request.user):
            return Response(
                {"detail": "Bạn không có quyền thêm thiết bị vào mẫu chuyển đổi thiết bị tuần."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not _can_edit_weekly_equipment_switch_template(request.user):
            return Response(
                {"detail": "Bạn không có quyền sửa mẫu chuyển đổi thiết bị tuần."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        if not _can_edit_weekly_equipment_switch_template(request.user):
            return Response(
                {"detail": "Bạn không có quyền sửa mẫu chuyển đổi thiết bị tuần."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not _can_delete_weekly_equipment_switch_template(request.user):
            return Response(
                {"detail": "Bạn không có quyền xóa thiết bị khỏi mẫu chuyển đổi thiết bị tuần."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        from tochuc.models import NhaMay

        for factory in NhaMay.objects.all():
            if _is_song_hinh_factory(factory) or (factory.ma_nha_may and factory.ma_nha_may.upper() == "SH"):
                if MauChuyenDoiThietBi.objects.filter(nha_may=factory).count() < 22:
                    _create_default_switch_templates(factory)

        queryset = MauChuyenDoiThietBi.objects.select_related(
            "nha_may",
            "thiet_bi",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_update(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )


class SoChuyenDoiThietBiTuanFilterSet(django_filters.FilterSet):
    tuan_tu = django_filters.NumberFilter(field_name="tuan", lookup_expr="gte")
    tuan_den = django_filters.NumberFilter(field_name="tuan", lookup_expr="lte")
    ngay_tu = django_filters.DateFilter(field_name="tuan_ket_thuc", lookup_expr="gte")
    ngay_den = django_filters.DateFilter(field_name="tuan_bat_dau", lookup_expr="lte")

    class Meta:
        model = SoChuyenDoiThietBiTuan
        fields = ["nha_may", "nam", "tuan", "ca_truc", "tuan_tu", "tuan_den", "ngay_tu", "ngay_den", "nguoi_tao"]


class SoChuyenDoiThietBiTuanViewSet(viewsets.ModelViewSet):
    serializer_class = SoChuyenDoiThietBiTuanSerializer
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoChuyenDoiThietBiTuanFilterSet
    search_fields = [
        "nguoi_tao__email",
        "nguoi_tao__username",
        "ca_truc",
        "lan_chuyen_dois__ghi_chu_chung",
        "lan_chuyen_dois__chi_tiets__ghi_chu",
        "lan_chuyen_dois__chi_tiets__thiet_bi__ten",
        "lan_chuyen_dois__chi_tiets__thiet_bi__ma_day_du",
    ]
    ordering_fields = ["nam", "tuan", "tuan_bat_dau", "created_at", "updated_at"]
    ordering = ["-nam", "-tuan", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewWeeklyEquipmentSwitchLogs]
        if self.action == "create":
            permission_classes = [CanCreateWeeklyEquipmentSwitchLogs]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [CanEditWeeklyEquipmentSwitchLogs]
        elif self.action == "destroy":
            permission_classes = [CanDeleteWeeklyEquipmentSwitchLogs]
        elif self.action in ["xac_nhan", "duyet"]:
            permission_classes = [CanConfirmWeeklyEquipmentSwitchLogs]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = (
            SoChuyenDoiThietBiTuan.objects.select_related(
                "nha_may",
                "nguoi_tao",
                "nguoi_duyet",
            )
            .prefetch_related(
                "lan_chuyen_dois",
                "lan_chuyen_dois__nguoi_thuc_hien",
                "lan_chuyen_dois__chi_tiets",
                "lan_chuyen_dois__chi_tiets__thiet_bi",
            )
            .all()
            .distinct()
        )
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        if not data.get("nha_may"):
            user_factory = get_user_factory(request.user)
            if user_factory:
                data["nha_may"] = user_factory.id
            else:
                sh = _get_song_hinh_factory()
                if sh:
                    data["nha_may"] = sh.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        factory_data = apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        if not factory_data.get("nha_may") and not serializer.validated_data.get("nha_may"):
            factory_data["nha_may"] = _get_song_hinh_factory()
        serializer.save(
            nguoi_tao=self.request.user,
            **factory_data
        )

    def perform_update(self, serializer):
        if _weekly_switch_log_locked(serializer.instance) and not (self.request.user.is_superuser or has_profile_permission(self.request.user, "can_manage_all_weekly_equipment_switch_logs")):
            raise PermissionDenied("Sổ chuyển đổi thiết bị tuần đã được duyệt và khóa sổ, không thể chỉnh sửa.")
        if not _can_edit_weekly_equipment_switch_log(self.request.user, serializer.instance):
            raise PermissionDenied("Bạn không có quyền cập nhật sổ chuyển đổi thiết bị tuần này.")
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_destroy(self, instance):
        if _weekly_switch_log_locked(instance) and not (self.request.user.is_superuser or has_profile_permission(self.request.user, "can_manage_all_weekly_equipment_switch_logs")):
            raise PermissionDenied("Sổ chuyển đổi thiết bị tuần đã được duyệt và khóa sổ, không thể xóa.")
        if not _can_delete_weekly_equipment_switch_log(self.request.user, instance):
            raise PermissionDenied("Bạn không có quyền xóa sổ chuyển đổi thiết bị tuần này.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="xac-nhan")
    def xac_nhan(self, request, pk=None):
        so = self.get_object()
        if not _can_confirm_weekly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Bạn không có quyền duyệt / xác nhận sổ chuyển đổi thiết bị tuần."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if so.nguoi_tao_id == request.user.id and not (request.user.is_superuser or has_profile_permission(request.user, "can_manage_all_weekly_equipment_switch_logs")):
            return Response(
                {"detail": "Người tạo sổ không được tự ký duyệt sổ của chính mình."},
                status=status.HTTP_403_FORBIDDEN,
            )
        so.nguoi_duyet = request.user
        so.duyet_at = timezone.now()
        so.trang_thai = SoChuyenDoiThietBiTuan.TrangThai.DA_DUYET
        if "ghi_chu_duyet" in request.data:
            so.ghi_chu_duyet = str(request.data.get("ghi_chu_duyet") or "").strip()
        so.dong_bo_chu_ky_tu_user()
        so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="huy-xac-nhan")
    def huy_xac_nhan(self, request, pk=None):
        so = self.get_object()
        if not _can_unlock_weekly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Bạn không có quyền mở khóa / hủy duyệt sổ chuyển đổi thiết bị tuần này."},
                status=status.HTTP_403_FORBIDDEN,
            )
        so.nguoi_duyet = None
        so.duyet_at = None
        so.trang_thai = SoChuyenDoiThietBiTuan.TrangThai.CHO_DUYET
        so.chu_ky_nguoi_duyet = None
        so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="tao-lan-chuyen-doi")
    def tao_lan_chuyen_doi(self, request, pk=None):
        so = self.get_object()
        target_nha_may = so.nha_may or _get_song_hinh_factory()
        if _weekly_switch_log_locked(so) and not (request.user.is_superuser or has_profile_permission(request.user, "can_manage_all_weekly_equipment_switch_logs")):
            return Response(
                {"detail": "Sổ chuyển đổi thiết bị tuần đã được duyệt và khóa sổ, không thể tạo thêm lần chuyển đổi mới."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_edit_weekly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Bạn không có quyền thêm lần chuyển đổi thiết bị."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if so.lan_chuyen_dois.exists():
            return Response(
                {"detail": "Mỗi sổ tuần chỉ được tạo một lần chuyển đổi thiết bị."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LanChuyenDoiThietBiSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        templates = list(
            MauChuyenDoiThietBi.objects.select_related("thiet_bi")
            .filter(dang_su_dung=True)
            .filter(nha_may=target_nha_may)
            .order_by("to_may", "thu_tu", "created_at")
        )
        if not templates:
            _create_default_switch_templates(target_nha_may)
            templates = list(
                MauChuyenDoiThietBi.objects.select_related("thiet_bi")
                .filter(dang_su_dung=True)
                .filter(nha_may=target_nha_may)
                .order_by("to_may", "thu_tu", "created_at")
            )
        if not templates:
            return Response(
                {"detail": "Chua co mau chuyen doi thiet bi cho nha may nay va khong tim thay thiet bi phu hop de tao mau mac dinh."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prev_so = _get_previous_weekly_switch_log(so)
        prev_status_map = {}
        if prev_so:
            prev_lan = prev_so.lan_chuyen_dois.order_by("-thoi_gian", "-created_at").first()
            if prev_lan:
                prev_status_map = {
                    ct.thiet_bi_id: ct.trang_thai
                    for ct in prev_lan.chi_tiets.all()
                }

        with transaction.atomic():
            lan = serializer.save(so=so, nguoi_thuc_hien=request.user)
            ChiTietChuyenDoiThietBi.objects.bulk_create(
                [
                    ChiTietChuyenDoiThietBi(
                        lan_chuyen_doi=lan,
                        thiet_bi=template.thiet_bi,
                        to_may=template.to_may,
                        nhom_thiet_bi=template.nhom_thiet_bi,
                        thu_tu=template.thu_tu,
                        trang_thai=(
                            "du_phong"
                            if prev_status_map.get(template.thiet_bi_id) == "lam_viec"
                            else (
                                "lam_viec"
                                if prev_status_map.get(template.thiet_bi_id) == "du_phong"
                                else ""
                            )
                        ),
                    )
                    for template in templates
                ]
            )

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"lan-chuyen-doi/(?P<lan_id>[^/.]+)",
    )
    def cap_nhat_lan_chuyen_doi(self, request, pk=None, lan_id=None):
        so = self.get_object()
        try:
            lan = so.lan_chuyen_dois.get(pk=lan_id)
        except LanChuyenDoiThietBi.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay lan chuyen doi thiet bi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if _weekly_switch_log_locked(so) and not (request.user.is_superuser or has_profile_permission(request.user, "can_manage_all_weekly_equipment_switch_logs")):
            return Response(
                {"detail": "Sổ chuyển đổi thiết bị tuần đã được duyệt và khóa sổ, không thể chỉnh sửa hoặc xóa lần chuyển đổi."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            if not _can_delete_weekly_equipment_switch_entry(request.user, lan):
                return Response(
                    {"detail": "Bạn không có quyền xóa lần chuyển đổi thiết bị này."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            lan.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        if not _can_edit_weekly_equipment_switch_entry(request.user, lan):
            return Response(
                {"detail": "Bạn không có quyền cập nhật lần chuyển đổi thiết bị này."},
                status=status.HTTP_403_FORBIDDEN,
            )

        lan_serializer = LanChuyenDoiThietBiSerializer(
            lan,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        lan_serializer.is_valid(raise_exception=True)

        chi_tiets = request.data.get("chi_tiets", [])
        chi_tiet_map = {str(item.id): item for item in lan.chi_tiets.all()}
        allowed_statuses = {choice[0] for choice in ChiTietChuyenDoiThietBi.TrangThai.choices}
        for payload in chi_tiets:
            trang_thai_value = payload.get("trang_thai")
            if trang_thai_value and trang_thai_value not in allowed_statuses:
                return Response(
                    {"detail": f"Trang thai khong hop le: {trang_thai_value}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            lan_serializer.save()
            for payload in chi_tiets:
                chi_tiet = chi_tiet_map.get(str(payload.get("id")))
                if not chi_tiet:
                    continue
                trang_thai_value = payload.get("trang_thai", chi_tiet.trang_thai)
                chi_tiet.trang_thai = trang_thai_value or ""
                chi_tiet.ghi_chu = payload.get("ghi_chu", chi_tiet.ghi_chu)
                chi_tiet.save(update_fields=["trang_thai", "ghi_chu", "updated_at"])

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_200_OK)
