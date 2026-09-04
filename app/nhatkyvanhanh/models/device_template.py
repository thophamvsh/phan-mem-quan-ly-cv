import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class MauTrangThaiThietBiCa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.PROTECT,
        related_name="mau_trang_thai_thiet_bi_ca",
        verbose_name="Nhà máy",
    )
    ten_mau = models.CharField(max_length=255, verbose_name="Tên mẫu")
    phien_ban = models.PositiveIntegerField(default=1, verbose_name="Phiên bản")
    dang_ap_dung = models.BooleanField(default=False, verbose_name="Đang áp dụng")
    ghi_chu = models.TextField(blank=True, verbose_name="Ghi chú")
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mau_trang_thai_thiet_bi_ca_da_tao",
        verbose_name="Người tạo",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nha_may__ten_nha_may", "-phien_ban"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "phien_ban"],
                name="uq_mau_trang_thai_tb_ca_nha_may_phien_ban",
            ),
            models.UniqueConstraint(
                fields=["nha_may"],
                condition=models.Q(dang_ap_dung=True),
                name="uq_mau_trang_thai_tb_ca_dang_ap_dung",
            ),
        ]
        permissions = [
            ("activate_mautrangthaithietbica", "Có quyền kích hoạt mẫu trạng thái thiết bị ca"),
        ]
        verbose_name = "Mẫu trạng thái thiết bị ca"
        verbose_name_plural = "Mẫu trạng thái thiết bị ca"

    @property
    def da_duoc_su_dung(self):
        from .giao_ca_vh import SogiaonhancaVH

        return SogiaonhancaVH.objects.filter(
            trang_thai_thiet_bi__template_id=str(self.pk)
        ).exists()

    def __str__(self):
        return f"{self.nha_may} - {self.ten_mau} v{self.phien_ban}"


class NhomMauTrangThaiThietBiCa(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mau = models.ForeignKey(
        MauTrangThaiThietBiCa,
        on_delete=models.CASCADE,
        related_name="nhom_thiet_bi",
        verbose_name="Mẫu",
    )
    ma_nhom = models.SlugField(max_length=80, verbose_name="Mã nhóm")
    tieu_de = models.CharField(max_length=255, verbose_name="Tiêu đề")
    thu_tu = models.PositiveIntegerField(default=1, verbose_name="Thứ tự")

    class Meta:
        ordering = ["thu_tu", "id"]
        constraints = [
            models.UniqueConstraint(fields=["mau", "ma_nhom"], name="uq_nhom_mau_tb_ca_ma_nhom")
        ]
        verbose_name = "Nhóm mẫu trạng thái thiết bị ca"
        verbose_name_plural = "Nhóm mẫu trạng thái thiết bị ca"

    def __str__(self):
        return self.tieu_de


class ChiTietMauTrangThaiThietBiCa(models.Model):
    class TrangThai(models.TextChoices):
        DONG = "dong", "Đóng"
        CAT = "cat", "Cắt"
        CAT_VTCL = "cat_vtcl", "Cắt VTCL"
        KHAC = "khac", "Khác"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nhom = models.ForeignKey(
        NhomMauTrangThaiThietBiCa,
        on_delete=models.CASCADE,
        related_name="thiet_bi",
        verbose_name="Nhóm",
    )
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="chi_tiet_mau_trang_thai_ca",
        null=True,
        blank=True,
        verbose_name="Thiết bị trong danh mục",
    )
    ma_hien_thi = models.CharField(max_length=255, verbose_name="Mã hiển thị")
    trang_thai_mac_dinh = models.CharField(
        max_length=16,
        choices=TrangThai.choices,
        default=TrangThai.DONG,
        verbose_name="Trạng thái mặc định",
    )
    ghi_chu_mac_dinh = models.CharField(max_length=500, blank=True, verbose_name="Ghi chú mặc định")
    thu_tu = models.PositiveIntegerField(default=1, verbose_name="Thứ tự")

    class Meta:
        ordering = ["thu_tu", "id"]
        constraints = [
            models.UniqueConstraint(fields=["nhom", "ma_hien_thi"], name="uq_chi_tiet_mau_tb_ca_ma")
        ]
        verbose_name = "Chi tiết mẫu trạng thái thiết bị ca"
        verbose_name_plural = "Chi tiết mẫu trạng thái thiết bị ca"

    def clean(self):
        if not self.thiet_bi_id:
            return
        plant_code = (self.nhom.mau.nha_may.ma_nha_may or "").casefold()
        device_plant = (self.thiet_bi.nha_may or "").casefold()
        full_code = (self.thiet_bi.ma_day_du or "").casefold()
        plant_name = (self.nhom.mau.nha_may.ten_nha_may or "").casefold()
        if device_plant not in {plant_code, plant_name} and not full_code.startswith(f"{plant_code}."):
            raise ValidationError({"thiet_bi": "Thiết bị không thuộc nhà máy của mẫu."})

    def __str__(self):
        return self.ma_hien_thi
