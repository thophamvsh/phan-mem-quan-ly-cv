import uuid

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


class SuKien(TimestampedUUIDModel):
    class TrangThaiXuLy(models.TextChoices):
        CHUA_XU_LY_XONG = "chua_xu_ly_xong", "Chua xu ly xong"
        DANG_XU_LY = "dang_xu_ly", "Dang xu ly"
        XU_LY_XONG = "xu_ly_xong", "Xu ly xong"

    thoi_gian_xay_ra = models.DateTimeField()
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="su_kiens",
        null=True,
        blank=True,
        verbose_name="Nha may",
    )
    ten_he_thong_thiet_bi = models.CharField(max_length=255)
    hien_tuong_dien_bien = models.TextField()
    phan_tich_nguyen_nhan = models.TextField(blank=True)
    qua_trinh_kiem_tra = models.TextField(blank=True)
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
        verbose_name = "Su kien"
        verbose_name_plural = "Su kien"

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
    def qua_trinh_xu_ly(self):
        return self._get_latest_attr("qua_trinh_xu_ly", "")

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
        verbose_name = "Dien bien su kien"
        verbose_name_plural = "Dien bien su kien"

    def __str__(self):
        return f"Dien bien {self.su_kien_id} - {self.thoi_gian_dien_bien}"


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
        verbose_name = "Khac phuc su kien"
        verbose_name_plural = "Khac phuc su kien"

    def __str__(self):
        return f"Khac phuc {self.su_kien_id}"

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
        CHO_XAC_NHAN = "cho_xac_nhan", "Cho xac nhan"
        HOAN_THANH = "hoan_thanh", "Hoan thanh"

    ngay_truc = models.DateField()
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_vh",
        null=True,
        blank=True,
        verbose_name="Nha may",
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
        CHO_XAC_NHAN = "cho_xac_nhan", "Cho xac nhan"
        HOAN_THANH = "hoan_thanh", "Hoan thanh"

    ngay_truc = models.DateField()
    nha_may = models.ForeignKey(
        "khovattu.Bang_nha_may",
        on_delete=models.PROTECT,
        related_name="so_giao_nhan_ca_hc",
        null=True,
        blank=True,
        verbose_name="Nha may",
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
        verbose_name = "So giao nhan ca hanh chinh"
        verbose_name_plural = "So giao nhan ca hanh chinh"

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
        verbose_name = "Nguoi truc so giao nhan ca hanh chinh"
        verbose_name_plural = "Nguoi truc so giao nhan ca hanh chinh"

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
        verbose_name = "Noi dung chi tiet so giao nhan ca hanh chinh"
        verbose_name_plural = "Noi dung chi tiet so giao nhan ca hanh chinh"

    def __str__(self):
        return self.tieu_de or f"Noi dung chi tiet HC {self.thu_tu}"
