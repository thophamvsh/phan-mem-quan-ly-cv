from django.conf import settings
from django.db import models
from .base import TimestampedUUIDModel, _lay_chu_ky_profile

class SoAnToanDauGio(TimestampedUUIDModel):
    class CaTruc(models.TextChoices):
        CA_NGAY = "ca_ngay", "Ca ngày"
        CA_DEM = "ca_dem", "Ca đêm"

    ngay_dong_bo = models.DateField()
    ca_truc = models.CharField(
        max_length=10,
        choices=CaTruc.choices,
        default=CaTruc.CA_NGAY,
    )
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_an_toan_dau_gio",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    tinh_trang_an_toan = models.CharField(max_length=255, blank=True)
    nguoi_dong_bo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_an_toan_dau_gio_da_dong_bo",
        null=True,
        blank=True,
    )
    chu_ky_nguoi_dong_bo = models.ImageField(
        upload_to="operations/so_an_toan_dau_gio/chu_ky/nguoi_dong_bo/",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-ngay_dong_bo", "-ca_truc", "-created_at"]
        unique_together = ["ngay_dong_bo", "ca_truc"]
        verbose_name = "Sổ an toàn đầu giờ"
        verbose_name_plural = "Sổ an toàn đầu giờ"

    def dong_bo_chu_ky_tu_user(self):
        if self.nguoi_dong_bo_id and not self.chu_ky_nguoi_dong_bo:
            chu_ky = _lay_chu_ky_profile(self.nguoi_dong_bo)
            self.chu_ky_nguoi_dong_bo = chu_ky.name if chu_ky else None

    def save(self, *args, **kwargs):
        self.dong_bo_chu_ky_tu_user()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"So An Toan Dau Gio {self.ngay_dong_bo:%Y-%m-%d}"
