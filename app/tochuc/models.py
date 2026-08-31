from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class NhaMay(models.Model):
    """Danh mục nhà máy dùng chung cho toàn hệ thống."""

    id = models.BigAutoField(primary_key=True)
    ma_nha_may = models.CharField(max_length=50, unique=True)
    ten_nha_may = models.CharField(max_length=255)

    class Meta:
        db_table = "khovattu_bang_nha_may"
        verbose_name = "Nhà máy"
        verbose_name_plural = "Nhà máy"

    def __str__(self):
        return f"{self.ma_nha_may} - {self.ten_nha_may}"


class TimeStampedOrganizationModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DonViToChuc(TimeStampedOrganizationModel):
    class LoaiDonVi(models.TextChoices):
        CONG_TY = "cong_ty", "Công ty"
        CUM_NHA_MAY = "cum_nha_may", "Cụm nhà máy"
        NHA_MAY = "nha_may", "Nhà máy"
        VAN_PHONG = "van_phong", "Văn phòng"
        KHAC = "khac", "Khác"

    ma_don_vi = models.CharField(max_length=50, unique=True)
    ten_don_vi = models.CharField(max_length=200)
    loai_don_vi = models.CharField(
        max_length=20,
        choices=LoaiDonVi.choices,
        default=LoaiDonVi.NHA_MAY,
    )
    don_vi_cha = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="don_vi_con",
        null=True,
        blank=True,
    )
    nha_may = models.ForeignKey(
        NhaMay,
        on_delete=models.PROTECT,
        related_name="don_vi_to_chuc",
        null=True,
        blank=True,
    )
    thu_tu = models.PositiveSmallIntegerField(default=1)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        db_table = "quanlycatruc_donvitochuc"
        ordering = ["thu_tu", "ten_don_vi"]
        verbose_name = "Đơn vị tổ chức"
        verbose_name_plural = "Các đơn vị tổ chức"

    def clean(self):
        if self.pk and self.don_vi_cha_id == self.pk:
            raise ValidationError(
                {"don_vi_cha": "Đơn vị không thể là cấp trên của chính nó."}
            )
        ancestor = self.don_vi_cha
        visited = set()
        while ancestor:
            if ancestor.pk == self.pk or ancestor.pk in visited:
                raise ValidationError(
                    {"don_vi_cha": "Cấu trúc đơn vị tạo thành vòng lặp."}
                )
            if self.nha_may_id and ancestor.nha_may_pham_vi_id not in {
                None,
                self.nha_may_id,
            }:
                raise ValidationError(
                    {"don_vi_cha": "Đơn vị cha phải thuộc cùng nhà máy."}
                )
            visited.add(ancestor.pk)
            ancestor = ancestor.don_vi_cha

    @property
    def nha_may_pham_vi_id(self):
        current, visited = self, set()
        while current and current.pk not in visited:
            if current.nha_may_id:
                return current.nha_may_id
            visited.add(current.pk)
            current = current.don_vi_cha
        return None

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ma_don_vi} - {self.ten_don_vi}"


class BoPhan(TimeStampedOrganizationModel):
    class LoaiBoPhan(models.TextChoices):
        VAN_HANH = "van_hanh", "Vận hành"
        KY_THUAT = "ky_thuat", "Kỹ thuật"
        HANH_CHINH = "hanh_chinh", "Hành chính"
        BAO_VE = "bao_ve", "Bảo vệ"
        BAO_TRI = "bao_tri", "Bảo trì"
        AN_TOAN = "an_toan", "An toàn"
        KHAC = "khac", "Khác"

    don_vi = models.ForeignKey(
        DonViToChuc,
        on_delete=models.PROTECT,
        related_name="bo_phan",
    )
    ma_bo_phan = models.CharField(max_length=50)
    ten_bo_phan = models.CharField(max_length=150)
    loai_bo_phan = models.CharField(
        max_length=20,
        choices=LoaiBoPhan.choices,
        default=LoaiBoPhan.KHAC,
    )
    thu_tu = models.PositiveSmallIntegerField(default=1)
    dang_hoat_dong = models.BooleanField(default=True)

    class Meta:
        db_table = "quanlycatruc_bophan"
        ordering = ["don_vi", "thu_tu", "ten_bo_phan"]
        constraints = [
            models.UniqueConstraint(
                fields=["don_vi", "ma_bo_phan"],
                name="uq_bophan_donvi_ma",
            )
        ]
        verbose_name = "Bộ phận"
        verbose_name_plural = "Các bộ phận"

    @property
    def nha_may_pham_vi_id(self):
        return self.don_vi.nha_may_pham_vi_id

    def __str__(self):
        return f"{self.ten_bo_phan} - {self.don_vi.ten_don_vi}"


class NhanSu(TimeStampedOrganizationModel):
    """Danh mục nhân sự dùng chung, độc lập với tài khoản đăng nhập."""

    ma_nhan_vien = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
    )
    ho_ten = models.CharField(max_length=150)
    don_vi = models.ForeignKey(
        DonViToChuc,
        on_delete=models.PROTECT,
        related_name="nhan_su",
    )
    bo_phan = models.ForeignKey(
        BoPhan,
        on_delete=models.PROTECT,
        related_name="nhan_su",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="nhan_su_ca_truc",
        null=True,
        blank=True,
    )
    chuc_danh = models.CharField(max_length=120, blank=True)
    dien_thoai = models.CharField(max_length=30, blank=True)
    tu_ngay = models.DateField(default=date.today)
    den_ngay = models.DateField(null=True, blank=True)
    dang_lam_viec = models.BooleanField(default=True)

    class Meta:
        db_table = "quanlycatruc_nhansu"
        ordering = ["don_vi", "bo_phan", "ho_ten"]
        indexes = [
            models.Index(
                fields=["don_vi", "bo_phan", "dang_lam_viec"],
                name="quanlycatru_don_vi__2e1cc8_idx",
            )
        ]
        verbose_name = "Nhân sự"
        verbose_name_plural = "Danh mục nhân sự"

    @property
    def nha_may_id(self):
        return self.don_vi.nha_may_pham_vi_id if self.don_vi_id else None

    def clean(self):
        errors = {}
        if (
            self.bo_phan_id
            and self.don_vi_id
            and self.bo_phan.don_vi_id != self.don_vi_id
        ):
            errors["bo_phan"] = "Bộ phận phải thuộc đơn vị đã chọn."
        if self.den_ngay and self.den_ngay < self.tu_ngay:
            errors["den_ngay"] = (
                "Ngày kết thúc không được trước ngày bắt đầu."
            )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.ma_nhan_vien = self.ma_nhan_vien or None
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.ho_ten
