from datetime import date
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .base import TimestampedUUIDModel, _current_year, _lay_chu_ky_profile


class KhuVucChuyenDoiThietBi(TimestampedUUIDModel):
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.PROTECT,
        related_name="khu_vuc_chuyen_doi_thiet_bi",
        verbose_name="Nhà máy",
    )
    ma_khu_vuc = models.CharField(max_length=50, verbose_name="Mã khu vực")
    ten_khu_vuc = models.CharField(max_length=255, verbose_name="Tên khu vực")
    thu_tu = models.PositiveIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    dang_su_dung = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        ordering = ["nha_may", "thu_tu", "ten_khu_vuc"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "ma_khu_vuc"],
                name="uq_khu_vuc_chuyen_doi_nha_may_ma",
            )
        ]
        verbose_name = "Khu vực chuyển đổi thiết bị"
        verbose_name_plural = "Khu vực chuyển đổi thiết bị"

    def clean(self):
        self.ma_khu_vuc = (self.ma_khu_vuc or "").strip().upper()
        self.ten_khu_vuc = (self.ten_khu_vuc or "").strip()
        if not self.ma_khu_vuc:
            raise ValidationError({"ma_khu_vuc": "Mã khu vực là bắt buộc."})
        if not self.ten_khu_vuc:
            raise ValidationError({"ten_khu_vuc": "Tên khu vực là bắt buộc."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ten_khu_vuc} ({self.nha_may})"


class MauChuyenDoiThietBi(TimestampedUUIDModel):
    class ToMay(models.TextChoices):
        H1 = "H1", "Tổ máy H1"
        H2 = "H2", "Tổ máy H2"
        TU_DUNG = "tu_dung", "Tự dùng"

    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.PROTECT,
        related_name="mau_chuyen_doi_thiet_bi",
        null=True,
        blank=True,
        verbose_name="Nhà máy",
    )
    khu_vuc = models.ForeignKey(
        KhuVucChuyenDoiThietBi,
        on_delete=models.PROTECT,
        related_name="mau_thiet_bi",
        null=True,
        blank=True,
        verbose_name="Tổ máy / Khu vực",
    )
    to_may = models.CharField(max_length=50, verbose_name="Mã tổ máy / Khu vực")
    nhom_thiet_bi = models.CharField(max_length=255, blank=True, verbose_name="Nhóm thiết bị")
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.CASCADE,
        related_name="mau_chuyen_doi_thiet_bi",
        verbose_name="Thiết bị liên kết",
    )
    thu_tu = models.PositiveIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    dang_su_dung = models.BooleanField(default=True, verbose_name="Đang sử dụng")

    class Meta:
        ordering = ["to_may", "thu_tu", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "khu_vuc", "thiet_bi"],
                name="uq_mau_chuyen_doi_thiet_bi_nha_may_khu_vuc_tb",
            )
        ]
        verbose_name = "Mẫu chuyển đổi thiết bị tuần"
        verbose_name_plural = "Mẫu chuyển đổi thiết bị tuần"

    def __str__(self):
        return f"{self.khu_vuc.ten_khu_vuc if self.khu_vuc_id else self.to_may} - {self.thiet_bi}"

    def get_to_may_display(self):
        if self.khu_vuc_id:
            return self.khu_vuc.ten_khu_vuc
        return dict(self.ToMay.choices).get(self.to_may, self.to_may)


class SoChuyenDoiThietBiTuan(TimestampedUUIDModel):
    class CaTruc(models.TextChoices):
        A = "A", "Ca A"
        B = "B", "Ca B"
        C = "C", "Ca C"
        D = "D", "Ca D"

    class TrangThai(models.TextChoices):
        CHO_DUYET = "cho_duyet", "Chờ duyệt"
        DA_DUYET = "da_duyet", "Đã duyệt"

    nam = models.PositiveSmallIntegerField(default=_current_year, verbose_name="Năm")
    tuan = models.PositiveSmallIntegerField(default=1, verbose_name="Tuần")
    ca_truc = models.CharField(max_length=1, choices=CaTruc.choices, default=CaTruc.A, verbose_name="Ca trực")
    tuan_bat_dau = models.DateField(verbose_name="Ngày bắt đầu tuần")
    tuan_ket_thuc = models.DateField(verbose_name="Ngày kết thúc tuần")
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
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
        verbose_name="Người tạo sổ",
    )
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        default=TrangThai.CHO_DUYET,
        verbose_name="Trạng thái",
    )
    nguoi_duyet = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="so_chuyen_doi_tuan_da_duyet",
        null=True,
        blank=True,
        verbose_name="Người duyệt / Trưởng ca / Quản đốc",
    )
    duyet_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời điểm duyệt",
    )
    ghi_chu_duyet = models.TextField(
        blank=True,
        verbose_name="Ý kiến phê duyệt",
    )
    chu_ky_nguoi_tao = models.ImageField(
        upload_to="operations/so_chuyen_doi_tuan/chu_ky/nguoi_tao/",
        null=True,
        blank=True,
        verbose_name="Chữ ký người lập sổ",
    )
    chu_ky_nguoi_duyet = models.ImageField(
        upload_to="operations/so_chuyen_doi_tuan/chu_ky/nguoi_duyet/",
        null=True,
        blank=True,
        verbose_name="Chữ ký người duyệt",
    )

    class Meta:
        ordering = ["-nam", "-tuan", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "nam", "tuan", "ca_truc"],
                name="uq_so_chuyen_doi_thiet_bi_tuan_nha_may_nam_tuan_ca",
            )
        ]
        verbose_name = "Sổ theo dõi chuyển đổi thiết bị tuần"
        verbose_name_plural = "Sổ theo dõi chuyển đổi thiết bị tuần"

    @property
    def da_khoa(self):
        return bool(self.nguoi_duyet_id and self.duyet_at) or self.trang_thai == self.TrangThai.DA_DUYET

    def dong_bo_chu_ky_tu_user(self):
        if self.nguoi_tao_id and not self.chu_ky_nguoi_tao:
            chu_ky = _lay_chu_ky_profile(self.nguoi_tao)
            self.chu_ky_nguoi_tao = chu_ky.name if chu_ky else None

        if self.duyet_at and self.nguoi_duyet_id and not self.chu_ky_nguoi_duyet:
            chu_ky = _lay_chu_ky_profile(self.nguoi_duyet)
            self.chu_ky_nguoi_duyet = chu_ky.name if chu_ky else None
        elif not self.duyet_at:
            self.chu_ky_nguoi_duyet = None

    def _cap_nhat_khoang_thoi_gian_tuan(self):
        if self.nam < 2000 or self.nam > 2100:
            raise ValidationError({"nam": "Năm không hợp lệ."})
        if self.tuan < 1 or self.tuan > 53:
            raise ValidationError({"tuan": "Tuần phải nằm trong khoảng 1-53."})
        try:
            week_start = date.fromisocalendar(self.nam, self.tuan, 1)
        except ValueError:
            raise ValidationError({"tuan": "Tuần không hợp lệ với năm đã chọn."})
        self.tuan_bat_dau = week_start
        self.tuan_ket_thuc = date.fromisocalendar(self.nam, self.tuan, 7)

    def clean(self):
        self._cap_nhat_khoang_thoi_gian_tuan()
        if self.tuan_bat_dau and self.tuan_ket_thuc and self.tuan_ket_thuc < self.tuan_bat_dau:
            raise ValidationError({"tuan_ket_thuc": "Ngày kết thúc tuần phải lớn hơn hoặc bằng ngày bắt đầu."})

    def save(self, *args, **kwargs):
        self._cap_nhat_khoang_thoi_gian_tuan()
        self.dong_bo_chu_ky_tu_user()
        self.full_clean()
        if self.duyet_at and self.nguoi_duyet_id:
            self.trang_thai = self.TrangThai.DA_DUYET
        elif not self.duyet_at and not self.nguoi_duyet_id and self.trang_thai == self.TrangThai.DA_DUYET:
            self.trang_thai = self.TrangThai.CHO_DUYET
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Sổ chuyển đổi thiết bị tuần {self.tuan}/{self.nam} - Ca {self.ca_truc}"


class LanChuyenDoiThietBi(TimestampedUUIDModel):
    so = models.ForeignKey(
        SoChuyenDoiThietBiTuan,
        on_delete=models.CASCADE,
        related_name="lan_chuyen_dois",
        verbose_name="Sổ chuyển đổi tuần",
    )
    thoi_gian = models.DateTimeField(default=timezone.now, verbose_name="Thời gian chuyển đổi")
    nguoi_thuc_hien = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lan_chuyen_doi_thiet_bi_da_thuc_hien",
        null=True,
        blank=True,
        verbose_name="Người thực hiện",
    )
    ghi_chu_chung = models.TextField(blank=True, verbose_name="Ghi chú chung")

    class Meta:
        ordering = ["thoi_gian", "created_at"]
        verbose_name = "Lần chuyển đổi thiết bị tuần"
        verbose_name_plural = "Lần chuyển đổi thiết bị tuần"

    def clean(self):
        if self.so_id and self.thoi_gian:
            thoi_gian_date = timezone.localtime(self.thoi_gian).date() if timezone.is_aware(self.thoi_gian) else self.thoi_gian.date()
            if thoi_gian_date < self.so.tuan_bat_dau or thoi_gian_date > self.so.tuan_ket_thuc:
                raise ValidationError({"thoi_gian": "Thời gian chuyển đổi phải nằm trong tuần của sổ."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Lần chuyển đổi {self.thoi_gian:%Y-%m-%d %H:%M}"


class ChiTietChuyenDoiThietBi(TimestampedUUIDModel):
    class TrangThai(models.TextChoices):
        LAM_VIEC = "lam_viec", "Làm việc"
        DU_PHONG = "du_phong", "Dự phòng"

    lan_chuyen_doi = models.ForeignKey(
        LanChuyenDoiThietBi,
        on_delete=models.CASCADE,
        related_name="chi_tiets",
        verbose_name="Lần chuyển đổi",
    )
    thiet_bi = models.ForeignKey(
        "quanlyvanhanh.ThietBi",
        on_delete=models.PROTECT,
        related_name="chi_tiet_chuyen_doi_thiet_bi",
        verbose_name="Thiết bị",
    )
    khu_vuc = models.ForeignKey(
        KhuVucChuyenDoiThietBi,
        on_delete=models.PROTECT,
        related_name="chi_tiet_lich_su",
        null=True,
        blank=True,
        verbose_name="Tổ máy / Khu vực",
    )
    to_may = models.CharField(max_length=50, verbose_name="Mã tổ máy / Khu vực")
    ten_khu_vuc_snapshot = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Tên khu vực tại thời điểm tạo sổ",
    )
    nhom_thiet_bi = models.CharField(max_length=255, blank=True, verbose_name="Nhóm thiết bị")
    trang_thai = models.CharField(
        max_length=20,
        choices=TrangThai.choices,
        blank=True,
        verbose_name="Trạng thái chuyển đổi",
    )
    ghi_chu = models.TextField(blank=True, verbose_name="Ghi chú")
    thu_tu = models.PositiveIntegerField(default=1, verbose_name="Thứ tự")

    class Meta:
        ordering = ["to_may", "thu_tu", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lan_chuyen_doi", "thiet_bi"],
                name="uq_chi_tiet_chuyen_doi_lan_thiet_bi",
            )
        ]
        verbose_name = "Chi tiết chuyển đổi thiết bị tuần"
        verbose_name_plural = "Chi tiết chuyển đổi thiết bị tuần"

    def __str__(self):
        return f"{self.thiet_bi} - {self.get_trang_thai_display() or 'Chưa chọn'}"
