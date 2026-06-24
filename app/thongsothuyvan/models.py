from django.conf import settings
from django.db import models


class BaseThuyVan(models.Model):
    Mucnuoc = models.DecimalField(max_digits=10, decimal_places=2)
    dungtich = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SonghinhMnh(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Sông Hinh Mnh"
        verbose_name_plural = "Sông Hinh Mnh"


class ThuongKonTumMnh(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Thượng Kon Tum Mnh"
        verbose_name_plural = "Thượng Kon Tum Mnh"


class Vinhson_HoA(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Vĩnh Sơn - Hồ A"
        verbose_name_plural = "Vĩnh Sơn - Hồ A"


class Vinhson_HoB(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Vĩnh Sơn - Hồ B"
        verbose_name_plural = "Vĩnh Sơn - Hồ B"


class Vinhson_Hoc(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Vĩnh Sơn - Hồ C"
        verbose_name_plural = "Vĩnh Sơn - Hồ C"

class RealtimeUpdateState(models.Model):
    auto_update_enabled = models.BooleanField(default=False)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_hourly_slot = models.DateTimeField(null=True, blank=True)
    last_saved_at = models.DateTimeField(null=True, blank=True)
    last_manual_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trang thai cap nhat realtime"
        verbose_name_plural = "Trang thai cap nhat realtime"

    @classmethod
    def get_solo(cls):
        state, _ = cls.objects.get_or_create(pk=1)
        return state


class SongHinhRealtimeSnapshot(models.Model):
    time_stamp = models.DateTimeField()
    mntl = models.FloatField()
    mnhl = models.FloatField()
    ph1 = models.FloatField()
    ph2 = models.FloatField()
    pnm = models.FloatField()
    qcm = models.FloatField()
    dm1 = models.FloatField()
    dm2 = models.FloatField()
    dm3 = models.FloatField()
    dm4 = models.FloatField()
    dm5 = models.FloatField()
    dm6 = models.FloatField()
    qtran = models.FloatField()
    dung_tich_ho = models.FloatField(null=True, blank=True)
    dung_tich_phong_lu = models.FloatField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-time_stamp"]
        verbose_name = "Realtime Song Hinh"
        verbose_name_plural = "Realtime Song Hinh"


class VinhSonRealtimeSnapshot(models.Model):
    time_stamp = models.DateTimeField()
    mntla = models.FloatField()
    mntla_td = models.FloatField(null=True, blank=True)
    mntlb = models.FloatField()
    mntlc = models.FloatField()
    mnhl = models.FloatField()
    ph1 = models.FloatField()
    ph2 = models.FloatField()
    qcm = models.FloatField()
    qtran = models.FloatField()
    dung_tich_ho_a = models.FloatField(null=True, blank=True)
    dung_tich_ho_b = models.FloatField(null=True, blank=True)
    dung_tich_ho_c = models.FloatField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-time_stamp"]
        verbose_name = "Realtime Vinh Son"
        verbose_name_plural = "Realtime Vinh Son"


class ThongsoSanxuat(models.Model):
    nha_may = models.CharField(max_length=50, default='songhinh')
    thoi_gian = models.DateTimeField()

    # Các cột từ C đến X (trừ E)
    cot_c = models.CharField(verbose_name="Hồ chứa", max_length=100, null=True, blank=True)
    cot_d = models.FloatField(verbose_name="Mực nước kế hoạch", null=True, blank=True)
    # Bỏ qua cột E theo yêu cầu
    cot_f = models.FloatField(verbose_name="Mực nước chết (m)", null=True, blank=True)
    cot_g = models.FloatField(verbose_name="Mực nước thượng lưu (m)", null=True, blank=True)
    cot_h = models.FloatField(verbose_name="Dung tích hữu ích (tr.m3)", null=True, blank=True)
    cot_i = models.FloatField(verbose_name="Lưu lượng nước về Qv (m3/s)", null=True, blank=True)
    cot_j = models.FloatField(verbose_name="Lưu lượng qua máy Qcm (m3/s)", null=True, blank=True)
    cot_k = models.FloatField(verbose_name="Lưu lượng xả lũ Qxl (m3/s)", null=True, blank=True)
    cot_l = models.FloatField(verbose_name="Sản lượng Qc ngày", null=True, blank=True)
    cot_m = models.FloatField(verbose_name="Đầu cực ngày", null=True, blank=True)
    cot_n = models.FloatField(verbose_name="Thương phẩm ngày", null=True, blank=True)
    cot_o = models.FloatField(verbose_name="Sản lượng Qc Ao giao tháng", null=True, blank=True)
    cot_p = models.FloatField(verbose_name="Sản lượng Qc lũy kế tháng", null=True, blank=True)
    cot_q = models.FloatField(verbose_name="Đầu cực tháng", null=True, blank=True)
    cot_r = models.FloatField(verbose_name="Thương phẩm tháng", null=True, blank=True)
    cot_s = models.FloatField(verbose_name="Sản lượng Qc năm Ao giao", null=True, blank=True)
    cot_t = models.FloatField(verbose_name="Sản lượng Qc lũy kế năm", null=True, blank=True)
    cot_u = models.FloatField(verbose_name="Đầu cực năm", null=True, blank=True)
    cot_v = models.FloatField(verbose_name="Thương phẩm năm", null=True, blank=True)
    cot_w = models.FloatField(verbose_name="Sản lượng kế hoạch năm", null=True, blank=True)
    cot_x = models.FloatField(verbose_name="Sản lượng tự dùng ngày", null=True, blank=True)
    sanluong_kh_thang = models.FloatField(verbose_name="Sản lượng kế hoạch tháng", null=True, blank=True)
    mucnuoc_gioihan_tuan = models.FloatField(verbose_name="Mực nước giới hạn tuần", null=True, blank=True)
    mucnuoc_gioihan_tuan_ho_a = models.FloatField(verbose_name="Mực nước giới hạn tuần hồ A", null=True, blank=True)
    mucnuoc_gioihan_tuan_ho_b = models.FloatField(verbose_name="Mực nước giới hạn tuần hồ B", null=True, blank=True)
    mucnuoc_thuongluu_ho_b = models.FloatField(verbose_name="Mực nước thượng lưu hồ B (m)", null=True, blank=True)
    mucnuoc_thuongluu_ho_c = models.FloatField(verbose_name="Mực nước thượng lưu hồ C (m)", null=True, blank=True)
    luuluong_ve_ho_b = models.FloatField(verbose_name="Lưu lượng nước về hồ B (m3/s)", null=True, blank=True)
    luuluong_ve_ho_c = models.FloatField(verbose_name="Lưu lượng nước về hồ C (m3/s)", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thongsosanxuat_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thongsosanxuat_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-thoi_gian"]
        unique_together = ('thoi_gian', 'nha_may')
        indexes = [
            models.Index(fields=["nha_may", "-thoi_gian"], name="tsx_plant_time_desc_idx"),
        ]
        verbose_name = "Thông số sản xuất"
        verbose_name_plural = "Thông số sản xuất"


class ThongSoThuyVanCaiDat(models.Model):
    LOAI_KE_HOACH_NAM = "annual"
    LOAI_KE_HOACH_THANG = "monthly"
    LOAI_MNGH_TUAN = "weekly"
    LOAI_CHOICES = (
        (LOAI_KE_HOACH_NAM, "Ke hoach nam"),
        (LOAI_KE_HOACH_THANG, "Ke hoach thang"),
        (LOAI_MNGH_TUAN, "MNGH tuan"),
    )

    nha_may = models.CharField(max_length=50, default="songhinh")
    nam = models.PositiveIntegerField()
    loai = models.CharField(max_length=20, choices=LOAI_CHOICES)
    thang = models.PositiveSmallIntegerField(default=0)
    tuan = models.PositiveSmallIntegerField(default=0)
    tuan_bat_dau = models.DateField(null=True, blank=True)
    tuan_ket_thuc = models.DateField(null=True, blank=True)
    sanluong_kehoach_nam = models.FloatField(null=True, blank=True)
    sanluong_kehoach_thang = models.FloatField(null=True, blank=True)
    mucnuoc_gioihan_tuan = models.FloatField(null=True, blank=True)
    mucnuoc_gioihan_tuan_ho_a = models.FloatField(null=True, blank=True)
    mucnuoc_gioihan_tuan_ho_b = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thongsothuyvancaidat_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thongsothuyvancaidat_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nha_may", "nam", "loai", "thang", "tuan"]
        unique_together = ("nha_may", "nam", "loai", "thang", "tuan")
        verbose_name = "Thong so thuy van cai dat"
        verbose_name_plural = "Thong so thuy van cai dat"

    def __str__(self):
        scope = self.loai
        if self.thang:
            scope = f"{scope} thang {self.thang}"
        if self.tuan:
            scope = f"{scope} tuan {self.tuan}"
        return f"{self.nha_may} {self.nam} {scope}"


class MucnuocQuytrinh(models.Model):
    nha_may = models.CharField(max_length=50, default="songhinh")
    ngay_bat_dau = models.CharField(
        verbose_name="Ngày bắt đầu",
        max_length=5,
        help_text="Định dạng dd/MM, áp dụng cho tất cả các năm",
    )
    ngay_ket_thuc = models.CharField(
        verbose_name="Ngày kết thúc",
        max_length=5,
        help_text="Định dạng dd/MM, áp dụng cho tất cả các năm",
    )
    muc_nuoc_bat_dau = models.FloatField(verbose_name="Mực nước hồ từ")
    muc_nuoc_ket_thuc = models.FloatField(verbose_name="Mực nước hồ kết thúc")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mucnuocquytrinh_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="mucnuocquytrinh_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ngay_bat_dau", "ngay_ket_thuc"]
        unique_together = ("nha_may", "ngay_bat_dau", "ngay_ket_thuc")
        verbose_name = "Mực nước quy trình"
        verbose_name_plural = "Mực nước quy trình"

    def __str__(self):
        return (
            f"{self.nha_may} {self.ngay_bat_dau} - {self.ngay_ket_thuc}: "
            f"{self.muc_nuoc_bat_dau} - {self.muc_nuoc_ket_thuc}"
        )


class ThongsoGioPhat(models.Model):
    nha_may = models.CharField(max_length=50, default='songhinh')
    ngay = models.DateField()
    to_may = models.IntegerField()
    gio_phat_dien = models.FloatField(null=True, blank=True)
    gio_ngung = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thongsogiophat_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thongsogiophat_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ngay", "to_may"]
        unique_together = ('ngay', 'to_may', 'nha_may')
        indexes = [
            models.Index(fields=["nha_may", "ngay"], name="tgp_plant_day_idx"),
        ]
        verbose_name = "Thông số giờ phát"
        verbose_name_plural = "Thông số giờ phát"


class ThongSoThuyVanThucTe(models.Model):
    nha_may = models.CharField(max_length=50)
    ngay = models.DateField()
    muc_nuoc_ho = models.FloatField(null=True, blank=True)
    qve = models.FloatField(null=True, blank=True)
    muc_nuoc_ho_a = models.FloatField(null=True, blank=True)
    muc_nuoc_ho_b = models.FloatField(null=True, blank=True)
    muc_nuoc_ho_c = models.FloatField(null=True, blank=True)
    qve_ho_a = models.FloatField(null=True, blank=True)
    qve_ho_b = models.FloatField(null=True, blank=True)
    qve_ho_c = models.FloatField(null=True, blank=True)
    qve_tong = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thongsothuyvanthucte_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="thongsothuyvanthucte_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ngay", "nha_may"]
        unique_together = ("nha_may", "ngay")
        indexes = [
            models.Index(fields=["nha_may", "-ngay"], name="tstt_plant_day_desc_idx"),
        ]
        verbose_name = "Thủy văn theo dõi"
        verbose_name_plural = "Thủy văn theo dõi"

    def __str__(self):
        return f"{self.nha_may} {self.ngay}"


class TramDoMuaVrain(models.Model):
    Thoi_gian = models.DateTimeField(verbose_name="Thời gian")
    Xa_Ea_M_doan = models.FloatField(verbose_name="Xã Ea M'đoan", null=True, blank=True)
    Thon_10_Xa_Ea_M_Doal = models.FloatField(verbose_name="Thôn 10 - Xã Ea M'Doal", null=True, blank=True)
    UBND_xa_Song_Hinh = models.FloatField(verbose_name="UBND xã Sông Hinh", null=True, blank=True)
    Cu_Kroa = models.FloatField(verbose_name="Cư Kroa", null=True, blank=True)
    Xa_Ea_Trang = models.FloatField(verbose_name="Xã Ea Trang", null=True, blank=True)
    Dap_Tran = models.FloatField(verbose_name="Đập Tràn", null=True, blank=True)
    Ho_B_TD_Vinh_Son = models.FloatField(verbose_name="Hồ B - TĐ Vĩnh Sơn", null=True, blank=True)
    Ho_A_TD_Vinh_Son = models.FloatField(verbose_name="Hồ A - TĐ Vĩnh Sơn", null=True, blank=True)
    Ho_C_TD_Vinh_Son = models.FloatField(verbose_name="Hồ C - TĐ Vĩnh Sơn", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-Thoi_gian"]
        verbose_name = "Trạm đo mưa Vrain"
        verbose_name_plural = "Trạm đo mưa Vrain"
