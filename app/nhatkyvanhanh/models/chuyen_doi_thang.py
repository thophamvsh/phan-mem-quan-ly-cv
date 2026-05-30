from datetime import date
from calendar import monthrange
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .base import TimestampedUUIDModel, _current_year

class MauChuyenDoiTBThang(TimestampedUUIDModel):
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="mau_chuyen_doi_tb_thang",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    ma_nhom = models.CharField(max_length=20, blank=True)
    ten_nhom = models.CharField(max_length=255)
    don_vi_nhom = models.CharField(max_length=50, blank=True)
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="mau_chuyen_doi_tb_thang",
    )
    don_vi = models.CharField(max_length=50, default="Lan")
    thu_tu_nhom = models.PositiveIntegerField(default=1)
    thu_tu = models.PositiveIntegerField(default=1)
    dang_su_dung = models.BooleanField(default=True)

    class Meta:
        ordering = ["nha_may", "thu_tu_nhom", "thu_tu", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "thiet_bi"],
                name="uq_mau_chuyen_doi_tb_thang_nha_may_thiet_bi",
            )
        ]
        verbose_name = "Mẫu chuyển đổi TB tháng"
        verbose_name_plural = "Mẫu chuyển đổi TB tháng"

    def __str__(self):
        return f"{self.ten_nhom} - {self.thiet_bi}"


class SoChuyenDoiTBThang(TimestampedUUIDModel):
    class CaTruc(models.TextChoices):
        A = "A", "Ca A"
        B = "B", "Ca B"
        C = "C", "Ca C"
        D = "D", "Ca D"

    nam = models.PositiveSmallIntegerField(default=_current_year)
    thang = models.PositiveSmallIntegerField(default=1)
    ca_truc = models.CharField(max_length=1, choices=CaTruc.choices, default=CaTruc.A)
    thang_bat_dau = models.DateField()
    thang_ket_thuc = models.DateField()
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_chuyen_doi_tb_thang",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_chuyen_doi_tb_thang_da_tao",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-nam", "-thang", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "nam", "thang", "ca_truc"],
                name="uq_so_chuyen_doi_tb_thang_nha_may_nam_thang_ca",
            )
        ]
        verbose_name = "Sổ chuyển đổi TB tháng"
        verbose_name_plural = "Sổ chuyển đổi TB tháng"

    def _cap_nhat_khoang_thoi_gian_thang(self):
        if self.nam < 2000 or self.nam > 2100:
            raise ValidationError({"nam": "Nam khong hop le."})
        if self.thang < 1 or self.thang > 12:
            raise ValidationError({"thang": "Thang phai nam trong khoang 1-12."})
        self.thang_bat_dau = date(self.nam, self.thang, 1)
        self.thang_ket_thuc = date(self.nam, self.thang, monthrange(self.nam, self.thang)[1])

    def clean(self):
        self._cap_nhat_khoang_thoi_gian_thang()
        if self.thang_ket_thuc < self.thang_bat_dau:
            raise ValidationError({"thang_ket_thuc": "Thang ket thuc phai lon hon hoac bang thang bat dau."})

    def save(self, *args, **kwargs):
        self._cap_nhat_khoang_thoi_gian_thang()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Sổ chuyển đổi TB tháng {self.thang}/{self.nam} - Ca {self.ca_truc}"


class ChiTietChuyenDoiTBThang(TimestampedUUIDModel):
    so = models.ForeignKey(
        SoChuyenDoiTBThang,
        on_delete=models.CASCADE,
        related_name="chi_tiets",
    )
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="chi_tiet_chuyen_doi_tb_thang",
    )
    ma_nhom = models.CharField(max_length=20, blank=True)
    ten_nhom = models.CharField(max_length=255)
    don_vi_nhom = models.CharField(max_length=50, blank=True)
    don_vi = models.CharField(max_length=50, default="Lan")
    dau_thang = models.IntegerField(default=0)
    cuoi_thang = models.IntegerField(default=0)
    thuc_hien = models.IntegerField(default=0, editable=False)
    ghi_chu = models.TextField(blank=True)
    thu_tu_nhom = models.PositiveIntegerField(default=1)
    thu_tu = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["thu_tu_nhom", "thu_tu", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["so", "thiet_bi"],
                name="uq_chi_tiet_chuyen_doi_tb_thang_so_thiet_bi",
            )
        ]
        verbose_name = "Chi tiết chuyển đổi TB tháng"
        verbose_name_plural = "Chi tiết chuyển đổi TB tháng"

    def clean(self):
        self.thuc_hien = (self.cuoi_thang or 0) - (self.dau_thang or 0)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.thiet_bi} - {self.thuc_hien}"
