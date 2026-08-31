from django.contrib import admin

from .models import ChiTietPhuongAnPhanCongCa, DieuChinhNhanSuCaTruc, KipTruc, LichSuLichTruc, LichTrucCa, MauChuKyCaTruc, NgayTrucCa, NhanSu, NhomLichTruc, PhamViNhanSuCaTruc, PhuongAnPhanCongCa, ThanhVienKipTruc


@admin.register(NhanSu)
class NhanSuAdmin(admin.ModelAdmin):
    list_display = ("ho_ten", "ma_nhan_vien", "don_vi", "bo_phan", "chuc_danh", "user", "dang_lam_viec")
    list_filter = ("don_vi", "bo_phan", "dang_lam_viec")
    search_fields = ("ho_ten", "ma_nhan_vien", "chuc_danh", "user__username")


@admin.register(NhomLichTruc)
class NhomLichTrucAdmin(admin.ModelAdmin):
    list_display = ("ma_nhom", "ten_nhom", "nha_may", "don_vi", "bo_phan", "dia_diem", "dang_hoat_dong")
    list_filter = ("nha_may", "don_vi", "bo_phan", "dang_hoat_dong")
    search_fields = ("ma_nhom", "ten_nhom", "dia_diem")


@admin.register(PhamViNhanSuCaTruc)
class PhamViNhanSuCaTrucAdmin(admin.ModelAdmin):
    list_display = ("nhom_lich", "nhan_su", "tu_ngay", "den_ngay", "dang_hoat_dong")
    list_filter = ("nhom_lich", "dang_hoat_dong")


class ThanhVienInline(admin.TabularInline):
    model = ThanhVienKipTruc
    extra = 0


@admin.register(KipTruc)
class KipTrucAdmin(admin.ModelAdmin):
    list_display = ("ten_kip", "ma_kip", "loai_kip", "nha_may", "dang_hoat_dong")
    list_filter = ("loai_kip", "nha_may", "dang_hoat_dong")
    search_fields = ("ten_kip", "ma_kip", "nha_may__ten_nha_may")
    inlines = [ThanhVienInline]


@admin.register(ThanhVienKipTruc)
class ThanhVienKipTrucAdmin(admin.ModelAdmin):
    list_display = (
        "nhan_su_hien_thi",
        "kip_truc",
        "nha_may_hien_thi",
        "vai_tro",
        "tu_ngay",
        "den_ngay",
        "dang_hoat_dong",
    )
    list_filter = (
        "kip_truc__nha_may",
        "kip_truc__nhom_lich",
        "kip_truc",
        "vai_tro",
        "dang_hoat_dong",
    )
    search_fields = (
        "nhan_su__ho_ten",
        "nhan_su__ma_nhan_vien",
        "user__username",
        "kip_truc__ma_kip",
        "kip_truc__ten_kip",
    )
    list_select_related = ("kip_truc", "kip_truc__nha_may", "nhan_su", "user")

    @admin.display(description="Nhân sự", ordering="nhan_su__ho_ten")
    def nhan_su_hien_thi(self, obj):
        return obj.nhan_su or obj.user

    @admin.display(description="Nhà máy", ordering="kip_truc__nha_may__ma_nha_may")
    def nha_may_hien_thi(self, obj):
        return obj.kip_truc.nha_may


@admin.register(MauChuKyCaTruc)
class MauChuKyAdmin(admin.ModelAdmin):
    list_display = ("ten_mau", "nha_may", "phien_ban", "tu_ngay", "dang_hoat_dong")
    list_filter = ("nha_may", "dang_hoat_dong")


class NgayTrucInline(admin.TabularInline):
    model = NgayTrucCa
    extra = 0
    fields = ("ngay", "kip_ca_ngay", "kip_ca_dem", "kip_hanh_chinh", "da_dieu_chinh", "ghi_chu")


@admin.register(LichTrucCa)
class LichTrucCaAdmin(admin.ModelAdmin):
    list_display = ("nha_may", "thang", "nam", "phien_ban", "trang_thai", "nguoi_tao", "nguoi_duyet")
    list_filter = ("trang_thai", "nha_may", "nam", "thang")
    search_fields = ("nha_may__ten_nha_may", "nguoi_tao__username")
    readonly_fields = ("nguoi_tao", "nguoi_duyet", "ngay_gui_duyet", "ngay_duyet", "snapshot_nhan_su")
    inlines = [NgayTrucInline]


admin.site.register(LichSuLichTruc)


class ChiTietPhuongAnInline(admin.TabularInline):
    model = ChiTietPhuongAnPhanCongCa
    extra = 0


@admin.register(PhuongAnPhanCongCa)
class PhuongAnPhanCongCaAdmin(admin.ModelAdmin):
    list_display = ("nha_may", "thang", "nam", "phien_ban", "ngay_hieu_luc", "trang_thai")
    list_filter = ("nha_may", "nam", "thang", "trang_thai")
    inlines = [ChiTietPhuongAnInline]


@admin.register(DieuChinhNhanSuCaTruc)
class DieuChinhNhanSuCaTrucAdmin(admin.ModelAdmin):
    list_display = ("ngay_truc", "loai_ca", "loai_dieu_chinh", "nhan_su_vang", "nhan_su_thay", "trang_thai")
    list_filter = ("loai_ca", "loai_dieu_chinh", "trang_thai")
    search_fields = ("nhan_su_vang__ho_ten", "nhan_su_thay__ho_ten", "ly_do")
    readonly_fields = ("nguoi_tao", "nguoi_duyet", "ngay_duyet")
