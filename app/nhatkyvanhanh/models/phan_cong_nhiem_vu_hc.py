from django.conf import settings
from django.db import models
from .base import TimestampedUUIDModel, _current_year


class BangPhanCongNhiemVuHC(TimestampedUUIDModel):
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.PROTECT,
        related_name="bang_phan_cong_nhiem_vu_hc",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    thang = models.PositiveSmallIntegerField(verbose_name="Tháng")
    nam = models.PositiveSmallIntegerField(default=_current_year, verbose_name="Năm")
    tieu_de = models.CharField(max_length=255, blank=True, verbose_name="Tiêu đề")
    ngay_lap = models.DateField(null=True, blank=True, verbose_name="Ngày lập")
    dia_diem_lap = models.CharField(max_length=255, blank=True, verbose_name="Địa điểm lập")
    ghi_chu = models.TextField(blank=True, verbose_name="Ghi chú / Hướng dẫn")
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bang_phan_cong_nhiem_vu_hc_da_tao",
        null=True,
        blank=True,
        verbose_name="Người tạo",
    )

    class Meta:
        ordering = ["-nam", "-thang", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "nam", "thang"],
                name="uq_bang_phan_cong_hc_nha_may_nam_thang",
            )
        ]
        verbose_name = "Bảng phân công nhiệm vụ ca HC"
        verbose_name_plural = "Bảng phân công nhiệm vụ ca HC"

    def __str__(self):
        plant_name = self.nha_may.ten_nha_may if self.nha_may else "Chung"
        return f"{plant_name} - Tháng {self.thang:02d}/{self.nam}"


class ChiTietNhiemVuThuTrongTuan(TimestampedUUIDModel):
    bang_phan_cong = models.ForeignKey(
        BangPhanCongNhiemVuHC,
        on_delete=models.CASCADE,
        related_name="chi_tiets",
        verbose_name="Bảng phân công",
    )
    stt = models.PositiveSmallIntegerField(default=1, verbose_name="STT")
    thu = models.CharField(max_length=20, verbose_name="Thứ trong tuần")
    noi_dung_nhiem_vu = models.TextField(blank=True, verbose_name="Khu vực / Nội dung nhiệm vụ")

    class Meta:
        ordering = ["stt", "id"]
        verbose_name = "Chi tiết nhiệm vụ thứ trong tuần"
        verbose_name_plural = "Chi tiết nhiệm vụ thứ trong tuần"

    def __str__(self):
        return f"{self.thu} - {self.bang_phan_cong}"