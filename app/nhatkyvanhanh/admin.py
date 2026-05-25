from django.contrib import admin
from django.contrib.auth import get_user_model
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.formats import base_formats
from import_export.widgets import ForeignKeyWidget

from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi

from .models import (
    ChiTietSoGiaoNhanCaHC,
    ChiTietSoGiaoNhanCaVH,
    ChiTietChuyenDoiThietBi,
    ChiTietChuyenDoiTBThang,
    DienBienSuKien,
    KhacPhucSuKien,
    LanChuyenDoiThietBi,
    MauChuyenDoiThietBi,
    MauChuyenDoiTBThang,
    NguoiTrucSoGiaoNhanCaHC,
    SoBCHCSongHinh,
    SoChuyenDoiTBThang,
    SoChuyenDoiThietBiTuan,
    Sonhatkyvanhanh,
    SonhatkyvanhanhDiesel,
    SuKien,
    SogiaonhancaHC,
    SogiaonhancaVH,
    SoAnToanDauGio,
)


User = get_user_model()


class SafeExportChangeListMixin:
    search_help_text = ""

    def get_export_queryset(self, request):
        from django.contrib.admin.views.main import ChangeList

        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        list_select_related = self.get_list_select_related(request)
        list_editable = getattr(self, "list_editable", ())
        list_per_page = getattr(self, "list_per_page", 100)
        list_max_show_all = getattr(self, "list_max_show_all", 200)
        sortable_by = getattr(self, "sortable_by", None)
        date_hierarchy = getattr(self, "date_hierarchy", None)

        change_list = ChangeList(
            request,
            self.model,
            list_display,
            list_display_links,
            list_filter,
            date_hierarchy,
            search_fields,
            list_select_related,
            list_per_page,
            list_max_show_all,
            list_editable,
            self,
            sortable_by,
        )
        return change_list.get_queryset(request)


class XLSXOnlyMixin:
    formats = (base_formats.XLSX,)

    def get_import_formats(self):
        return list(self.formats)

    def get_export_formats(self):
        return list(self.formats)


class MauChuyenDoiThietBiResource(resources.ModelResource):
    nha_may = fields.Field(
        column_name="ma_nha_may",
        attribute="nha_may",
        widget=ForeignKeyWidget(Bang_nha_may, "ma_nha_may"),
    )
    thiet_bi = fields.Field(
        column_name="thiet_bi_ma_day_du",
        attribute="thiet_bi",
        widget=ForeignKeyWidget(ThietBi, "ma_day_du"),
    )

    class Meta:
        model = MauChuyenDoiThietBi
        import_id_fields = ("nha_may", "thiet_bi")
        fields = (
            "nha_may",
            "to_may",
            "nhom_thiet_bi",
            "thiet_bi",
            "thu_tu",
            "dang_su_dung",
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class MauChuyenDoiTBThangResource(resources.ModelResource):
    nha_may = fields.Field(
        column_name="ma_nha_may",
        attribute="nha_may",
        widget=ForeignKeyWidget(Bang_nha_may, "ma_nha_may"),
    )
    thiet_bi = fields.Field(
        column_name="thiet_bi_ma_day_du",
        attribute="thiet_bi",
        widget=ForeignKeyWidget(ThietBi, "ma_day_du"),
    )

    class Meta:
        model = MauChuyenDoiTBThang
        import_id_fields = ("nha_may", "thiet_bi")
        fields = (
            "nha_may",
            "ma_nhom",
            "ten_nhom",
            "don_vi_nhom",
            "thiet_bi",
            "don_vi",
            "thu_tu_nhom",
            "thu_tu",
            "dang_su_dung",
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class SoChuyenDoiTBThangResource(resources.ModelResource):
    nha_may = fields.Field(
        column_name="ma_nha_may",
        attribute="nha_may",
        widget=ForeignKeyWidget(Bang_nha_may, "ma_nha_may"),
    )
    nguoi_tao = fields.Field(
        column_name="nguoi_tao_email",
        attribute="nguoi_tao",
        widget=ForeignKeyWidget(User, "email"),
    )

    class Meta:
        model = SoChuyenDoiTBThang
        import_id_fields = ("nha_may", "nam", "thang", "ca_truc")
        fields = (
            "nha_may",
            "nam",
            "thang",
            "ca_truc",
            "thang_bat_dau",
            "thang_ket_thuc",
            "nguoi_tao",
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class ChiTietChuyenDoiTBThangResource(resources.ModelResource):
    so = fields.Field(
        column_name="so_id",
        attribute="so",
        widget=ForeignKeyWidget(SoChuyenDoiTBThang, "id"),
    )
    thiet_bi = fields.Field(
        column_name="thiet_bi_ma_day_du",
        attribute="thiet_bi",
        widget=ForeignKeyWidget(ThietBi, "ma_day_du"),
    )

    class Meta:
        model = ChiTietChuyenDoiTBThang
        import_id_fields = ("so", "thiet_bi")
        fields = (
            "so",
            "thiet_bi",
            "ma_nhom",
            "ten_nhom",
            "don_vi_nhom",
            "don_vi",
            "dau_thang",
            "cuoi_thang",
            "thuc_hien",
            "ghi_chu",
            "thu_tu_nhom",
            "thu_tu",
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class KhacPhucSuKienInline(admin.TabularInline):
    model = KhacPhucSuKien
    readonly_fields = ("nguoi_tao", "created_at", "updated_at")
    extra = 0


class DienBienSuKienInline(admin.TabularInline):
    model = DienBienSuKien
    readonly_fields = ("nguoi_tao", "chuc_danh_nguoi_tao", "created_at", "updated_at")
    extra = 0


class ChiTietSoGiaoNhanCaVHInline(admin.TabularInline):
    model = ChiTietSoGiaoNhanCaVH
    readonly_fields = ("nguoi_tao", "created_at", "updated_at")
    extra = 0


class ChiTietSoGiaoNhanCaHCInline(admin.TabularInline):
    model = ChiTietSoGiaoNhanCaHC
    readonly_fields = ("nguoi_tao", "created_at", "updated_at")
    extra = 0


class NguoiTrucSoGiaoNhanCaHCInline(admin.TabularInline):
    model = NguoiTrucSoGiaoNhanCaHC
    readonly_fields = ("nguoi_tao", "created_at", "updated_at")
    extra = 0


class ChiTietChuyenDoiThietBiInline(admin.TabularInline):
    model = ChiTietChuyenDoiThietBi
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("thiet_bi",)
    extra = 0


class LanChuyenDoiThietBiInline(admin.TabularInline):
    model = LanChuyenDoiThietBi
    readonly_fields = ("nguoi_thuc_hien", "created_at", "updated_at")
    extra = 0


class ChiTietChuyenDoiTBThangInline(admin.TabularInline):
    model = ChiTietChuyenDoiTBThang
    readonly_fields = ("thuc_hien", "created_at", "updated_at")
    autocomplete_fields = ("thiet_bi",)
    extra = 0


@admin.register(SuKien)
class SuKienAdmin(admin.ModelAdmin):
    list_display = (
        "ten_he_thong_thiet_bi",
        "nha_may",
        "thoi_gian_xay_ra",
        "loai",
        "trang_thai",
        "ben_ghi_nhan_su_kien",
        "nguoi_tao",
        "created_at",
    )
    list_filter = ("nha_may", "loai", "trang_thai", "thoi_gian_xay_ra", "created_at")
    search_fields = (
        "ten_he_thong_thiet_bi",
        "hien_tuong_dien_bien",
        "chi_dao",
        "nguoi_chi_dao__email",
        "bao_cho",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
        "ben_ghi_nhan_su_kien__email",
        "nguoi_tao__email",
    )
    readonly_fields = (
        "chu_ky_ben_ghi_nhan_su_kien",
        "chu_ky_nguoi_chi_dao",
        "created_at",
        "updated_at",
    )
    exclude = ("chu_ky_ben_ghi_nhan_su_kien", "chu_ky_nguoi_chi_dao")
    inlines = [DienBienSuKienInline, KhacPhucSuKienInline]


@admin.register(DienBienSuKien)
class DienBienSuKienAdmin(admin.ModelAdmin):
    list_display = (
        "su_kien",
        "thoi_gian_dien_bien",
        "nguoi_tao",
        "chuc_danh_nguoi_tao",
        "created_at",
    )
    list_filter = ("thoi_gian_dien_bien", "created_at")
    search_fields = (
        "su_kien__ten_he_thong_thiet_bi",
        "noi_dung",
        "nguoi_tao__email",
        "chuc_danh_nguoi_tao",
    )
    readonly_fields = ("nguoi_tao", "chuc_danh_nguoi_tao", "created_at", "updated_at")


@admin.register(KhacPhucSuKien)
class KhacPhucSuKienAdmin(admin.ModelAdmin):
    list_display = (
        "su_kien",
        "nguoi_tao",
        "thoi_gian_xu_ly",
        "ben_xu_ly_su_kien_thiet_bi",
        "nguoi_xac_nhan_xu_ly",
        "created_at",
    )
    list_filter = ("thoi_gian_xu_ly", "created_at")
    search_fields = (
        "su_kien__ten_he_thong_thiet_bi",
        "noi_dung_xu_ly_khac_phuc",
        "nguoi_tao__email",
        "ben_xu_ly_su_kien_thiet_bi__email",
    )
    readonly_fields = (
        "nguoi_tao",
        "chu_ky_ben_xu_ly_su_kien_thiet_bi",
        "chu_ky_nguoi_xac_nhan_xu_ly",
        "created_at",
        "updated_at",
    )
    exclude = (
        "chu_ky_ben_xu_ly_su_kien_thiet_bi",
        "chu_ky_nguoi_xac_nhan_xu_ly",
    )


@admin.register(SogiaonhancaVH)
class SogiaonhancaVHAdmin(admin.ModelAdmin):
    list_display = (
        "ngay_truc",
        "ca_truc",
        "dia_diem",
        "nguoi_tao",
        "user_giao_ca",
        "user_nhan_ca",
        "trang_thai",
        "co_chu_ky",
        "created_at",
    )
    list_filter = ("ca_truc", "trang_thai", "ngay_truc", "created_at")
    search_fields = (
        "dia_diem",
        "truc_chinh",
        "truc_phu",
        "noi_dung_chi_tiets__tieu_de",
        "noi_dung_chi_tiets__noi_dung",
        "user_giao_ca__email",
        "user_nhan_ca__email",
    )
    readonly_fields = ("nguoi_tao", "chu_ky_user_giao_ca", "chu_ky_user_nhan_ca", "created_at", "updated_at")
    exclude = ("chu_ky_user_giao_ca", "chu_ky_user_nhan_ca")
    inlines = [ChiTietSoGiaoNhanCaVHInline]

    def co_chu_ky(self, obj):
        return bool(obj.chu_ky_user_giao_ca or obj.chu_ky_user_nhan_ca)

    co_chu_ky.boolean = True
    co_chu_ky.short_description = "Có chữ ký"


@admin.register(SogiaonhancaHC)
class SogiaonhancaHCAdmin(admin.ModelAdmin):
    list_display = (
        "ngay_truc",
        "dia_diem",
        "nguoi_tao",
        "user_giao_ca",
        "user_nhan_ca",
        "trang_thai",
        "co_chu_ky",
        "created_at",
    )
    list_filter = ("trang_thai", "ngay_truc", "created_at")
    search_fields = (
        "dia_diem",
        "nguoi_truc",
        "nguoi_truc_2",
        "nguoi_truc_3",
        "noi_dung_chi_tiets__tieu_de",
        "noi_dung_chi_tiets__noi_dung",
        "user_giao_ca__email",
        "user_nhan_ca__email",
    )
    readonly_fields = ("nguoi_tao", "chu_ky_user_giao_ca", "chu_ky_user_nhan_ca", "created_at", "updated_at")
    exclude = ("chu_ky_user_giao_ca", "chu_ky_user_nhan_ca")
    inlines = [NguoiTrucSoGiaoNhanCaHCInline, ChiTietSoGiaoNhanCaHCInline]

    def co_chu_ky(self, obj):
        return bool(obj.chu_ky_user_giao_ca or obj.chu_ky_user_nhan_ca)

    co_chu_ky.boolean = True
    co_chu_ky.short_description = "Có chữ ký"


@admin.register(Sonhatkyvanhanh)
class SonhatkyvanhanhAdmin(admin.ModelAdmin):
    list_display = (
        "thoi_gian_tao",
        "nha_may",
        "nguoi_tao",
        "nguoi_xac_nhan",
        "trang_thai",
        "co_chu_ky",
        "created_at",
    )
    list_filter = ("trang_thai", "thoi_gian_tao", "created_at", "nha_may")
    search_fields = (
        "noi_dung_tao",
        "nguoi_tao__email",
        "nguoi_tao__username",
        "nguoi_xac_nhan__email",
        "nguoi_xac_nhan__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    )
    readonly_fields = (
        "nguoi_tao",
        "chu_ky_nguoi_tao",
        "chu_ky_nguoi_xac_nhan",
        "created_at",
        "updated_at",
    )
    exclude = ("chu_ky_nguoi_tao", "chu_ky_nguoi_xac_nhan")

    def co_chu_ky(self, obj):
        return bool(obj.chu_ky_nguoi_tao or obj.chu_ky_nguoi_xac_nhan)

    co_chu_ky.boolean = True
    co_chu_ky.short_description = "Có chữ ký"


@admin.register(SonhatkyvanhanhDiesel)
class SonhatkyvanhanhDieselAdmin(admin.ModelAdmin):
    list_display = (
        "thoi_gian",
        "nha_may",
        "ca_truc",
        "noi_dung",
        "nguoi_tao",
        "co_chu_ky",
        "created_at",
    )
    list_filter = ("thoi_gian", "created_at", "nha_may", "ca_truc")
    search_fields = (
        "noi_dung",
        "ca_truc",
        "nguoi_tao__email",
        "nguoi_tao__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    )
    readonly_fields = (
        "nguoi_tao",
        "chu_ky_nguoi_tao",
        "created_at",
        "updated_at",
    )
    exclude = ("chu_ky_nguoi_tao",)

    def co_chu_ky(self, obj):
        return bool(obj.chu_ky_nguoi_tao)

    co_chu_ky.boolean = True
    co_chu_ky.short_description = "Có chữ ký"


@admin.register(SoBCHCSongHinh)
class SoBCHCSongHinhAdmin(admin.ModelAdmin):
    list_display = (
        "ngay_dong_bo",
        "nha_may",
        "muc_nuoc_quy_trinh",
        "muc_nuoc_ho",
        "luu_luong_ve_ho",
        "luu_luong_xa_tran",
        "luu_luong_chay_may",
        "luu_luong_chay_may_qt",
        "nguoi_dong_bo",
        "co_chu_ky",
        "created_at",
    )
    list_filter = ("ngay_dong_bo", "created_at", "nha_may")
    search_fields = (
        "nguyen_nhan_khong_dap_ung",
        "nguoi_dong_bo__email",
        "nguoi_dong_bo__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    )
    readonly_fields = (
        "nguoi_dong_bo",
        "chu_ky_nguoi_dong_bo",
        "created_at",
        "updated_at",
    )
    exclude = ("chu_ky_nguoi_dong_bo",)

    def co_chu_ky(self, obj):
        return bool(obj.chu_ky_nguoi_dong_bo)

    co_chu_ky.boolean = True
    co_chu_ky.short_description = "Có chữ ký"


@admin.register(SoAnToanDauGio)
class SoAnToanDauGioAdmin(admin.ModelAdmin):
    list_display = (
        "ngay_dong_bo",
        "ca_truc",
        "nha_may",
        "tinh_trang_an_toan",
        "nguoi_dong_bo",
        "co_chu_ky",
        "created_at",
    )
    list_filter = ("ngay_dong_bo", "ca_truc", "created_at", "nha_may")
    search_fields = (
        "tinh_trang_an_toan",
        "nguoi_dong_bo__email",
        "nguoi_dong_bo__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    )
    readonly_fields = (
        "nguoi_dong_bo",
        "chu_ky_nguoi_dong_bo",
        "created_at",
        "updated_at",
    )
    exclude = ("chu_ky_nguoi_dong_bo",)
    date_hierarchy = "ngay_dong_bo"

    def co_chu_ky(self, obj):
        return bool(obj.chu_ky_nguoi_dong_bo)

    co_chu_ky.boolean = True
    co_chu_ky.short_description = "Có chữ ký"


@admin.register(MauChuyenDoiThietBi)
class MauChuyenDoiThietBiAdmin(
    SafeExportChangeListMixin,
    XLSXOnlyMixin,
    ImportExportModelAdmin,
):
    resource_class = MauChuyenDoiThietBiResource
    list_display = (
        "nha_may",
        "to_may",
        "nhom_thiet_bi",
        "thiet_bi",
        "thu_tu",
        "dang_su_dung",
    )
    list_filter = ("nha_may", "to_may", "dang_su_dung")
    search_fields = (
        "nhom_thiet_bi",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    )
    autocomplete_fields = ("thiet_bi",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(LanChuyenDoiThietBi)
class LanChuyenDoiThietBiAdmin(admin.ModelAdmin):
    list_display = ("so", "thoi_gian", "nguoi_thuc_hien", "created_at")
    list_filter = ("thoi_gian", "created_at", "so__nha_may")
    search_fields = (
        "ghi_chu_chung",
        "nguoi_thuc_hien__email",
        "nguoi_thuc_hien__username",
    )
    readonly_fields = ("nguoi_thuc_hien", "created_at", "updated_at")
    inlines = [ChiTietChuyenDoiThietBiInline]


@admin.register(SoChuyenDoiThietBiTuan)
class SoChuyenDoiThietBiTuanAdmin(admin.ModelAdmin):
    list_display = ("nam", "tuan", "ca_truc", "tuan_bat_dau", "tuan_ket_thuc", "nha_may", "nguoi_tao", "created_at")
    list_filter = ("nam", "tuan", "ca_truc", "nha_may", "created_at")
    search_fields = (
        "nguoi_tao__email",
        "nguoi_tao__username",
        "ca_truc",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    )
    readonly_fields = ("nguoi_tao", "created_at", "updated_at")
    inlines = [LanChuyenDoiThietBiInline]


@admin.register(MauChuyenDoiTBThang)
class MauChuyenDoiTBThangAdmin(
    SafeExportChangeListMixin,
    XLSXOnlyMixin,
    ImportExportModelAdmin,
):
    resource_class = MauChuyenDoiTBThangResource
    list_display = (
        "nha_may",
        "ma_nhom",
        "ten_nhom",
        "don_vi_nhom",
        "thiet_bi",
        "don_vi",
        "thu_tu_nhom",
        "thu_tu",
        "dang_su_dung",
    )
    list_filter = ("nha_may", "ma_nhom", "dang_su_dung")
    search_fields = (
        "ma_nhom",
        "ten_nhom",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    )
    autocomplete_fields = ("thiet_bi",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ChiTietChuyenDoiTBThang)
class ChiTietChuyenDoiTBThangAdmin(
    SafeExportChangeListMixin,
    XLSXOnlyMixin,
    ImportExportModelAdmin,
):
    resource_class = ChiTietChuyenDoiTBThangResource
    list_display = (
        "so",
        "thiet_bi",
        "ma_nhom",
        "ten_nhom",
        "don_vi",
        "dau_thang",
        "cuoi_thang",
        "thuc_hien",
        "thu_tu",
    )
    list_filter = ("so__nam", "so__thang", "so__ca_truc", "so__nha_may", "ma_nhom")
    search_fields = (
        "ma_nhom",
        "ten_nhom",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "so__nha_may__ma_nha_may",
        "so__nha_may__ten_nha_may",
    )
    autocomplete_fields = ("so", "thiet_bi")
    readonly_fields = ("thuc_hien", "created_at", "updated_at")


@admin.register(SoChuyenDoiTBThang)
class SoChuyenDoiTBThangAdmin(
    SafeExportChangeListMixin,
    XLSXOnlyMixin,
    ImportExportModelAdmin,
):
    resource_class = SoChuyenDoiTBThangResource
    list_display = ("nam", "thang", "ca_truc", "thang_bat_dau", "thang_ket_thuc", "nha_may", "nguoi_tao", "created_at")
    list_filter = ("nam", "thang", "ca_truc", "nha_may", "created_at")
    search_fields = (
        "nguoi_tao__email",
        "nguoi_tao__username",
        "ca_truc",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    )
    readonly_fields = ("nguoi_tao", "created_at", "updated_at")
    inlines = [ChiTietChuyenDoiTBThangInline]
