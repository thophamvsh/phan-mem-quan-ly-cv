from django.conf import settings
from django.db import models
from .base import TimestampedUUIDModel, _lay_chu_ky_profile

class SoBCHCSongHinh(TimestampedUUIDModel):
    ngay_dong_bo = models.DateField(unique=True)
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_bchc_song_hinh",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    muc_nuoc_quy_trinh = models.CharField(max_length=50, blank=True)
    muc_nuoc_quy_trinh_tu = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    muc_nuoc_quy_trinh_den = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    muc_nuoc_ho = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    luu_luong_ve_ho = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    luu_luong_xa_tran = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    luu_luong_chay_may = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    luu_luong_chay_may_qt = models.CharField(max_length=50, blank=True)
    nguyen_nhan_khong_dap_ung = models.TextField(blank=True)
    nguoi_dong_bo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_bchc_song_hinh_da_dong_bo",
        null=True,
        blank=True,
    )
    chu_ky_nguoi_dong_bo = models.ImageField(
        upload_to="operations/so_bchc_song_hinh/chu_ky/nguoi_dong_bo/",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-ngay_dong_bo", "-created_at"]
        verbose_name = "Sổ BCHC Sông Hinh"
        verbose_name_plural = "Sổ BCHC Sông Hinh"

    def dong_bo_chu_ky_tu_user(self):
        if self.nguoi_dong_bo_id and not self.chu_ky_nguoi_dong_bo:
            chu_ky = _lay_chu_ky_profile(self.nguoi_dong_bo)
            self.chu_ky_nguoi_dong_bo = chu_ky.name if chu_ky else None

    def save(self, *args, **kwargs):
        self.dong_bo_chu_ky_tu_user()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"So BCHC Song Hinh {self.ngay_dong_bo:%Y-%m-%d}"
