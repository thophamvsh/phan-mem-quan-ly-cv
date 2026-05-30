from django.utils import timezone
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from nhatkyvanhanh.models import Sonhatkyvanhanh, SonhatkyvanhanhDiesel
from nhatkyvanhanh.serializers import SonhatkyvanhanhSerializer, SonhatkyvanhanhDieselSerializer
from nhatkyvanhanh.permissions import (
    CanViewOperationLogbooks,
    CanCreateOperationLogbooks,
    CanConfirmOperationLogbooks,
    CanViewDieselOperationLogbooks,
    CanCreateDieselOperationLogbooks,
)
from .helpers import (
    _operation_logbook_locked,
    _can_edit_operation_logbook,
    _can_delete_operation_logbook,
    _can_edit_diesel_operation_logbook,
    _can_delete_diesel_operation_logbook,
)


class SonhatkyvanhanhFilterSet(django_filters.FilterSet):
    ngay_tao = django_filters.DateFilter(
        field_name="thoi_gian_tao",
        lookup_expr="date",
    )
    ngay_tao_tu = django_filters.DateFilter(
        field_name="thoi_gian_tao",
        lookup_expr="date__gte",
    )
    ngay_tao_den = django_filters.DateFilter(
        field_name="thoi_gian_tao",
        lookup_expr="date__lte",
    )

    class Meta:
        model = Sonhatkyvanhanh
        fields = [
            "nha_may",
            "trang_thai",
            "ngay_tao",
            "ngay_tao_tu",
            "ngay_tao_den",
            "nguoi_tao",
            "nguoi_xac_nhan",
        ]


class SonhatkyvanhanhViewSet(viewsets.ModelViewSet):
    serializer_class = SonhatkyvanhanhSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SonhatkyvanhanhFilterSet
    search_fields = [
        "noi_dung_tao",
        "nguoi_tao__email",
        "nguoi_tao__username",
        "nguoi_xac_nhan__email",
        "nguoi_xac_nhan__username",
    ]
    ordering_fields = ["thoi_gian_tao", "created_at", "updated_at"]
    ordering = ["-thoi_gian_tao", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewOperationLogbooks]
        if self.action == "create":
            permission_classes = [CanCreateOperationLogbooks]
        elif self.action == "xac_nhan":
            permission_classes = [CanConfirmOperationLogbooks]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Sonhatkyvanhanh.objects.select_related(
            "nha_may",
            "nguoi_tao",
            "nguoi_xac_nhan",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        item = serializer.save(
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_update(self, serializer):
        if _operation_logbook_locked(serializer.instance):
            raise PermissionDenied("So nhat ky van hanh da duoc xac nhan, khong duoc chinh sua.")
        if not _can_edit_operation_logbook(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so nhat ky van hanh.")
        item = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_destroy(self, instance):
        if _operation_logbook_locked(instance):
            raise PermissionDenied("So nhat ky van hanh da duoc xac nhan, khong duoc xoa.")
        if not _can_delete_operation_logbook(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so nhat ky van hanh.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def xac_nhan(self, request, pk=None):
        item = self.get_object()
        if item.nguoi_tao_id == request.user.id:
            return Response(
                {"detail": "Nguoi tao so khong duoc tu xac nhan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if item.nguoi_xac_nhan_id and item.nguoi_xac_nhan_id != request.user.id:
            return Response(
                {"detail": "So nhat ky van hanh da duoc user khac xac nhan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not item.xac_nhan_at:
            item.nguoi_xac_nhan = request.user
            item.xac_nhan_at = timezone.now()
            item.save()
        serializer = self.get_serializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SonhatkyvanhanhDieselFilterSet(django_filters.FilterSet):
    ngay_tu = django_filters.DateFilter(field_name="thoi_gian", lookup_expr="date__gte")
    ngay_den = django_filters.DateFilter(field_name="thoi_gian", lookup_expr="date__lte")

    class Meta:
        model = SonhatkyvanhanhDiesel
        fields = ["nha_may", "ca_truc", "ngay_tu", "ngay_den", "nguoi_tao"]


class SonhatkyvanhanhDieselViewSet(viewsets.ModelViewSet):
    serializer_class = SonhatkyvanhanhDieselSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SonhatkyvanhanhDieselFilterSet
    search_fields = [
        "noi_dung",
        "ca_truc",
        "nguoi_tao__email",
        "nguoi_tao__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["thoi_gian", "created_at", "updated_at"]
    ordering = ["-thoi_gian", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewDieselOperationLogbooks]
        if self.action == "create":
            permission_classes = [CanCreateDieselOperationLogbooks]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SonhatkyvanhanhDiesel.objects.select_related(
            "nha_may",
            "nguoi_tao",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        item = serializer.save(
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_update(self, serializer):
        if not _can_edit_diesel_operation_logbook(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so nhat ky van hanh Diesel.")
        item = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_destroy(self, instance):
        if not _can_delete_diesel_operation_logbook(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so nhat ky van hanh Diesel.")
        return super().perform_destroy(instance)
