from django.utils import timezone
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from datetime import date, datetime, timedelta
from django.utils.dateparse import parse_datetime

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from quanlycatruc.models import LichTrucCa, NgayTrucCa
from quanlycatruc.permissions import can_access_plant
from quanlycatruc.services import actual_shift_staff
from nhatkyvanhanh.models import SogiaonhancaHC, ChiTietSoGiaoNhanCaHC, NguoiTrucSoGiaoNhanCaHC
from nhatkyvanhanh.serializers import (
    SogiaonhancaHCSerializer,
    ChiTietSoGiaoNhanCaHCSerializer,
    NguoiTrucSoGiaoNhanCaHCSerializer,
)
from nhatkyvanhanh.permissions import (
    CanViewAdminShiftHandoverLogs,
    CanCreateAdminShiftHandoverLogs,
    CanReceiveAdminShiftHandoverLogs,
    CanEditAdminShiftHandoverLogs,
    CanDeleteAdminShiftHandoverLogs,
    IsShiftLogCreator,
    IsNotShiftLogCreator,
)
from .helpers import (
    _dong_bo_chu_ky_so_giao_nhan,
    _shift_log_received,
    _is_creator_of_shift_log,
    _can_create_shift_detail,
    _can_update_shift_detail,
)


class SogiaonhancaHCFilterSet(django_filters.FilterSet):
    ngay_truc_tu = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="gte")
    ngay_truc_den = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="lte")

    class Meta:
        model = SogiaonhancaHC
        fields = [
            "nha_may",
            "trang_thai",
            "ngay_truc",
            "ngay_truc_tu",
            "ngay_truc_den",
            "user_giao_ca",
            "user_nhan_ca",
        ]


class SogiaonhancaHCViewSet(viewsets.ModelViewSet):
    serializer_class = SogiaonhancaHCSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SogiaonhancaHCFilterSet
    search_fields = [
        "dia_diem",
        "nguoi_truc",
        "nguoi_truc_2",
        "nguoi_truc_3",
        "nguoi_truc_chi_tiets__ten_nguoi_truc",
        "noi_dung_chi_tiets__tieu_de",
        "noi_dung_chi_tiets__noi_dung",
        "luu_y",
        "user_giao_ca__email",
        "user_giao_ca__username",
        "user_nhan_ca__email",
        "user_nhan_ca__username",
    ]
    ordering_fields = [
        "ngay_truc",
        "thoi_gian_bat_dau_ca",
        "thoi_gian_giao_ca",
        "created_at",
        "updated_at",
    ]
    ordering = ["-ngay_truc", "-thoi_gian_bat_dau_ca", "-thoi_gian_giao_ca", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewAdminShiftHandoverLogs]
        if self.action == "create":
            permission_classes = [CanCreateAdminShiftHandoverLogs]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [CanEditAdminShiftHandoverLogs]
        elif self.action == "destroy":
            permission_classes = [CanDeleteAdminShiftHandoverLogs]
        elif self.action == "ky_nhan_ca":
            permission_classes = [CanReceiveAdminShiftHandoverLogs, IsNotShiftLogCreator]
        elif self.action == "ky_giao_ca":
            permission_classes = [CanViewAdminShiftHandoverLogs, IsShiftLogCreator]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SogiaonhancaHC.objects.select_related(
            "nha_may",
            "user_giao_ca",
            "user_nhan_ca",
            "nguoi_tao",
        ).prefetch_related(
            "nguoi_truc_chi_tiets__nguoi_tao",
            "noi_dung_chi_tiets__nguoi_tao",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        factory_values = apply_request_factory_to_serializer(
            self.request.user, serializer, "nha_may", "fk"
        )
        nha_may = factory_values.get("nha_may") or serializer.validated_data.get("nha_may")
        ngay_truc = serializer.validated_data.get("ngay_truc")
        if nha_may and ngay_truc and SogiaonhancaHC.objects.filter(
            nha_may=nha_may, ngay_truc=ngay_truc
        ).exists():
            raise ValidationError(
                {"ngay_truc": ["Nhà máy đã có sổ giao nhận ca hành chính trong ngày này."]}
            )

        source_schedule = serializer.validated_data.get("lich_truc_nguon")
        source_day = serializer.validated_data.get("ngay_truc_ca_nguon")
        staff = actual_shift_staff(source_day, "hanh_chinh") if source_day else []
        creator_in_roster = (
            any(person.get("user_id") == self.request.user.id for person in staff)
            if source_day else None
        )
        try:
            so = serializer.save(
                user_giao_ca=self.request.user,
                nguoi_tao=self.request.user,
                phien_ban_lich_nguon=source_schedule.phien_ban if source_schedule else None,
                dong_bo_bien_che_at=timezone.now() if source_schedule else None,
                nguoi_tao_thuoc_bien_che=creator_in_roster,
                **factory_values,
            )
            _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
            so.save()
        except DjangoValidationError as exc:
            msg = (
                {"ngay_truc": ["Nhà máy đã có sổ giao nhận ca hành chính trong ngày này."]}
                if "already exists" in str(exc)
                else (exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            )
            raise ValidationError(msg)

    def perform_update(self, serializer):
        if _shift_log_received(serializer.instance):
            raise PermissionDenied("So giao nhan ca da duoc ky nhan, khong duoc chinh sua.")
        if not _is_creator_of_shift_log(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so giao nhan ca hanh chinh.")
        factory_values = apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        nha_may = factory_values.get("nha_may") or serializer.validated_data.get("nha_may", serializer.instance.nha_may)
        ngay_truc = serializer.validated_data.get("ngay_truc", serializer.instance.ngay_truc)
        if nha_may and ngay_truc and SogiaonhancaHC.objects.filter(
            nha_may=nha_may, ngay_truc=ngay_truc
        ).exclude(pk=serializer.instance.pk).exists():
            raise ValidationError(
                {"ngay_truc": ["Nhà máy đã có sổ giao nhận ca hành chính trong ngày này."]}
            )
        source_schedule = serializer.validated_data.get("lich_truc_nguon", serializer.instance.lich_truc_nguon)
        source_day = serializer.validated_data.get("ngay_truc_ca_nguon", serializer.instance.ngay_truc_ca_nguon)
        staff = actual_shift_staff(source_day, "hanh_chinh") if source_day else []
        creator_in_roster = (
            any(person.get("user_id") == serializer.instance.nguoi_tao_id for person in staff)
            if source_day else None
        )
        try:
            so = serializer.save(
                phien_ban_lich_nguon=source_schedule.phien_ban if source_schedule else None,
                dong_bo_bien_che_at=timezone.now() if source_schedule else serializer.instance.dong_bo_bien_che_at,
                nguoi_tao_thuoc_bien_che=creator_in_roster,
                **factory_values
            )
            _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
            so.save()
        except DjangoValidationError as exc:
            msg = (
                {"ngay_truc": ["Nhà máy đã có sổ giao nhận ca hành chính trong ngày này."]}
                if "already exists" in str(exc)
                else (exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            )
            raise ValidationError(msg)

    @action(detail=False, methods=["get"], url_path="bien-che-lich-truc")
    def bien_che_lich_truc(self, request):
        try:
            plant_id = int(request.query_params.get("nha_may", ""))
            shift_date = date.fromisoformat(request.query_params.get("ngay_truc", ""))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Nhà máy hoặc ngày trực không hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not can_access_plant(request.user, plant_id):
            raise PermissionDenied("Bạn không có quyền xem lịch trực của nhà máy này.")

        range_start = parse_datetime(request.query_params.get("thoi_gian_bat_dau", ""))
        range_end = parse_datetime(request.query_params.get("thoi_gian_ket_thuc", ""))
        if range_start and timezone.is_naive(range_start):
            range_start = timezone.make_aware(range_start)
        if range_end and timezone.is_naive(range_end):
            range_end = timezone.make_aware(range_end)
        if not range_start:
            range_start = timezone.make_aware(datetime.combine(shift_date, datetime.min.time()))
        if not range_end:
            range_end = range_start + timedelta(days=6)
        if range_end <= range_start:
            return Response(
                {"detail": "Thời gian kết thúc sổ phải sau thời gian bắt đầu."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        local_start = timezone.localtime(range_start)
        local_end = timezone.localtime(range_end)
        range_last_date = (local_end - timedelta(microseconds=1)).date()

        candidates = list(
            NgayTrucCa.objects.filter(
                lich_truc__nha_may_id=plant_id,
                lich_truc__trang_thai__in=[
                    LichTrucCa.TrangThai.DA_DUYET,
                    LichTrucCa.TrangThai.DANG_AP_DUNG,
                    LichTrucCa.TrangThai.DA_KHOA,
                ],
                ngay__range=(local_start.date(), range_last_date),
            ).select_related("lich_truc", "lich_truc__nhom_lich", "kip_hanh_chinh")
        )
        priority = {
            LichTrucCa.TrangThai.DANG_AP_DUNG: 3,
            LichTrucCa.TrangThai.DA_KHOA: 2,
            LichTrucCa.TrangThai.DA_DUYET: 1,
        }
        schedules = {}
        for day in candidates:
            schedules.setdefault(day.lich_truc_id, []).append(day)
        schedule_days = sorted(
            schedules.values(),
            key=lambda days: (
                priority.get(days[0].lich_truc.trang_thai, 0),
                days[0].lich_truc.phien_ban,
            ),
            reverse=True,
        )

        def boundary(day_value):
            value = datetime.combine(day_value, local_start.timetz().replace(tzinfo=None))
            return timezone.make_aware(value, timezone.get_current_timezone())

        options = []
        for days in schedule_days:
            days.sort(key=lambda item: item.ngay)
            segments = []
            active = {}
            for roster_day in days:
                current = {}
                for person in actual_shift_staff(roster_day, "hanh_chinh"):
                    key = (
                        f"n:{person.get('nhan_su_id')}" if person.get("nhan_su_id")
                        else f"u:{person.get('user_id')}" if person.get("user_id")
                        else f"t:{person.get('ho_ten', '').strip().casefold()}"
                    )
                    current[key] = person
                    previous = active.get(key)
                    if previous and previous["last_date"] + timedelta(days=1) == roster_day.ngay:
                        previous["last_date"] = roster_day.ngay
                    else:
                        if previous:
                            segments.append(previous)
                        active[key] = {
                            "person": person,
                            "start_date": roster_day.ngay,
                            "last_date": roster_day.ngay,
                        }
                for key in list(active):
                    if key not in current:
                        segments.append(active.pop(key))
            segments.extend(active.values())

            staff = []
            for segment in sorted(
                segments,
                key=lambda item: (item["start_date"], item["person"].get("ho_ten", "")),
            ):
                person_start = max(range_start, boundary(segment["start_date"]))
                person_end = min(range_end, boundary(segment["last_date"] + timedelta(days=1)))
                if person_end > person_start:
                    staff.append({
                        **segment["person"],
                        "thoi_gian_bat_dau": person_start.isoformat(),
                        "thoi_gian_ket_thuc": person_end.isoformat(),
                    })

            day = days[0]
            team_codes = list(dict.fromkeys(
                item.kip_hanh_chinh.ma_kip for item in days if item.kip_hanh_chinh_id
            ))
            options.append({
                "lich_truc_id": day.lich_truc_id,
                "ngay_truc_id": day.id,
                "phien_ban": day.lich_truc.phien_ban,
                "nhom_lich": day.lich_truc.nhom_lich_id,
                "nhom_lich_ten": (
                    day.lich_truc.nhom_lich.ten_nhom
                    if day.lich_truc.nhom_lich_id else "Lịch trực chung"
                ),
                "kip_hanh_chinh": ", ".join(team_codes) or "Không bố trí",
                "nhan_su": staff,
                "nguoi_tao_thuoc_bien_che": any(
                    person.get("user_id") == request.user.id for person in staff
                ),
            })
        if not options:
            return Response(
                {"detail": "Không tìm thấy lịch trực đã duyệt, đang áp dụng hoặc đã khóa cho ngày này."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"lua_chon": options})

    def perform_destroy(self, instance):
        if _shift_log_received(instance):
            raise PermissionDenied("So giao nhan ca da duoc ky nhan, khong duoc xoa.")
        if not _is_creator_of_shift_log(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so giao nhan ca hanh chinh.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def ky_giao_ca(self, request, pk=None):
        so = self.get_object()
        if not so.nhan_ca_ky_at:
            return Response(
                {"detail": "Can ky nhan ca truoc khi ky giao ca."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not so.giao_ca_ky_at:
            so.giao_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="noi-dung-chi-tiet")
    def tao_noi_dung_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if _shift_log_received(so):
            return Response(
                {"detail": "So giao nhan ca da duoc ky nhan, khong duoc them noi dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_create_shift_detail(request.user, so):
            return Response(
                {"detail": "Chi user giao ca moi duoc them noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ChiTietSoGiaoNhanCaHCSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"noi-dung-chi-tiet/(?P<chi_tiet_id>[^/.]+)",
    )
    def cap_nhat_noi_dung_chi_tiet(self, request, pk=None, chi_tiet_id=None):
        so = self.get_object()
        if _shift_log_received(so):
            return Response(
                {"detail": "So giao nhan ca da duoc ky nhan, khong duoc cap nhat noi dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            chi_tiet = so.noi_dung_chi_tiets.get(pk=chi_tiet_id)
        except ChiTietSoGiaoNhanCaHC.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay noi dung chi tiet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _can_update_shift_detail(request.user, so, chi_tiet):
            return Response(
                {"detail": "Chi user giao ca tao noi dung moi duoc cap nhat noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            chi_tiet.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = ChiTietSoGiaoNhanCaHCSerializer(
            chi_tiet,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="nguoi-truc-chi-tiet")
    def tao_nguoi_truc_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if _shift_log_received(so):
            return Response(
                {"detail": "So giao nhan ca da duoc ky nhan, khong duoc them nguoi truc."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _is_creator_of_shift_log(request.user, so):
            return Response(
                {"detail": "Chi user tao so moi duoc them nguoi truc."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = NguoiTrucSoGiaoNhanCaHCSerializer(
            data=request.data,
            context={**self.get_serializer_context(), "shift_log": so},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"nguoi-truc-chi-tiet/(?P<nguoi_truc_id>[^/.]+)",
    )
    def cap_nhat_nguoi_truc_chi_tiet(self, request, pk=None, nguoi_truc_id=None):
        so = self.get_object()
        if _shift_log_received(so):
            return Response(
                {"detail": "So giao nhan ca da duoc ky nhan, khong duoc cap nhat nguoi truc."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _is_creator_of_shift_log(request.user, so):
            return Response(
                {"detail": "Chi user tao so moi duoc cap nhat nguoi truc."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            nguoi_truc = so.nguoi_truc_chi_tiets.get(pk=nguoi_truc_id)
        except NguoiTrucSoGiaoNhanCaHC.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay nguoi truc."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "DELETE":
            nguoi_truc.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = NguoiTrucSoGiaoNhanCaHCSerializer(
            nguoi_truc,
            data=request.data,
            partial=True,
            context={**self.get_serializer_context(), "shift_log": so},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ky_nhan_ca(self, request, pk=None):
        so = self.get_object()
        if so.user_nhan_ca_id and so.user_nhan_ca_id != request.user.id:
            return Response(
                {"detail": "So da duoc gan user nhan ca khac."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not so.nhan_ca_ky_at:
            if not so.user_nhan_ca_id:
                so.user_nhan_ca = request.user
            so.nhan_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)
