from datetime import datetime
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied

from core.factory_scope import filter_queryset_by_factory
from thongsothuyvan.models import ThongsoSanxuat
from nhatkyvanhanh.models import SoBCHCSongHinh
from nhatkyvanhanh.serializers import SoBCHCSongHinhSerializer
from nhatkyvanhanh.permissions import CanViewBCHCSongHinh, CanCreateBCHCSongHinh, has_profile_permission
from .helpers import (
    _get_song_hinh_factory,
    _find_muc_nuoc_quy_trinh,
    _decimal_or_none,
    _format_decimal_range,
    _calculate_bchc_qt,
)


class SoBCHCSongHinhFilterSet(django_filters.FilterSet):
    ngay_tu = django_filters.DateFilter(field_name="ngay_dong_bo", lookup_expr="gte")
    ngay_den = django_filters.DateFilter(field_name="ngay_dong_bo", lookup_expr="lte")

    class Meta:
        model = SoBCHCSongHinh
        fields = ["ngay_dong_bo", "ngay_tu", "ngay_den", "nguoi_dong_bo"]


class SoBCHCSongHinhViewSet(viewsets.ModelViewSet):
    serializer_class = SoBCHCSongHinhSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoBCHCSongHinhFilterSet
    search_fields = [
        "nguyen_nhan_khong_dap_ung",
        "nguoi_dong_bo__email",
        "nguoi_dong_bo__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["ngay_dong_bo", "created_at", "updated_at"]
    ordering = ["-ngay_dong_bo", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewBCHCSongHinh]
        if self.action in ["create", "dong_bo"]:
            permission_classes = [CanCreateBCHCSongHinh]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SoBCHCSongHinh.objects.select_related(
            "nha_may",
            "nguoi_dong_bo",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        item = serializer.save(
            nha_may=_get_song_hinh_factory(),
            nguoi_dong_bo=self.request.user,
        )
        item.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        if not (
            has_profile_permission(user, "can_edit_bchc_song_hinh")
            or instance.nguoi_dong_bo_id == user.id
        ):
            raise PermissionDenied("Chi user dong bo hoac user co quyen moi duoc cap nhat so BCHC Song Hinh.")
        item = serializer.save()
        item.save()

    def perform_destroy(self, instance):
        if not (
            has_profile_permission(self.request.user, "can_edit_bchc_song_hinh")
            or instance.nguoi_dong_bo_id == self.request.user.id
        ):
            raise PermissionDenied("Chi user dong bo hoac user co quyen moi duoc xoa so BCHC Song Hinh.")
        return super().perform_destroy(instance)

    @action(detail=False, methods=["post"], url_path="dong-bo")
    def dong_bo(self, request):
        ngay_dong_bo = request.data.get("ngay_dong_bo") or request.data.get("date")
        if not ngay_dong_bo:
            return Response(
                {"detail": "Thieu ngay_dong_bo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sync_date = datetime.strptime(str(ngay_dong_bo), "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "ngay_dong_bo phai co dinh dang YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        san_xuat = (
            ThongsoSanxuat.objects.filter(nha_may="songhinh", thoi_gian__date=sync_date)
            .order_by("-thoi_gian")
            .first()
        )
        if not san_xuat:
            return Response(
                {"detail": "Khong co du lieu ThongsoSanxuat Song Hinh cho ngay nay."},
                status=status.HTTP_404_NOT_FOUND,
            )

        quy_trinh = _find_muc_nuoc_quy_trinh(sync_date)
        muc_nuoc_tu = _decimal_or_none(getattr(quy_trinh, "muc_nuoc_bat_dau", None))
        muc_nuoc_den = _decimal_or_none(getattr(quy_trinh, "muc_nuoc_ket_thuc", None))
        muc_nuoc_ho = _decimal_or_none(san_xuat.cot_g)

        item, created = SoBCHCSongHinh.objects.get_or_create(
            ngay_dong_bo=sync_date,
            defaults={
                "nha_may": _get_song_hinh_factory(),
                "nguoi_dong_bo": request.user,
            },
        )
        if (
            not created
            and not request.user.is_superuser
            and item.nguoi_dong_bo_id
            and item.nguoi_dong_bo_id != request.user.id
        ):
            raise PermissionDenied("Chi user dong bo moi duoc dong bo lai ngay nay.")

        item.nha_may = item.nha_may or _get_song_hinh_factory()
        item.nguoi_dong_bo = request.user
        item.chu_ky_nguoi_dong_bo = None
        item.muc_nuoc_quy_trinh_tu = muc_nuoc_tu
        item.muc_nuoc_quy_trinh_den = muc_nuoc_den
        item.muc_nuoc_quy_trinh = _format_decimal_range(muc_nuoc_tu, muc_nuoc_den)
        item.muc_nuoc_ho = muc_nuoc_ho
        item.luu_luong_ve_ho = _decimal_or_none(san_xuat.cot_i)
        item.luu_luong_xa_tran = _decimal_or_none(san_xuat.cot_k)
        item.luu_luong_chay_may = _decimal_or_none(san_xuat.cot_j)
        item.luu_luong_chay_may_qt = _calculate_bchc_qt(
            muc_nuoc_ho,
            muc_nuoc_tu,
            muc_nuoc_den,
        )
        item.save()

        serializer = self.get_serializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)
