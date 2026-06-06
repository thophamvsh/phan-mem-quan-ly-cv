from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.exceptions import PermissionDenied

from core.factory_scope import (
    filter_queryset_by_factory,
    has_all_factory_access,
)
from quanlyvanhanh.models import AnToanThietBi, DinhKem, ThietBi
from quanlyvanhanh.serializers import AnToanThietBiSerializer, DinhKemSerializer


def _ensure_thiet_bi_access(user, thiet_bi):
    if not thiet_bi or has_all_factory_access(user):
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


class AnToanThietBiViewSet(viewsets.ModelViewSet):
    """ViewSet quan ly an toan thiet bi."""

    queryset = AnToanThietBi.objects.all()
    serializer_class = AnToanThietBiSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["thiet_bi", "bao_ho_lao_dong"]
    search_fields = ["moi_nguy", "bien_phap", "bao_ho_lao_dong", "ghi_chu"]
    ordering_fields = ["thiet_bi__ten", "moi_nguy"]
    ordering = ["thiet_bi__ten", "moi_nguy"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("thiet_bi")
        return filter_queryset_by_factory(
            queryset,
            self.request.user,
            "thiet_bi__nha_may",
            "string",
        )

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get("thiet_bi"))
        serializer.save()

    def perform_update(self, serializer):
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get("thiet_bi", serializer.instance.thiet_bi),
        )
        serializer.save()


class DinhKemViewSet(viewsets.ModelViewSet):
    """ViewSet quan ly dinh kem."""

    queryset = DinhKem.objects.all()
    serializer_class = DinhKemSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["thiet_bi", "dinh_dang"]
    search_fields = ["tieu_de", "thiet_bi__ten"]
    ordering_fields = ["tieu_de", "ngay_tai_len"]
    ordering = ["-ngay_tai_len"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("thiet_bi")
        return filter_queryset_by_factory(
            queryset,
            self.request.user,
            "thiet_bi__nha_may",
            "string",
        )

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get("thiet_bi"))
        serializer.save()

    def perform_update(self, serializer):
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get("thiet_bi", serializer.instance.thiet_bi),
        )
        serializer.save()
