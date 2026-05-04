from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.formats import base_formats

from .models import SonghinhMnh, ThuongKonTumMnh, Vinhson_HoA, Vinhson_HoB, Vinhson_Hoc


class XLSXOnlyMixin:
    # Chỉ dùng các format đã có sẵn dependency trong project
    formats = (base_formats.XLSX, base_formats.CSV)

    def get_import_formats(self):
        return list(self.formats)

    def get_export_formats(self):
        return list(self.formats)


class BaseThuyVanResource(resources.ModelResource):
    class Meta:
        # File import chỉ cần đúng 2 cột: Mucnuoc, dungtich
        fields = ("Mucnuoc", "dungtich")
        export_order = fields
        # Luôn tạo bản ghi mới khi import, không dò trùng bằng get()
        force_init_instance = True


class SonghinhMnhResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = SonghinhMnh


class ThuongKonTumMnhResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = ThuongKonTumMnh


class Vinhson_HoAResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = Vinhson_HoA


class Vinhson_HoBResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = Vinhson_HoB


class Vinhson_HocResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = Vinhson_Hoc


@admin.register(SonghinhMnh)
class SonghinhMnhAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = SonghinhMnhResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")


@admin.register(ThuongKonTumMnh)
class ThuongKonTumMnhAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThuongKonTumMnhResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")


@admin.register(Vinhson_HoA)
class Vinhson_HoAAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = Vinhson_HoAResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")


@admin.register(Vinhson_HoB)
class Vinhson_HoBAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = Vinhson_HoBResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")


@admin.register(Vinhson_Hoc)
class Vinhson_HocAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = Vinhson_HocResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")