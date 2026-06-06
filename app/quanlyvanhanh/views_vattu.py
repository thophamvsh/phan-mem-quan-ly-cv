from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.exceptions import PermissionDenied

from core.factory_scope import (
    filter_queryset_by_factory,
    has_all_factory_access,
)
from quanlyvanhanh.models import ThietBi, ThietBiVatTu, VatTu
from quanlyvanhanh.serializers import ThietBiVatTuSerializer, VatTuSerializer


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


class VatTuViewSet(viewsets.ModelViewSet):
    """ViewSet quan ly vat tu."""

    queryset = VatTu.objects.all()
    serializer_class = VatTuSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["nha_che_tao", "nha_cung_cap", "don_vi_tinh"]
    search_fields = ["ma_vat_tu", "ten_vat_tu", "quy_cach"]
    ordering_fields = ["ma_vat_tu", "ten_vat_tu"]
    ordering = ["ma_vat_tu"]


class ThietBiVatTuViewSet(viewsets.ModelViewSet):
    """ViewSet quan ly vat tu gan voi thiet bi."""

    queryset = ThietBiVatTu.objects.all()
    serializer_class = ThietBiVatTuSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["thiet_bi", "vat_tu"]
    search_fields = ["thiet_bi__ten", "vat_tu__ten_vat_tu", "ghi_chu"]
    ordering_fields = ["thiet_bi__ten", "vat_tu__ten_vat_tu"]
    ordering = ["thiet_bi__ten", "vat_tu__ten_vat_tu"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("thiet_bi", "vat_tu")
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
