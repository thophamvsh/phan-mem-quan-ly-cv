from django.contrib import admin
from django.db.models import Q
from import_export.admin import ImportExportModelAdmin
from import_export.formats import base_formats

from .models import BoPhan, DonViToChuc, NhaMay, NhanSu
from .resources import NhaMayResource, NhanSuResource


@admin.register(NhaMay)
class NhaMayAdmin(ImportExportModelAdmin):
    resource_class = NhaMayResource
    formats = (base_formats.XLSX,)
    list_display = ("ma_nha_may", "ten_nha_may")
    search_fields = ("ma_nha_may", "ten_nha_may")
    list_per_page = 200

    def get_import_formats(self):
        return list(self.formats)

    def get_export_formats(self):
        return list(self.formats)


class NhaMayNhanSuFilter(admin.SimpleListFilter):
    title = "nhà máy"
    parameter_name = "nha_may"

    def lookups(self, request, model_admin):
        return NhaMay.objects.order_by("ten_nha_may").values_list(
            "id",
            "ten_nha_may",
        )

    def queryset(self, request, queryset):
        plant_id = self.value()
        if not plant_id:
            return queryset
        return queryset.filter(
            Q(don_vi__nha_may_id=plant_id)
            | Q(don_vi__don_vi_cha__nha_may_id=plant_id)
            | Q(
                don_vi__don_vi_cha__don_vi_cha__nha_may_id=plant_id,
            )
        ).distinct()


@admin.register(NhanSu)
class NhanSuAdmin(ImportExportModelAdmin):
    resource_class = NhanSuResource
    formats = (base_formats.XLSX,)
    list_display = (
        "ho_ten",
        "ma_nhan_vien",
        "don_vi",
        "bo_phan",
        "chuc_danh",
        "user",
        "dang_lam_viec",
    )
    list_filter = (
        NhaMayNhanSuFilter,
        "don_vi",
        "bo_phan",
        "dang_lam_viec",
    )
    search_fields = (
        "ho_ten",
        "ma_nhan_vien",
        "chuc_danh",
        "user__username",
    )

    def get_import_formats(self):
        return list(self.formats)

    def get_export_formats(self):
        return list(self.formats)


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
