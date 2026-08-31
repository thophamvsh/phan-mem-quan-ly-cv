from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from .models import BoPhan, DonViToChuc
from .permissions import (
    OrganizationDirectoryPermission,
    can_access_organization_plant,
)
from .serializers import BoPhanSerializer, DonViToChucSerializer


def _user_plant_id(user):
    return getattr(getattr(user, "profile", None), "nha_may_id", None)


def _scope_units(queryset, user):
    if user.is_superuser or getattr(
        getattr(user, "profile", None),
        "is_all_factories",
        False,
    ):
        return queryset
    plant_id = _user_plant_id(user)
    if not plant_id:
        return queryset.none()
    return queryset.filter(
        Q(nha_may_id=plant_id)
        | Q(nha_may__isnull=True, don_vi_cha__nha_may_id=plant_id)
        | Q(
            nha_may__isnull=True,
            don_vi_cha__nha_may__isnull=True,
            don_vi_cha__don_vi_cha__nha_may_id=plant_id,
        )
    ).distinct()


class DonViToChucViewSet(viewsets.ModelViewSet):
    serializer_class = DonViToChucSerializer
    permission_classes = [OrganizationDirectoryPermission]
    pagination_class = None
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "nha_may",
        "don_vi_cha",
        "loai_don_vi",
        "dang_hoat_dong",
    ]
    search_fields = ["ma_don_vi", "ten_don_vi"]
    ordering_fields = ["thu_tu", "ma_don_vi", "ten_don_vi"]
    ordering = ["thu_tu", "ten_don_vi"]

    def get_queryset(self):
        return _scope_units(
            DonViToChuc.objects.select_related("nha_may", "don_vi_cha"),
            self.request.user,
        )

    def _validated_plant_id(self, serializer):
        plant = serializer.validated_data.get(
            "nha_may",
            getattr(serializer.instance, "nha_may", None),
        )
        parent = serializer.validated_data.get(
            "don_vi_cha",
            getattr(serializer.instance, "don_vi_cha", None),
        )
        return plant.id if plant else (
            parent.nha_may_pham_vi_id if parent else None
        )

    def perform_create(self, serializer):
        plant_id = self._validated_plant_id(serializer)
        if not plant_id and not self.request.user.is_superuser:
            raise PermissionDenied(
                "Chỉ quản trị viên hệ thống được tạo đơn vị cấp công ty."
            )
        if plant_id and not can_access_organization_plant(
            self.request.user,
            plant_id,
        ):
            raise PermissionDenied(
                "Bạn không có quyền tạo đơn vị trong nhà máy này."
            )
        serializer.save()

    def perform_update(self, serializer):
        plant_id = self._validated_plant_id(serializer)
        if not plant_id and not self.request.user.is_superuser:
            raise PermissionDenied(
                "Chỉ quản trị viên hệ thống được quản lý đơn vị cấp công ty."
            )
        if plant_id and not can_access_organization_plant(
            self.request.user,
            plant_id,
        ):
            raise PermissionDenied(
                "Bạn không có quyền chuyển đơn vị sang nhà máy này."
            )
        serializer.save()

    def perform_destroy(self, instance):
        instance.dang_hoat_dong = False
        instance.save(update_fields=["dang_hoat_dong", "updated_at"])

    @action(detail=False, methods=["get"], url_path="options")
    def options(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            dang_hoat_dong=True
        )
        return Response(
            [
                {"id": item.id, "label": str(item)}
                for item in queryset
            ]
        )


class BoPhanViewSet(viewsets.ModelViewSet):
    serializer_class = BoPhanSerializer
    permission_classes = [OrganizationDirectoryPermission]
    pagination_class = None
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["don_vi", "loai_bo_phan", "dang_hoat_dong"]
    search_fields = ["ma_bo_phan", "ten_bo_phan"]
    ordering_fields = ["thu_tu", "ma_bo_phan", "ten_bo_phan"]
    ordering = ["don_vi", "thu_tu", "ten_bo_phan"]

    def get_queryset(self):
        queryset = BoPhan.objects.select_related(
            "don_vi",
            "don_vi__nha_may",
        )
        if self.request.user.is_superuser or getattr(
            getattr(self.request.user, "profile", None),
            "is_all_factories",
            False,
        ):
            scoped = queryset
        else:
            plant_id = _user_plant_id(self.request.user)
            scoped = (
                queryset.filter(don_vi__nha_may_id=plant_id)
                if plant_id
                else queryset.none()
            )
        plant_id = self.request.query_params.get("nha_may")
        return (
            scoped.filter(don_vi__nha_may_id=plant_id)
            if plant_id
            else scoped
        )

    def _validate_unit_scope(self, unit):
        if not can_access_organization_plant(
            self.request.user,
            unit.nha_may_pham_vi_id,
        ):
            raise PermissionDenied(
                "Bạn không có quyền quản lý bộ phận trong đơn vị này."
            )

    def perform_create(self, serializer):
        self._validate_unit_scope(serializer.validated_data["don_vi"])
        serializer.save()

    def perform_update(self, serializer):
        unit = serializer.validated_data.get(
            "don_vi",
            serializer.instance.don_vi,
        )
        self._validate_unit_scope(unit)
        serializer.save()

    def perform_destroy(self, instance):
        instance.dang_hoat_dong = False
        instance.save(update_fields=["dang_hoat_dong", "updated_at"])

    @action(detail=False, methods=["get"], url_path="options")
    def options(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            dang_hoat_dong=True
        )
        return Response(
            [
                {"id": item.id, "label": item.ten_bo_phan}
                for item in queryset
            ]
        )
