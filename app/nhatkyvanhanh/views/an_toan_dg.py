import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from django.core.exceptions import PermissionDenied

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from nhatkyvanhanh.models import SoAnToanDauGio
from nhatkyvanhanh.serializers import SoAnToanSerializer
from nhatkyvanhanh.permissions import CanCreateOperationLogbooks, CanViewSoAnToanDauGio, has_profile_permission


class SoAntoanFilterSet(django_filters.FilterSet):
    ngay_dong_bo_tu = django_filters.DateFilter(field_name="ngay_dong_bo", lookup_expr="gte")
    ngay_dong_bo_den = django_filters.DateFilter(field_name="ngay_dong_bo", lookup_expr="lte")

    class Meta:
        model = SoAnToanDauGio
        fields = ["nha_may", "ngay_dong_bo", "ngay_dong_bo_tu", "ngay_dong_bo_den", "nguoi_dong_bo"]


class SoAnToanViewSet(viewsets.ModelViewSet):
    serializer_class = SoAnToanSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoAntoanFilterSet
    search_fields = [
        "tinh_trang_an_toan",
        "nguoi_dong_bo__email",
        "nguoi_dong_bo__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["ngay_dong_bo", "created_at", "updated_at"]
    ordering = ["-ngay_dong_bo", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewSoAnToanDauGio]
        if self.action == "create":
            permission_classes = [CanViewSoAnToanDauGio, CanCreateOperationLogbooks]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SoAnToanDauGio.objects.select_related(
            "nha_may",
            "nguoi_dong_bo",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        item = serializer.save(
            nguoi_dong_bo=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        if not (
            has_profile_permission(user, "can_edit_so_an_toan_dau_gio")
            or instance.nguoi_dong_bo_id == user.id
        ):
            raise PermissionDenied("Ban khong co quyen chinh sua so an toan dau gio nay.")
        item = serializer.save()
        item.save()

    def perform_destroy(self, instance):
        if not (
            has_profile_permission(self.request.user, "can_delete_so_an_toan_dau_gio")
            or instance.nguoi_dong_bo_id == self.request.user.id
        ):
            raise PermissionDenied("Ban khong co quyen xoa so an toan dau gio nay.")
        return super().perform_destroy(instance)
