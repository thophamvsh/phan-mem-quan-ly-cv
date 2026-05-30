from datetime import date
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .base import TimestampedUUIDModel, _current_year

class MauChuyenDoiThietBi(TimestampedUUIDModel):
    class ToMay(models.TextChoices):
        H1 = "H1", "Tổ máy H1"
        H2 = "H2", "Tổ máy H2"
        TU_DUNG = "tu_dung", "Tự dùng"

    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="mau_chuyen_doi_thiet_bi",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    to_may = models.CharField(max_length=20, choices=ToMay.choices)
    nhom_thiet_bi = models.CharField(max_length=255, blank=True)
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="mau_chuyen_doi_thiet_bi",
    )
    thu_tu = models.PositiveIntegerField(default=1)
    dang_su_dung = models.BooleanField(default=True)

    class Meta:
        ordering = ["nha_may", "to_may", "thu_tu", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "thiet_bi"],
                name="uq_mau_chuyen_doi_thiet_bi_nha_may_thiet_bi",
            )
        ]
        verbose_name = "Mẫu chuyển đổi thiết bị"
        verbose_name_plural = "Mẫu chuyển đổi thiết bị"

    def __str__(self):
        return f"{self.get_to_may_display()} - {self.thiet_bi}"


class SoChuyenDoiThietBiTuan(TimestampedUUIDModel):
    class CaTruc(models.TextChoices):
        A = "A", "Ca A"
        B = "B", "Ca B"
        C = "C", "Ca C"
        D = "D", "Ca D"

    nam = models.PositiveSmallIntegerField(default=_current_year)
    tuan = models.PositiveSmallIntegerField(default=1)
    ca_truc = models.CharField(max_length=1, choices=CaTruc.choices, default=CaTruc.A)
    tuan_bat_dau = models.DateField()
    tuan_ket_thuc = models.DateField()
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_chuyen_doi_thiet_bi_tuan",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_chuyen_doi_thiet_bi_tuan_da_tao",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-nam", "-tuan", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "nam", "tuan", "ca_truc"],
                name="uq_so_chuyen_doi_thiet_bi_tuan_nha_may_nam_tuan_ca",
            )
        ]
        verbose_name = "Sổ chuyển đổi thiết bị tuần"
        verbose_name_plural = "Sổ chuyển đổi thiết bị tuần"

    def _cap_nhat_khoang_thoi_gian_tuan(self):
        if self.nam < 2000 or self.nam > 2100:
            raise ValidationError({"nam": "Nam khong hop le."})
        if self.tuan < 1 or self.tuan > 53:
            raise ValidationError({"tuan": "Tuan phai nam trong khoang 1-53."})
        try:
            week_start = date.fromisocalendar(self.nam, self.tuan, 1)
        except ValueError:
            raise ValidationError({"tuan": "Tuan khong hop le voi nam da chon."})
        self.tuan_bat_dau = week_start
        self.tuan_ket_thuc = date.fromisocalendar(self.nam, self.tuan, 7)

    def clean(self):
        self._cap_nhat_khoang_thoi_gian_tuan()
        if self.tuan_bat_dau and self.tuan_ket_thuc and self.tuan_ket_thuc < self.tuan_bat_dau:
            raise ValidationError({"tuan_ket_thuc": "Tuan ket thuc phai lon hon hoac bang tuan bat dau."})

    def save(self, *args, **kwargs):
        self._cap_nhat_khoang_thoi_gian_tuan()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Sổ chuyển đổi thiết bị tuần {self.tuan}/{self.nam} - Ca {self.ca_truc}"


class LanChuyenDoiThietBi(TimestampedUUIDModel):
    so = models.ForeignKey(
        SoChuyenDoiThietBiTuan,
        on_delete=models.CASCADE,
        related_name="lan_chuyen_dois",
    )
    thoi_gian = models.DateTimeField(default=timezone.now)
    nguoi_thuc_hien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lan_chuyen_doi_thiet_bi_da_thuc_hien",
        null=True,
        blank=True,
    )
    ghi_chu_chung = models.TextField(blank=True)

    class Meta:
        ordering = ["thoi_gian", "created_at"]
        verbose_name = "Lần chuyển đổi thiết bị"
        verbose_name_plural = "Lần chuyển đổi thiết bị"

    def clean(self):
        if self.so_id and self.thoi_gian:
            thoi_gian_date = timezone.localtime(self.thoi_gian).date() if timezone.is_aware(self.thoi_gian) else self.thoi_gian.date()
            if thoi_gian_date < self.so.tuan_bat_dau or thoi_gian_date > self.so.tuan_ket_thuc:
                raise ValidationError({"thoi_gian": "Thoi gian chuyen doi phai nam trong tuan cua so."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Lan chuyen doi {self.thoi_gian:%Y-%m-%d %H:%M}"


class ChiTietChuyenDoiThietBi(TimestampedUUIDModel):
    class TrangThai(models.TextChoices):
        LAM_VIEC = "lam_viec", "Làm việc"
        DU_PHONG = "du_phong", "Dự phòng"

    lan_chuyen_doi = models.ForeignKey(
        LanChuyenDoiThietBi,
        on_delete=models.CASCADE,
        related_name="chi_tiets",
    )
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="chi_tiet_chuyen_doi_thiet_bi",
    )
    to_may = models.CharField(max_length=20, choices=MauChuyenDoiThietBi.ToMay.choices)
    nhom_thiet_bi = models.CharField(max_length=255, blank=True)
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        blank=True,
    )
    ghi_chu = models.TextField(blank=True)
    thu_tu = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["to_may", "thu_tu", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lan_chuyen_doi", "thiet_bi"],
                name="uq_chi_tiet_chuyen_doi_lan_thiet_bi",
            )
        ]
        verbose_name = "Chi tiết chuyển đổi thiết bị"
        verbose_name_plural = "Chi tiết chuyển đổi thiết bị"

    def __str__(self):
        return f"{self.thiet_bi} - {self.get_trang_thai_display() or 'Chua chon'}"
