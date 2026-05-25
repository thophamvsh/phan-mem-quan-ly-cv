import uuid
from calendar import monthrange
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimestampedUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


def _lay_chu_ky_profile(user):
    try:
        profile = user.profile
    except Exception:
        return None
    return getattr(profile, "chu_ky", None)


def _current_year():
    return timezone.localdate().year


class SuKien(TimestampedUUIDModel):
    class LoaiSuKien(models.TextChoices):
        KHIEM_KHUYET = "khiem_khuyet", "Khiếm khuyết"
        SU_CO = "su_co", "Sự cố"

    class TrangThaiXuLy(models.TextChoices):
        CHUA_XU_LY_XONG = "chua_xu_ly_xong", "Chưa xử lý xong"
        DANG_XU_LY = "dang_xu_ly", "Đang xử lý"
        XU_LY_XONG = "xu_ly_xong", "Xử lý xong"

    thoi_gian_xay_ra = models.DateTimeField()
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="su_kiens",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="su_kiens",
        null=True,
        blank=True,
        verbose_name="Thiết bị liên quan",
    )
    ten_he_thong_thiet_bi = models.CharField(max_length=255)
    loai = models.CharField(
        max_length=32,
        choices=LoaiSuKien.choices,
        default=LoaiSuKien.SU_CO,
    )
    hien_tuong_dien_bien = models.TextField()
    phan_tich_nguyen_nhan = models.TextField(blank=True)
    qua_trinh_kiem_tra = models.TextField(blank=True)
    qua_trinh_xu_ly = models.TextField(blank=True)
    chi_dao = models.TextField(blank=True)
    nguoi_chi_dao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="su_kien_da_chi_dao",
        null=True,
        blank=True,
    )
    chu_ky_nguoi_chi_dao = models.ImageField(
        upload_to="operations/nhat_ky_su_kien/chu_ky/chi_dao/",
        null=True,
        blank=True,
    )
    de_xuat_khac_phuc = models.TextField(blank=True)
    bao_cho = models.CharField(max_length=255, blank=True)
    hinh_anh_truoc_su_co = models.ImageField(
        upload_to="operations/nhat_ky_su_kien/truoc_su_co/",
        null=True,
        blank=True,
    )
    chu_ky_ben_ghi_nhan_su_kien = models.ImageField(
        upload_to="operations/nhat_ky_su_kien/chu_ky/ghi_nhan/",
        null=True,
        blank=True,
    )
    trang_thai = models.CharField(
        max_length=32,
        choices=TrangThaiXuLy.choices,
        default=TrangThaiXuLy.CHUA_XU_LY_XONG,
    )
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="su_kien_da_tao",
        null=True,
        blank=True,
    )
    ben_ghi_nhan_su_kien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="su_kien_da_ghi_nhan",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-thoi_gian_xay_ra", "-created_at"]
        verbose_name = "Sự kiện"
        verbose_name_plural = "Sự kiện"

    def __str__(self):
        return f"{self.ten_he_thong_thiet_bi} - {self.thoi_gian_xay_ra}"

    @property
    def latest_khac_phuc(self):
        prefetched = getattr(self, "_prefetched_objects_cache", {})
        if "khac_phuc_su_kiens" in prefetched:
            items = list(prefetched["khac_phuc_su_kiens"])
            if not items:
                return None
            items.sort(
                key=lambda item: (
                    item.thoi_gian_xu_ly or timezone.make_aware(timezone.datetime.min),
                    item.created_at,
                ),
                reverse=True,
            )
            return items[0]

        return self.khac_phuc_su_kiens.order_by("-thoi_gian_xu_ly", "-created_at").first()

    def _get_latest_attr(self, attr_name, default=None):
        latest = self.latest_khac_phuc
        if latest is None:
            return default
        value = getattr(latest, attr_name, default)
        return default if value is None else value

    @property
    def thoi_gian_xu_ly(self):
        return self._get_latest_attr("thoi_gian_xu_ly")

    @property
    def ket_qua_kiem_tra_nguyen_nhan(self):
        return self._get_latest_attr("ket_qua_kiem_tra_nguyen_nhan", "")

    @property
    def noi_dung_xu_ly_khac_phuc(self):
        return self._get_latest_attr("noi_dung_xu_ly_khac_phuc", "")

    @property
    def de_xuat_lien_quan(self):
        return self._get_latest_attr("de_xuat_lien_quan", "")

    @property
    def ket_qua_sau_xu_ly(self):
        return self._get_latest_attr("ket_qua_sau_xu_ly", "")

    @property
    def hinh_anh_sau_xu_ly(self):
        return self._get_latest_attr("hinh_anh_sau_xu_ly")

    @property
    def chu_ky_ben_xu_ly_su_kien_thiet_bi(self):
        return self._get_latest_attr("chu_ky_ben_xu_ly_su_kien_thiet_bi")

    @property
    def chu_ky_nguoi_xac_nhan_xu_ly(self):
        return self._get_latest_attr("chu_ky_nguoi_xac_nhan_xu_ly")

    @property
    def ben_xu_ly_su_kien_thiet_bi(self):
        return self._get_latest_attr("ben_xu_ly_su_kien_thiet_bi")

    @property
    def nguoi_xac_nhan_xu_ly(self):
        return self._get_latest_attr("nguoi_xac_nhan_xu_ly")

    def clean(self):
        if self.trang_thai in [
            self.TrangThaiXuLy.DANG_XU_LY,
            self.TrangThaiXuLy.XU_LY_XONG,
        ] and not self.ben_ghi_nhan_su_kien_id:
            raise ValidationError({"ben_ghi_nhan_su_kien": "Can ghi nhan su kien truoc khi xu ly."})

    def save(self, *args, **kwargs):
        if self.ben_ghi_nhan_su_kien_id and not self.chu_ky_ben_ghi_nhan_su_kien:
            chu_ky = _lay_chu_ky_profile(self.ben_ghi_nhan_su_kien)
            if chu_ky:
                self.chu_ky_ben_ghi_nhan_su_kien = chu_ky.name
        if self.nguoi_chi_dao_id and not self.chu_ky_nguoi_chi_dao:
            chu_ky = _lay_chu_ky_profile(self.nguoi_chi_dao)
            if chu_ky:
                self.chu_ky_nguoi_chi_dao = chu_ky.name
        self.full_clean()
        return super().save(*args, **kwargs)


class DienBienSuKien(TimestampedUUIDModel):
    su_kien = models.ForeignKey(
        SuKien,
        on_delete=models.CASCADE,
        related_name="dien_bien_su_kiens",
    )
    thoi_gian_dien_bien = models.DateTimeField(default=timezone.now)
    noi_dung = models.TextField()
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dien_bien_su_kien_da_tao",
        null=True,
        blank=True,
    )
    chuc_danh_nguoi_tao = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["thoi_gian_dien_bien", "created_at"]
        verbose_name = "Diễn biến sự kiện"
        verbose_name_plural = "Diễn biến sự kiện"

    def __str__(self):
        return f"Diễn biến {self.su_kien_id} - {self.thoi_gian_dien_bien}"


class KhacPhucSuKien(TimestampedUUIDModel):
    su_kien = models.ForeignKey(
        SuKien,
        on_delete=models.CASCADE,
        related_name="khac_phuc_su_kiens",
    )
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="khac_phuc_su_kien_da_tao",
        null=True,
        blank=True,
    )
    qua_trinh_xu_ly = models.TextField(blank=True)
    thoi_gian_xu_ly = models.DateTimeField(null=True, blank=True)
    ket_qua_kiem_tra_nguyen_nhan = models.TextField(blank=True)
    noi_dung_xu_ly_khac_phuc = models.TextField(blank=True)
    de_xuat_lien_quan = models.TextField(blank=True)
    ket_qua_sau_xu_ly = models.TextField(blank=True)
    hinh_anh_sau_xu_ly = models.ImageField(
        upload_to="operations/nhat_ky_su_kien/sau_xu_ly/",
        null=True,
        blank=True,
    )
    chu_ky_ben_xu_ly_su_kien_thiet_bi = models.ImageField(
        upload_to="operations/nhat_ky_su_kien/chu_ky/xu_ly/",
        null=True,
        blank=True,
    )
    chu_ky_nguoi_xac_nhan_xu_ly = models.ImageField(
        upload_to="operations/nhat_ky_su_kien/chu_ky/xac_nhan/",
        null=True,
        blank=True,
    )
    ben_xu_ly_su_kien_thiet_bi = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="khac_phuc_su_kien_da_xu_ly",
        null=True,
        blank=True,
    )
    nguoi_xac_nhan_xu_ly = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="khac_phuc_su_kien_da_xac_nhan_xu_ly",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-thoi_gian_xu_ly", "-created_at"]
        verbose_name = "Khắc phục sự kiện"
        verbose_name_plural = "Khắc phục sự kiện"

    def __str__(self):
        return f"Khắc phục {self.su_kien_id}"

    def save(self, *args, **kwargs):
        if (
            self.su_kien.trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG
            and not self.thoi_gian_xu_ly
        ):
            self.thoi_gian_xu_ly = timezone.now()
        if self.ben_xu_ly_su_kien_thiet_bi_id and not self.chu_ky_ben_xu_ly_su_kien_thiet_bi:
            chu_ky = _lay_chu_ky_profile(self.ben_xu_ly_su_kien_thiet_bi)
            if chu_ky:
                self.chu_ky_ben_xu_ly_su_kien_thiet_bi = chu_ky.name
        if self.nguoi_xac_nhan_xu_ly_id and not self.chu_ky_nguoi_xac_nhan_xu_ly:
            chu_ky = _lay_chu_ky_profile(self.nguoi_xac_nhan_xu_ly)
            if chu_ky:
                self.chu_ky_nguoi_xac_nhan_xu_ly = chu_ky.name
        return super().save(*args, **kwargs)


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
