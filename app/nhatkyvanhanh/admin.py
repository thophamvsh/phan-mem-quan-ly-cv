from django.contrib import admin

from .models import (
    ChiTietSoGiaoNhanCaHC,
    ChiTietSoGiaoNhanCaVH,
    DienBienSuKien,
    KhacPhucSuKien,
    NguoiTrucSoGiaoNhanCaHC,
    SuKien,
    SogiaonhancaHC,
    SogiaonhancaVH,
)


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


@admin.register(SuKien)
class SuKienAdmin(admin.ModelAdmin):
    list_display = (
        "ten_he_thong_thiet_bi",
        "thoi_gian_xay_ra",
        "trang_thai",
        "ben_ghi_nhan_su_kien",
        "nguoi_tao",
        "created_at",
    )
    list_filter = ("trang_thai", "thoi_gian_xay_ra", "created_at")
    search_fields = (
        "ten_he_thong_thiet_bi",
        "hien_tuong_dien_bien",
        "bao_cho",
        "ben_ghi_nhan_su_kien__email",
        "nguoi_tao__email",
    )
    readonly_fields = (
        "chu_ky_ben_ghi_nhan_su_kien",
        "created_at",
        "updated_at",
    )
    exclude = ("chu_ky_ben_ghi_nhan_su_kien",)
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
