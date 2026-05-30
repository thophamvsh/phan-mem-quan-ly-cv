from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .base import TimestampedUUIDModel, _lay_chu_ky_profile

class Sonhatkyvanhanh(TimestampedUUIDModel):
    class TrangThai(models.TextChoices):
        CHO_XAC_NHAN = "cho_xac_nhan", "Chờ xác nhận"
        HOAN_THANH = "hoan_thanh", "Hoàn thành"

    thoi_gian_tao = models.DateTimeField(default=timezone.now)
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_nhat_ky_van_hanh",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    noi_dung_tao = models.TextField()
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_nhat_ky_van_hanh_da_tao",
        null=True,
        blank=True,
    )
    nguoi_xac_nhan = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_nhat_ky_van_hanh_da_xac_nhan",
        null=True,
        blank=True,
    )
    chu_ky_nguoi_tao = models.ImageField(
        upload_to="operations/so_nhat_ky_van_hanh/chu_ky/nguoi_tao/",
        null=True,
        blank=True,
    )
    chu_ky_nguoi_xac_nhan = models.ImageField(
        upload_to="operations/so_nhat_ky_van_hanh/chu_ky/nguoi_xac_nhan/",
        null=True,
        blank=True,
    )
    xac_nhan_at = models.DateTimeField(null=True, blank=True)
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHO_XAC_NHAN,
    )

    class Meta:
        ordering = ["-thoi_gian_tao", "-created_at"]
        verbose_name = "Sổ nhật ký vận hành"
        verbose_name_plural = "Sổ nhật ký vận hành"

    @property
    def da_hoan_thanh(self):
        return bool(self.nguoi_xac_nhan_id and self.xac_nhan_at)

    def clean(self):
        if self.nguoi_tao_id and self.nguoi_tao_id == self.nguoi_xac_nhan_id:
            raise ValidationError({"nguoi_xac_nhan": "Nguoi xac nhan phai khac nguoi tao."})

    def dong_bo_chu_ky_tu_user(self):
        if self.nguoi_tao_id and not self.chu_ky_nguoi_tao:
            chu_ky = _lay_chu_ky_profile(self.nguoi_tao)
            self.chu_ky_nguoi_tao = chu_ky.name if chu_ky else None

        if self.xac_nhan_at and self.nguoi_xac_nhan_id and not self.chu_ky_nguoi_xac_nhan:
            chu_ky = _lay_chu_ky_profile(self.nguoi_xac_nhan)
            self.chu_ky_nguoi_xac_nhan = chu_ky.name if chu_ky else None
        elif not self.xac_nhan_at:
            self.chu_ky_nguoi_xac_nhan = None

    def save(self, *args, **kwargs):
        self.dong_bo_chu_ky_tu_user()
        self.full_clean()
        self.trang_thai = (
            self.TrangThai.HOAN_THANH if self.da_hoan_thanh else self.TrangThai.CHO_XAC_NHAN
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Sổ nhật ký vận hành - {self.thoi_gian_tao}"


class SonhatkyvanhanhDiesel(TimestampedUUIDModel):
    thoi_gian = models.DateTimeField(default=timezone.now)
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_nhat_ky_van_hanh_diesel",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    noi_dung = models.TextField(blank=True)
    i = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="I (A)")
    u = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="U (V)")
    f = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="F (Hz)")
    i_sac = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="I sạc (A)")
    u_sac = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="U sạc (V)")
    p = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="P (KW)")
    q = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Q (KVAr)")
    chi_so_gio_vh = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    t_may = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="T máy (C)")
    muc_dau = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Mức dầu (lit)")
    ap_luc_dau = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ca_truc = models.CharField(max_length=50, blank=True)
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_nhat_ky_van_hanh_diesel_da_tao",
        null=True,
        blank=True,
    )
    chu_ky_nguoi_tao = models.ImageField(
        upload_to="operations/so_nhat_ky_van_hanh_diesel/chu_ky/nguoi_tao/",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-thoi_gian", "-created_at"]
        verbose_name = "Sổ nhật ký vận hành Diesel"
        verbose_name_plural = "Sổ nhật ký vận hành Diesel"

    def dong_bo_chu_ky_tu_user(self):
        if self.nguoi_tao_id and not self.chu_ky_nguoi_tao:
            chu_ky = _lay_chu_ky_profile(self.nguoi_tao)
            self.chu_ky_nguoi_tao = chu_ky.name if chu_ky else None

    def save(self, *args, **kwargs):
        self.dong_bo_chu_ky_tu_user()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Diesel {self.thoi_gian:%Y-%m-%d %H:%M}"
