"""Compatibility imports for legacy quanlyvanhanh view references."""

from quanlyvanhanh.views_thietbi import ThietBiViewSet
from quanlyvanhanh.views_thietbi_meta import AnToanThietBiViewSet, DinhKemViewSet
from quanlyvanhanh.views_thongso_dien import ThongSoVanHanhViewSet
from quanlyvanhanh.views_thongso_tomay import ThongSoToMayViewSet
from quanlyvanhanh.views_vattu import ThietBiVatTuViewSet, VatTuViewSet

__all__ = [
    "AnToanThietBiViewSet",
    "DinhKemViewSet",
    "ThietBiVatTuViewSet",
    "ThietBiViewSet",
    "ThongSoToMayViewSet",
    "ThongSoVanHanhViewSet",
    "VatTuViewSet",
]
