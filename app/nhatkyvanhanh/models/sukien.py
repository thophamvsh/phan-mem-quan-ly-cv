from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .base import TimestampedUUIDModel, _lay_chu_ky_profile

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


class ChiDaoSuKien(TimestampedUUIDModel):
    su_kien = models.ForeignKey(
        SuKien,
        on_delete=models.CASCADE,
        related_name="chi_dao_su_kiens",
    )
    noi_dung = models.TextField()
    nguoi_chi_dao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="chi_dao_su_kien_da_tao",
        null=True,
        blank=True,
    )
    chuc_danh_nguoi_chi_dao = models.CharField(max_length=100, blank=True)
    chu_ky_nguoi_chi_dao = models.ImageField(
        upload_to="operations/nhat_ky_su_kien/chu_ky/chi_dao/",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Chỉ đạo sự kiện"
        verbose_name_plural = "Chỉ đạo sự kiện"

    def __str__(self):
        return f"Chỉ đạo {self.su_kien_id} - {self.created_at}"

    def save(self, *args, **kwargs):
        if self.nguoi_chi_dao_id and not self.chu_ky_nguoi_chi_dao:
            chu_ky = _lay_chu_ky_profile(self.nguoi_chi_dao)
            if chu_ky:
                self.chu_ky_nguoi_chi_dao = chu_ky.name
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
