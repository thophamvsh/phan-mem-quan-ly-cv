import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied
from django.db import transaction
from rest_framework.exceptions import ValidationError as DRFValidationError

from django.utils import timezone
from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory, get_user_factory
from nhatkyvanhanh.models import MauChuyenDoiTBThang, SoChuyenDoiTBThang, ChiTietChuyenDoiTBThang
from nhatkyvanhanh.serializers import (
    MauChuyenDoiTBThangSerializer,
    SoChuyenDoiTBThangSerializer,
    ChiTietChuyenDoiTBThangSerializer,
)
from nhatkyvanhanh.permissions import (
    CanViewMonthlyEquipmentSwitchTemplates,
    CanCreateMonthlyEquipmentSwitchTemplates,
    CanEditMonthlyEquipmentSwitchTemplates,
    CanDeleteMonthlyEquipmentSwitchTemplates,
    CanViewMonthlyEquipmentSwitchLogs,
    CanCreateMonthlyEquipmentSwitchLogs,
    CanEditMonthlyEquipmentSwitchLogs,
    CanDeleteMonthlyEquipmentSwitchLogs,
)
from .helpers import (
    _get_song_hinh_factory,
    _create_default_monthly_switch_templates,
    _previous_month_values_by_device,
    _monthly_switch_log_locked,
    _can_confirm_monthly_equipment_switch_log,
    _can_unlock_monthly_equipment_switch_log,
    _can_edit_monthly_equipment_switch_log,
    _can_delete_monthly_equipment_switch_log,
)


class MauChuyenDoiTBThangFilterSet(django_filters.FilterSet):
    class Meta:
        model = MauChuyenDoiTBThang
        fields = ["nha_may", "ma_nhom", "dang_su_dung", "thiet_bi"]


class MauChuyenDoiTBThangViewSet(viewsets.ModelViewSet):
    serializer_class = MauChuyenDoiTBThangSerializer
    pagination_class = None
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MauChuyenDoiTBThangFilterSet
    search_fields = [
        "ma_nhom",
        "ten_nhom",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["thu_tu_nhom", "thu_tu", "created_at", "updated_at"]
    ordering = ["thu_tu_nhom", "thu_tu", "created_at"]

    def get_permissions(self):
        permission_classes = [CanViewMonthlyEquipmentSwitchTemplates]
        if self.action == "create":
            permission_classes = [CanCreateMonthlyEquipmentSwitchTemplates]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [CanEditMonthlyEquipmentSwitchTemplates]
        elif self.action == "destroy":
            permission_classes = [CanDeleteMonthlyEquipmentSwitchTemplates]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = MauChuyenDoiTBThang.objects.select_related(
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


class SoChuyenDoiTBThangFilterSet(django_filters.FilterSet):
    thang_tu = django_filters.NumberFilter(field_name="thang", lookup_expr="gte")
    thang_den = django_filters.NumberFilter(field_name="thang", lookup_expr="lte")
    ngay_tu = django_filters.DateFilter(field_name="thang_ket_thuc", lookup_expr="gte")
    ngay_den = django_filters.DateFilter(field_name="thang_bat_dau", lookup_expr="lte")

    class Meta:
        model = SoChuyenDoiTBThang
        fields = ["nha_may", "nam", "thang", "ca_truc", "thang_tu", "thang_den", "ngay_tu", "ngay_den", "nguoi_tao", "trang_thai"]


class SoChuyenDoiTBThangViewSet(viewsets.ModelViewSet):
    serializer_class = SoChuyenDoiTBThangSerializer
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoChuyenDoiTBThangFilterSet
    search_fields = [
        "nguoi_tao__email",
        "nguoi_tao__username",
        "ca_truc",
        "chi_tiets__ghi_chu",
        "chi_tiets__ten_nhom",
        "chi_tiets__thiet_bi__ten",
        "chi_tiets__thiet_bi__ma_day_du",
    ]
    ordering_fields = ["nam", "thang", "thang_bat_dau", "created_at", "updated_at"]
    ordering = ["-nam", "-thang", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewMonthlyEquipmentSwitchLogs]
        if self.action == "create":
            permission_classes = [CanCreateMonthlyEquipmentSwitchLogs]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [CanEditMonthlyEquipmentSwitchLogs]
        elif self.action == "destroy":
            permission_classes = [CanDeleteMonthlyEquipmentSwitchLogs]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = (
            SoChuyenDoiTBThang.objects.select_related(
                "nha_may",
                "nguoi_tao",
                "nguoi_duyet",
            )
            .prefetch_related(
                "chi_tiets",
                "chi_tiets__thiet_bi",
            )
            .all()
            .distinct()
        )
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def _create_details_from_templates(self, so):
        target_nha_may = so.nha_may or _get_song_hinh_factory()
        templates = list(
            MauChuyenDoiTBThang.objects.select_related("thiet_bi")
            .filter(dang_su_dung=True)
            .filter(nha_may=target_nha_may)
            .order_by("thu_tu_nhom", "thu_tu", "created_at")
        )
        if not templates:
            _create_default_monthly_switch_templates(target_nha_may)
            templates = list(
                MauChuyenDoiTBThang.objects.select_related("thiet_bi")
                .filter(dang_su_dung=True)
                .filter(nha_may=target_nha_may)
                .order_by("thu_tu_nhom", "thu_tu", "created_at")
            )
        if not templates:
            return False

        previous_values = _previous_month_values_by_device(so)
        existing_ids = set(so.chi_tiets.values_list("thiet_bi_id", flat=True))
        ChiTietChuyenDoiTBThang.objects.bulk_create(
            [
                ChiTietChuyenDoiTBThang(
                    so=so,
                    thiet_bi=template.thiet_bi,
                    ma_nhom=template.ma_nhom,
                    ten_nhom=template.ten_nhom,
                    don_vi_nhom=template.don_vi_nhom,
                    don_vi=template.don_vi,
                    dau_thang=previous_values.get(template.thiet_bi_id, 0),
                    cuoi_thang=previous_values.get(template.thiet_bi_id, 0),
                    thu_tu_nhom=template.thu_tu_nhom,
                    thu_tu=template.thu_tu,
                )
                for template in templates
                if template.thiet_bi_id not in existing_ids
            ]
        )
        return True

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
        factory_data = apply_request_factory_to_serializer(request.user, serializer, "nha_may", "fk")
        if not factory_data.get("nha_may") and not serializer.validated_data.get("nha_may"):
            factory_data["nha_may"] = _get_song_hinh_factory()

        with transaction.atomic():
            so = serializer.save(nguoi_tao=request.user, **factory_data)
            details_created = self._create_details_from_templates(so)
            if not details_created:
                raise DRFValidationError(
                    {"detail": "Chua co mau chuyen doi TB thang cho nha may nay va khong tim thay thiet bi phu hop de tao mau mac dinh."}
                )

        response_serializer = self.get_serializer(self.get_queryset().get(pk=so.pk))
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        so = serializer.instance
        if _monthly_switch_log_locked(so) and not self.request.user.is_superuser:
            raise PermissionDenied("Sổ chuyển đổi TB tháng đã được duyệt và khóa, không thể chỉnh sửa.")
        if not _can_edit_monthly_equipment_switch_log(self.request.user, serializer.instance):
            raise PermissionDenied("Ban khong co quyen cap nhat so chuyen doi TB thang nay.")
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_destroy(self, instance):
        if _monthly_switch_log_locked(instance) and not self.request.user.is_superuser:
            raise PermissionDenied("Sổ chuyển đổi TB tháng đã được duyệt và khóa, không thể xóa.")
        if not _can_delete_monthly_equipment_switch_log(self.request.user, instance):
            raise PermissionDenied("Ban khong co quyen xoa so chuyen doi TB thang nay.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="xac-nhan")
    def xac_nhan(self, request, pk=None):
        so = self.get_object()
        if not _can_confirm_monthly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Bạn không có quyền ký duyệt sổ chuyển đổi thiết bị tháng này."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if so.nguoi_tao_id == request.user.id and not request.user.is_superuser:
            return Response(
                {"detail": "Người tạo sổ không được tự ký duyệt sổ của chính mình."},
                status=status.HTTP_403_FORBIDDEN,
            )
        ghi_chu = request.data.get("ghi_chu_duyet", "")
        so.trang_thai = SoChuyenDoiTBThang.TrangThai.DA_DUYET
        so.nguoi_duyet = request.user
        so.duyet_at = timezone.now()
        if ghi_chu:
            so.ghi_chu_duyet = ghi_chu
        so.dong_bo_chu_ky_tu_user(request.user)
        so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="huy-xac-nhan")
    def huy_xac_nhan(self, request, pk=None):
        so = self.get_object()
        if not _can_unlock_monthly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Bạn không có quyền mở khóa sổ chuyển đổi thiết bị tháng này."},
                status=status.HTTP_403_FORBIDDEN,
            )
        so.trang_thai = SoChuyenDoiTBThang.TrangThai.CHO_DUYET
        so.nguoi_duyet = None
        so.duyet_at = None
        so.chu_ky_nguoi_duyet = None
        so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="tao-chi-tiet")
    def tao_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if _monthly_switch_log_locked(so) and not request.user.is_superuser:
            return Response(
                {"detail": "Sổ chuyển đổi TB tháng đã được duyệt và khóa, không thể thêm chi tiết."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_edit_monthly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Ban khong co quyen them chi tiet chuyen doi TB thang."},
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            details_created = self._create_details_from_templates(so)
            if not details_created:
                return Response(
                    {"detail": "Chua co mau chuyen doi TB thang cho nha may nay va khong tim thay thiet bi phu hop de tao mau mac dinh."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"chi-tiet/(?P<chi_tiet_id>[^/.]+)",
    )
    def cap_nhat_chi_tiet(self, request, pk=None, chi_tiet_id=None):
        so = self.get_object()
        if _monthly_switch_log_locked(so) and not request.user.is_superuser:
            return Response(
                {"detail": "Sổ chuyển đổi TB tháng đã được duyệt và khóa, không thể cập nhật chi tiết."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_edit_monthly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Ban khong co quyen cap nhat chi tiet chuyen doi TB thang nay."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            chi_tiet = so.chi_tiets.get(pk=chi_tiet_id)
        except ChiTietChuyenDoiTBThang.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay chi tiet chuyen doi TB thang."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChiTietChuyenDoiTBThangSerializer(
            chi_tiet,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="dong-bo-dau-thang")
    def dong_bo_dau_thang(self, request, pk=None):
        so = self.get_object()
        if _monthly_switch_log_locked(so) and not request.user.is_superuser:
            return Response(
                {"detail": "Sổ chuyển đổi TB tháng đã được duyệt và khóa, không thể đồng bộ chỉ số."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_edit_monthly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Bạn không có quyền chỉnh sửa sổ chuyển đổi TB tháng này."},
                status=status.HTTP_403_FORBIDDEN,
            )
        previous_values = _previous_month_values_by_device(so)
        if not previous_values:
            return Response(
                {"detail": "Không tìm thấy dữ liệu sổ chuyển đổi tháng trước để đồng bộ.", "count": 0},
                status=status.HTTP_200_OK,
            )
        with transaction.atomic():
            for ct in so.chi_tiets.all():
                if ct.thiet_bi_id in previous_values:
                    new_dau = previous_values[ct.thiet_bi_id]
                    ct.dau_thang = new_dau
                    if ct.cuoi_thang < new_dau:
                        ct.cuoi_thang = new_dau
                    ct.thuc_hien = ct.cuoi_thang - ct.dau_thang
                    ct.save(update_fields=["dau_thang", "cuoi_thang", "thuc_hien"])

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_200_OK)
