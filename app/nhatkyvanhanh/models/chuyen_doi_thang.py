from datetime import date
from calendar import monthrange
from decimal import Decimal
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from core.factory_scope import is_device_belong_to_factory
from .base import TimestampedUUIDModel, _current_year, _lay_chu_ky_profile
from nhatkyvanhanh.services.monthly_switch import MonthlySwitchCalculationService

class MauChuyenDoiTBThang(TimestampedUUIDModel):
    class LoaiTinhToan(models.TextChoices):
        COUNTER = "counter", "Bộ đếm tăng dần"
        FUEL = "fuel", "Nhiên liệu tiêu hao"

    class Pha(models.TextChoices):
        KHONG = "", "Không phân pha"
        A = "A", "Pha A"
        B = "B", "Pha B"
        C = "C", "Pha C"

    ma_dinh_danh = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.PROTECT,
        related_name="mau_chuyen_doi_tb_thang",
        null=False,
        blank=False,
        verbose_name="Nhà máy",
    )
    ma_nhom = models.CharField(max_length=20, blank=True)
    ten_nhom = models.CharField(max_length=255)
    don_vi_nhom = models.CharField(max_length=50, blank=True)
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="mau_chuyen_doi_tb_thang",
        null=True,
        blank=True,
    )
    ma_hien_thi = models.CharField(max_length=100)
    ten_hien_thi = models.CharField(max_length=255)
    pha = models.CharField(max_length=10, choices=Pha.choices, default="", blank=True)
    loai_tinh_toan = models.CharField(
        max_length=20,
        choices=LoaiTinhToan.choices,
        default=LoaiTinhToan.COUNTER,
    )
    don_vi = models.CharField(max_length=50, default="Lan")
    thu_tu_nhom = models.PositiveIntegerField(default=1)
    thu_tu = models.PositiveIntegerField(default=1)
    dang_su_dung = models.BooleanField(default=True)

    class Meta:
        ordering = ["nha_may", "thu_tu_nhom", "thu_tu", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "thiet_bi", "pha"],
                condition=models.Q(thiet_bi__isnull=False),
                name="uq_mau_thang_linked_device_phase",
            ),
            models.UniqueConstraint(
                fields=["nha_may", "ma_hien_thi", "pha"],
                condition=models.Q(thiet_bi__isnull=True),
                name="uq_mau_thang_manual_device_phase",
            ),
        ]
        verbose_name = "Mẫu chuyển đổi TB tháng"
        verbose_name_plural = "Mẫu chuyển đổi TB tháng"

    def clean(self):
        super().clean()
        self.pha = (self.pha or "").strip().upper()
        if self.thiet_bi_id:
            if self.nha_may_id and not is_device_belong_to_factory(
                self.thiet_bi, self.nha_may
            ):
                raise ValidationError(
                    {"thiet_bi": "Thiết bị được chọn không thuộc nhà máy này."}
                )
            self.ma_hien_thi = (self.thiet_bi.ma_day_du or self.thiet_bi.ma).strip().upper()
            self.ten_hien_thi = self.thiet_bi.ten.strip()
        else:
            self.ma_hien_thi = (self.ma_hien_thi or "").strip().upper()
            self.ten_hien_thi = (self.ten_hien_thi or "").strip()
            if not self.ma_hien_thi or not self.ten_hien_thi:
                raise ValidationError("Thiết bị tự do bắt buộc phải có mã và tên hiển thị.")

    def save(self, *args, **kwargs):
        # Populate linked-device snapshots before ``full_clean`` validates the
        # required CharFields. ``clean()`` itself runs after field validation.
        if self.thiet_bi_id:
            self.ma_hien_thi = (
                self.thiet_bi.ma_day_du or self.thiet_bi.ma
            ).strip().upper()
            self.ten_hien_thi = self.thiet_bi.ten.strip()
        else:
            self.ma_hien_thi = (self.ma_hien_thi or "").strip().upper()
            self.ten_hien_thi = (self.ten_hien_thi or "").strip()
        self.pha = (self.pha or "").strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ten_nhom} - {self.ten_hien_thi}"


class SoChuyenDoiTBThang(TimestampedUUIDModel):
    class CaTruc(models.TextChoices):
        A = "A", "Ca A"
        B = "B", "Ca B"
        C = "C", "Ca C"
        D = "D", "Ca D"

    class TrangThai(models.TextChoices):
        CHO_DUYET = "cho_duyet", "Chờ duyệt"
        DA_DUYET = "da_duyet", "Đã duyệt"

    nam = models.PositiveSmallIntegerField(default=_current_year)
    thang = models.PositiveSmallIntegerField(default=1)
    ca_truc = models.CharField(max_length=1, choices=CaTruc.choices, default=CaTruc.A)
    thang_bat_dau = models.DateField()
    thang_ket_thuc = models.DateField()
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHO_DUYET,
        verbose_name="Trạng thái",
    )
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.PROTECT,
        related_name="so_chuyen_doi_tb_thang",
        null=False,
        blank=False,
        verbose_name="Nhà máy",
    )
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_chuyen_doi_tb_thang_da_tao",
        null=True,
        blank=True,
        verbose_name="Người tạo",
    )
    nguoi_duyet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_chuyen_doi_tb_thang_da_duyet",
        null=True,
        blank=True,
        verbose_name="Người duyệt",
    )
    duyet_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian duyệt")
    ghi_chu_duyet = models.TextField(blank=True, verbose_name="Ghi chú duyệt")
    chu_ky_nguoi_tao = models.ImageField(
        upload_to="signatures/so_chuyen_doi_thang/nguoi_tao/",
        null=True,
        blank=True,
        verbose_name="Chữ ký người tạo",
    )
    chu_ky_nguoi_duyet = models.ImageField(
        upload_to="signatures/so_chuyen_doi_thang/nguoi_duyet/",
        null=True,
        blank=True,
        verbose_name="Chữ ký người duyệt",
    )

    class Meta:
        ordering = ["-nam", "-thang", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "nam", "thang"],
                name="uq_so_chuyen_doi_tb_thang_nha_may_nam_thang",
            )
        ]
        verbose_name = "Sổ chuyển đổi TB tháng"
        verbose_name_plural = "Sổ chuyển đổi TB tháng"

    @property
    def da_khoa(self):
        return bool(
            (self.nguoi_duyet_id and self.duyet_at)
            or self.trang_thai == self.TrangThai.DA_DUYET
        )

    def dong_bo_chu_ky_tu_user(self, user=None):
        if self.nguoi_tao_id and not self.chu_ky_nguoi_tao:
            signature = _lay_chu_ky_profile(self.nguoi_tao)
            if signature:
                self.chu_ky_nguoi_tao = signature
        if self.nguoi_duyet_id:
            signature = _lay_chu_ky_profile(self.nguoi_duyet)
            if signature:
                self.chu_ky_nguoi_duyet = signature
        if user and user.id == self.nguoi_duyet_id:
            signature = _lay_chu_ky_profile(user)
            if signature:
                self.chu_ky_nguoi_duyet = signature

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
        if self.nguoi_tao_id and not self.chu_ky_nguoi_tao:
            signature = _lay_chu_ky_profile(self.nguoi_tao)
            if signature:
                self.chu_ky_nguoi_tao = signature
        if self.nguoi_duyet_id and not self.chu_ky_nguoi_duyet:
            signature = _lay_chu_ky_profile(self.nguoi_duyet)
            if signature:
                self.chu_ky_nguoi_duyet = signature
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Sổ chuyển đổi TB tháng {self.thang}/{self.nam} - Ca {self.ca_truc}"


class ChiTietChuyenDoiTBThang(TimestampedUUIDModel):
    ma_dinh_danh = models.UUIDField(editable=False, db_index=True)
    so = models.ForeignKey(
        SoChuyenDoiTBThang,
        on_delete=models.CASCADE,
        related_name="chi_tiets",
    )
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="chi_tiet_chuyen_doi_tb_thang",
        null=True,
        blank=True,
    )
    ma_hien_thi = models.CharField(max_length=100)
    ten_hien_thi = models.CharField(max_length=255)
    ma_nhom = models.CharField(max_length=20, blank=True)
    ten_nhom = models.CharField(max_length=255)
    don_vi_nhom = models.CharField(max_length=50, blank=True)
    don_vi = models.CharField(max_length=50, default="Lan")
    pha = models.CharField(max_length=10, choices=MauChuyenDoiTBThang.Pha.choices, default="", blank=True)
    loai_tinh_toan = models.CharField(
        max_length=20,
        choices=MauChuyenDoiTBThang.LoaiTinhToan.choices,
        default=MauChuyenDoiTBThang.LoaiTinhToan.COUNTER,
    )
    dau_nam = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"))
    dau_thang = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"))
    nhap_trong_thang = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"))
    cuoi_thang = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"))
    thuc_hien = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"), editable=False)
    luy_ke_nam = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"), editable=False)
    luy_ke_truoc_so_hoa = models.DecimalField(max_digits=18, decimal_places=3, default=Decimal("0.000"))
    ghi_chu = models.TextField(blank=True)
    thu_tu_nhom = models.PositiveIntegerField(default=1)
    thu_tu = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["thu_tu_nhom", "thu_tu", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["so", "thiet_bi", "pha"],
                condition=models.Q(thiet_bi__isnull=False),
                name="uq_chi_tiet_thang_linked_device_phase",
            ),
            models.UniqueConstraint(
                fields=["so", "ma_hien_thi", "pha"],
                condition=models.Q(thiet_bi__isnull=True),
                name="uq_chi_tiet_thang_manual_device_phase",
            ),
            models.UniqueConstraint(
                fields=["so", "ma_dinh_danh"],
                name="uq_chi_tiet_thang_so_ma_dinh_danh",
            ),
        ]
        verbose_name = "Chi tiết chuyển đổi TB tháng"
        verbose_name_plural = "Chi tiết chuyển đổi TB tháng"

    def clean(self):
        super().clean()
        self.ma_hien_thi = (self.ma_hien_thi or "").strip().upper()
        self.ten_hien_thi = (self.ten_hien_thi or "").strip()
        if not self.ma_hien_thi or not self.ten_hien_thi:
            raise ValidationError("Chi tiết thiết bị bắt buộc phải có mã và tên hiển thị.")
        if self.loai_tinh_toan == MauChuyenDoiTBThang.LoaiTinhToan.COUNTER:
            integer_errors = {}
            for field in (
                "dau_nam",
                "dau_thang",
                "nhap_trong_thang",
                "cuoi_thang",
                "luy_ke_truoc_so_hoa",
            ):
                value = getattr(self, field, Decimal("0")) or Decimal("0")
                if value != value.to_integral_value():
                    integer_errors[field] = "Số lần vận hành phải là số nguyên."
            if integer_errors:
                raise ValidationError(integer_errors)
        MonthlySwitchCalculationService.apply(self)

    def save(self, *args, **kwargs):
        self.ma_hien_thi = (self.ma_hien_thi or "").strip().upper()
        self.ten_hien_thi = (self.ten_hien_thi or "").strip()
        self.pha = (self.pha or "").strip().upper()
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ten_hien_thi} - {self.thuc_hien}"
