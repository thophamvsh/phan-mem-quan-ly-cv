from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .base import TimestampedUUIDModel, _lay_chu_ky_profile

class SogiaonhancaVH(TimestampedUUIDModel):
    class CaTruc(models.TextChoices):
        A = "A", "Ca A"
        B = "B", "Ca B"
        C = "C", "Ca C"
        D = "D", "Ca D"
        E = "E", "Ca E"

    class TrangThai(models.TextChoices):
        CHO_XAC_NHAN = "cho_xac_nhan", "Chờ xác nhận"
        HOAN_THANH = "hoan_thanh", "Hoàn thành"

    ngay_truc = models.DateField()
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_vh",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    ca_truc = models.CharField(max_length=1, choices=CaTruc.choices)
    dia_diem = models.CharField(max_length=255, blank=True)
    truc_chinh = models.CharField(max_length=255, blank=True)
    truc_phu = models.CharField(max_length=255, blank=True)
    truc_ktvh = models.CharField(max_length=255, blank=True)
    dieu_do_a0 = models.CharField(max_length=255, blank=True)
    dieu_do_a3 = models.CharField(max_length=255, blank=True)
    dieu_do_b3 = models.CharField(max_length=255, blank=True)
    thoi_gian_bat_dau_ca = models.DateTimeField(null=True, blank=True)
    thoi_gian_giao_ca = models.DateTimeField()
    noi_dung_chi_tiet = models.TextField(blank=True)
    tinh_trang_van_hanh_trong_ca = models.TextField(blank=True)
    cac_phuong_tien_trang_bi_ca = models.TextField(blank=True)
    luu_y = models.TextField(blank=True)
    tong_muc_luc = models.TextField(blank=True)
    hinh_anh = models.ImageField(upload_to="operations/so_giao_nhan_ca_vh/", null=True, blank=True)
    chu_ky_user_giao_ca = models.ImageField(
        upload_to="operations/so_giao_nhan_ca_vh/chu_ky/giao_ca/",
        null=True,
        blank=True,
    )
    chu_ky_user_nhan_ca = models.ImageField(
        upload_to="operations/so_giao_nhan_ca_vh/chu_ky/nhan_ca/",
        null=True,
        blank=True,
    )
    user_giao_ca = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_vh_da_giao",
    )
    user_nhan_ca = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_vh_da_nhan",
        null=True,
        blank=True,
    )
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_vh_da_tao",
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
        verbose_name = "Sổ giao nhận ca vận hành"
        verbose_name_plural = "Sổ giao nhận ca vận hành"

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
        return f"So giao nhan ca {self.ca_truc} - {self.ngay_truc}"


class ChiTietSoGiaoNhanCaVH(TimestampedUUIDModel):
    so_giao_nhan_ca = models.ForeignKey(
        SogiaonhancaVH,
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
        related_name="chi_tiet_so_giao_nhan_ca_vh_da_tao",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["thu_tu", "thoi_gian", "created_at"]
        verbose_name = "Nội dung chi tiết sổ giao nhận ca vận hành"
        verbose_name_plural = "Nội dung chi tiết sổ giao nhận ca vận hành"

    def __str__(self):
        return self.tieu_de or f"Noi dung chi tiet {self.thu_tu}"


class LuuYChiDaoSoGiaoNhanCaVH(TimestampedUUIDModel):
    so_giao_nhan_ca = models.ForeignKey(
        SogiaonhancaVH,
        on_delete=models.CASCADE,
        related_name="luu_y_chi_daos",
    )
    thoi_gian = models.DateTimeField(default=timezone.now)
    noi_dung = models.TextField()
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="luu_y_chi_dao_so_giao_nhan_ca_vh_da_tao",
    )

    class Meta:
        ordering = ["thoi_gian", "created_at"]
        verbose_name = "Luu y chi dao so giao nhan ca van hanh"
        verbose_name_plural = "Luu y chi dao so giao nhan ca van hanh"

    def __str__(self):
        return f"Luu y chi dao {self.so_giao_nhan_ca_id} - {self.thoi_gian:%Y-%m-%d %H:%M}"
