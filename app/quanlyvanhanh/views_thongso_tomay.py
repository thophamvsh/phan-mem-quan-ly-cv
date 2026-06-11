from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.factory_scope import (
    apply_request_factory_to_serializer,
    filter_queryset_by_factory,
    has_profile_permission,
)
from quanlyvanhanh.models import ThietBi, ThongSoToMay
from quanlyvanhanh.serializers import (
    ThongSoToMayCreateSerializer,
    ThongSoToMaySerializer,
)
from quanlyvanhanh.services.thongso_tomay_service import (
    bulk_upsert_thong_so_to_may,
)


def _ensure_thiet_bi_access(user, thiet_bi):
    if not thiet_bi:
        return

    allowed = filter_queryset_by_factory(
        ThietBi.objects.filter(pk=thiet_bi.pk),
        user,
        "nha_may",
        "string",
    ).exists()
    if not allowed:
        raise PermissionDenied(
            "Ban khong co quyen thao tac voi thiet bi cua nha may nay."
        )


class ThongSoToMayViewSet(viewsets.ModelViewSet):
    """ViewSet quan ly thong so to may va legacy endpoints."""

    queryset = ThongSoToMay.objects.select_related("thiet_bi").all()
    serializer_class = ThongSoToMaySerializer

    def check_permissions(self, request):
        super().check_permissions(request)
        
        # Check custom profile permissions based on action
        if self.action in ["list", "retrieve", "by_date", "by_device", "config"]:
            if not has_profile_permission(request.user, "can_view_operation_parameters"):
                self.permission_denied(
                    request,
                    message="Tài khoản của bạn chưa được cấp quyền xem thông số vận hành. Vui lòng liên hệ quản trị viên."
                )
        elif self.action in ["create", "update", "partial_update", "bulk_create", "bulk_upsert"]:
            if not has_profile_permission(request.user, "can_edit_operation_parameters"):
                self.permission_denied(
                    request,
                    message="Tài khoản của bạn chưa được cấp quyền thêm/sửa thông số vận hành. Vui lòng liên hệ quản trị viên."
                )
        elif self.action in ["destroy", "delete_by_day"]:
            if not has_profile_permission(request.user, "can_delete_operation_parameters"):
                self.permission_denied(
                    request,
                    message="Tài khoản của bạn chưa được cấp quyền xóa dữ liệu thông số vận hành. Vui lòng liên hệ quản trị viên."
                )
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["thiet_bi", "ten_thong_so", "nha_may", "ngay_nhap"]
    search_fields = ["ten_thong_so", "ma_thong_so", "thiet_bi__ten", "ghi_chu"]
    ordering_fields = ["ten_thong_so", "ngay_nhap", "thoi_diem_nhap", "created_at"]
    ordering = ["-ngay_nhap", "-thoi_diem_nhap"]

    def get_serializer_class(self):
        if self.action in ["create", "bulk_upsert", "bulk_create"]:
            return ThongSoToMayCreateSerializer
        return ThongSoToMaySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return filter_queryset_by_factory(
            queryset,
            self.request.user,
            "nha_may",
            "string",
        )

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get("thiet_bi"))
        serializer.save(
            nguoi_nhap=self.request.user,
            **apply_request_factory_to_serializer(
                self.request.user,
                serializer,
                "nha_may",
                "string",
            )
        )

    def perform_update(self, serializer):
        if not self.request.user.is_superuser and serializer.instance.nguoi_nhap and serializer.instance.nguoi_nhap != self.request.user:
            raise PermissionDenied("Bạn không có quyền sửa thông số này vì nó được nhập bởi người dùng khác.")
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get("thiet_bi", serializer.instance.thiet_bi),
        )
        serializer.save(
            nguoi_nhap=self.request.user,
            **apply_request_factory_to_serializer(
                self.request.user,
                serializer,
                "nha_may",
                "string",
            )
        )

    def perform_destroy(self, instance):
        if not self.request.user.is_superuser and instance.nguoi_nhap and instance.nguoi_nhap != self.request.user:
            raise PermissionDenied("Bạn không có quyền xóa thông số này vì nó được nhập bởi người dùng khác.")
        instance.delete()

    @action(detail=False, methods=["get"])
    def by_date(self, request):
        date_value = request.query_params.get("date") or request.query_params.get("ngay")
        if not date_value:
            return Response(
                {"error": "Can cung cap date hoac ngay"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(ngay_nhap=date_value)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_device(self, request):
        device_id = request.query_params.get("device_id") or request.query_params.get("thiet_bi_id")
        device_code = request.query_params.get("device_code") or request.query_params.get("thiet_bi_ma")

        if not (device_id or device_code):
            return Response(
                {
                    "error": (
                        "Can cung cap device_id/thiet_bi_id "
                        "hoac device_code/thiet_bi_ma"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset()
        if device_id:
            try:
                device = ThietBi.objects.get(id=device_id)
                prefix = ".".join(device.ma_day_du.split(".")[:3])
                queryset = queryset.filter(thiet_bi__ma_day_du__startswith=prefix)
            except ThietBi.DoesNotExist:
                queryset = queryset.filter(thiet_bi_id=device_id)
        else:
            prefix = ".".join(device_code.split(".")[:3])
            queryset = queryset.filter(thiet_bi__ma_day_du__startswith=prefix)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        return self.bulk_upsert(request)

    @action(detail=False, methods=["post"])
    def bulk_upsert(self, request):
        data_list = request.data
        if not isinstance(data_list, list):
            return Response(
                {"error": "Du lieu phai la mot mang"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = bulk_upsert_thong_so_to_may(request.user, data_list)
        except PermissionDenied:
            raise
        except Exception as exc:
            return Response(
                {"error": f"Loi khi xu ly du lieu: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                **result,
                "message": (
                    f"Da tao {result['created']} ban ghi moi, "
                    f"cap nhat {result['updated']} ban ghi, "
                    f"xoa {result.get('deleted', 0)} ban ghi"
                ),
            },
            status=(
                status.HTTP_201_CREATED
                if result["created"] > 0
                else status.HTTP_200_OK
            ),
        )

    @action(detail=False, methods=["delete"])
    def delete_by_day(self, request):
        thiet_bi_ma = request.query_params.get("thiet_bi_ma")
        thiet_bi_id = request.query_params.get("thiet_bi_id")
        ngay_str = request.query_params.get("ngay")

        if not ngay_str:
            return Response(
                {"error": "Can cung cap tham so ngay (ngay)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(ngay_nhap=ngay_str)
        if thiet_bi_id:
            try:
                device = ThietBi.objects.get(id=thiet_bi_id)
                prefix = ".".join(device.ma_day_du.split(".")[:3])
                queryset = queryset.filter(thiet_bi__ma_day_du__startswith=prefix)
            except ThietBi.DoesNotExist:
                queryset = queryset.filter(thiet_bi_id=thiet_bi_id)
        elif thiet_bi_ma:
            prefix = ".".join(thiet_bi_ma.split(".")[:3])
            queryset = queryset.filter(thiet_bi__ma_day_du__startswith=prefix)

        if not request.user.is_superuser:
            forbidden_exists = queryset.filter(nguoi_nhap__isnull=False).exclude(nguoi_nhap=request.user).exists()
            if forbidden_exists:
                raise PermissionDenied("Bạn không có quyền xóa các thông số tổ máy của ngày này vì có một số bản ghi được nhập bởi người dùng khác.")

        deleted_count = queryset.delete()[0]
        return Response(
            {
                "message": f"Da xoa {deleted_count} thong so to may",
                "deleted_count": deleted_count,
            }
        )
