"""Shared organization directory administration.

That module owns the existing import/export resource. The registered model is
already ``tochuc.NhaMay``; moving the resource itself is a separate cleanup and
does not affect domain ownership.
"""
from django.contrib import admin

from .models import BoPhan, DonViToChuc


@admin.register(DonViToChuc)
class DonViToChucAdmin(admin.ModelAdmin):
    list_display = (
        "ma_don_vi",
        "ten_don_vi",
        "loai_don_vi",
        "don_vi_cha",
        "nha_may",
        "dang_hoat_dong",
    )
    list_filter = ("loai_don_vi", "nha_may", "dang_hoat_dong")
    search_fields = ("ma_don_vi", "ten_don_vi")


@admin.register(BoPhan)
class BoPhanAdmin(admin.ModelAdmin):
    list_display = (
        "ma_bo_phan",
        "ten_bo_phan",
        "don_vi",
        "loai_bo_phan",
        "dang_hoat_dong",
    )
    list_filter = ("loai_bo_phan", "don_vi", "dang_hoat_dong")
    search_fields = ("ma_bo_phan", "ten_bo_phan")
