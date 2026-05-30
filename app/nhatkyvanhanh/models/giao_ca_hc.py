from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .base import TimestampedUUIDModel, _lay_chu_ky_profile

class SogiaonhancaHC(TimestampedUUIDModel):
    class TrangThai(models.TextChoices):
        CHO_XAC_NHAN = "cho_xac_nhan", "Chờ xác nhận"
        HOAN_THANH = "hoan_thanh", "Hoàn thành"

    ngay_truc = models.DateField()
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_hc",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    dia_diem = models.CharField(max_length=255, blank=True)
    nguoi_truc = models.CharField(max_length=255, blank=True)
    nguoi_truc_2 = models.CharField(max_length=255, blank=True)
    nguoi_truc_3 = models.CharField(max_length=255, blank=True)
    thoi_gian_bat_dau_ca = models.DateTimeField(null=True, blank=True)
    thoi_gian_giao_ca = models.DateTimeField()
    luu_y = models.TextField(blank=True)
    chu_ky_user_giao_ca = models.ImageField(
        upload_to="operations/so_giao_nhan_ca_hc/chu_ky/giao_ca/",
        null=True,
        blank=True,
    )
    chu_ky_user_nhan_ca = models.ImageField(
        upload_to="operations/so_giao_nhan_ca_hc/chu_ky/nhan_ca/",
        null=True,
        blank=True,
    )
    user_giao_ca = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_hc_da_giao",
    )
    user_nhan_ca = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_hc_da_nhan",
        null=True,
        blank=True,
    )
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_hc_da_tao",
        null=True,
        blank=True,
    )
    giao_ca_ky_at = models.DateTimeField(null=True, blank=True)
    nhan_ca_ky_at = models.DateTimeField(null=True, blank=True)
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHO_XAC_NHAN,
    )

    class Meta:
        ordering = ["-ngay_truc", "-thoi_gian_bat_dau_ca", "-thoi_gian_giao_ca", "-created_at"]
        verbose_name = "Sổ giao nhận ca hành chính"
        verbose_name_plural = "Sổ giao nhận ca hành chính"

    @property
    def da_hoan_thanh(self):
        return bool(self.giao_ca_ky_at and self.nhan_ca_ky_at)

    def clean(self):
        if self.user_giao_ca_id and self.user_giao_ca_id == self.user_nhan_ca_id:
            raise ValidationError({"user_nhan_ca": "User nhan ca phai khac user giao ca."})
        if self.nguoi_tao_id and self.user_giao_ca_id and self.nguoi_tao_id != self.user_giao_ca_id:
            raise ValidationError({"user_giao_ca": "User tao so phai la user giao ca."})

    def dong_bo_chu_ky_tu_user(self):
        if self.giao_ca_ky_at and self.user_giao_ca_id and not self.chu_ky_user_giao_ca:
            chu_ky = _lay_chu_ky_profile(self.user_giao_ca)
            self.chu_ky_user_giao_ca = chu_ky.name if chu_ky else None
        elif not self.giao_ca_ky_at:
            self.chu_ky_user_giao_ca = None

        if self.nhan_ca_ky_at and self.user_nhan_ca_id and not self.chu_ky_user_nhan_ca:
            chu_ky = _lay_chu_ky_profile(self.user_nhan_ca)
            self.chu_ky_user_nhan_ca = chu_ky.name if chu_ky else None
        elif not self.nhan_ca_ky_at:
            self.chu_ky_user_nhan_ca = None

    def save(self, *args, **kwargs):
        self.dong_bo_chu_ky_tu_user()
        self.full_clean()
        self.trang_thai = (
            self.TrangThai.HOAN_THANH if self.da_hoan_thanh else self.TrangThai.CHO_XAC_NHAN
        )
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"So giao nhan ca hanh chinh - {self.ngay_truc}"


class NguoiTrucSoGiaoNhanCaHC(TimestampedUUIDModel):
    so_giao_nhan_ca = models.ForeignKey(
        SogiaonhancaHC,
        on_delete=models.CASCADE,
        related_name="nguoi_truc_chi_tiets",
    )
    thoi_gian = models.DateTimeField(default=timezone.now)
    ten_nguoi_truc = models.CharField(max_length=255)
    thu_tu = models.PositiveIntegerField(default=1)
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="nguoi_truc_so_giao_nhan_ca_hc_da_tao",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["thu_tu", "thoi_gian", "created_at"]
        verbose_name = "Người trực sổ giao nhận ca hành chính"
        verbose_name_plural = "Người trực sổ giao nhận ca hành chính"

    def __str__(self):
        return self.ten_nguoi_truc


class ChiTietSoGiaoNhanCaHC(TimestampedUUIDModel):
    so_giao_nhan_ca = models.ForeignKey(
        SogiaonhancaHC,
        on_delete=models.CASCADE,
        related_name="noi_dung_chi_tiets",
    )
    thoi_gian = models.DateTimeField(default=timezone.now)
    tieu_de = models.CharField(max_length=255, blank=True)
    noi_dung = models.TextField()
    thu_tu = models.PositiveIntegerField(default=1)
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chi_tiet_so_giao_nhan_ca_hc_da_tao",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["thu_tu", "thoi_gian", "created_at"]
        verbose_name = "Nội dung chi tiết sổ giao nhận ca hành chính"
        verbose_name_plural = "Nội dung chi tiết sổ giao nhận ca hành chính"

    def __str__(self):
        return self.tieu_de or f"Noi dung chi tiet HC {self.thu_tu}"
