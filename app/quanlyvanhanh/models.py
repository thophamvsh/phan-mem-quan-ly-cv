from django.db import models
from django.utils.text import slugify
from django.utils import timezone

# -------------------------
# BẢNG THIẾT BỊ (CÂY)
# -------------------------
class ThietBi(models.Model):
    ten = models.CharField(max_length=255, verbose_name="Tên")
    ma = models.CharField(max_length=100, verbose_name="Mã cấp hiện tại")  # VD: GE, OD, PD.01
    ma_day_du = models.CharField(max_length=255, unique=True, db_index=True, verbose_name="Mã đầy đủ")  # VD: SH.TB.H1.GE.OD.PD.01

    cha = models.ForeignKey(
        "self", null=True, blank=True, related_name="con",
        on_delete=models.CASCADE, verbose_name="Thiết bị cha"
    )

    loai = models.CharField(max_length=100, blank=True, verbose_name="Loại/Phân loại")
    trang_thai = models.CharField(max_length=32, blank=True, verbose_name="Trạng thái")

    nha_che_tao = models.CharField(max_length=255, blank=True, verbose_name="Nhà chế tạo")
    nha_cung_cap = models.CharField(max_length=255, blank=True, verbose_name="Nhà cung cấp")
    nuoc_san_xuat = models.CharField(max_length=64, blank=True, verbose_name="Nước sản xuất")
    nha_may = models.CharField(max_length=64, blank=True, verbose_name="Nhà máy/khu vực")

    do_uu_tien = models.PositiveSmallIntegerField(default=0, verbose_name="Mức ưu tiên")
    so_serial = models.CharField(max_length=255, blank=True, verbose_name="Số S/N")
    ma_van_hanh = models.CharField(max_length=100, blank=True, verbose_name="Mã vận hành")
    bo_phan_quan_ly = models.CharField(max_length=255, blank=True, verbose_name="Bộ phận quản lý")
    bang_ve = models.CharField(max_length=255, blank=True, verbose_name="Bảng vẽ")
    mo_ta_ky_thuat = models.TextField(blank=True, null=True, verbose_name="Thông số kỹ thuật (text)")

    # Ngày tháng
    ngay_lap_dat = models.DateField(null=True, blank=True, verbose_name="Ngày lắp đặt")
    ngay_dua_vao_van_hanh = models.DateField(null=True, blank=True, verbose_name="Ngày đưa vào vận hành")

    # Hình ảnh
    hinh_anh = models.ImageField(upload_to="thiet_bi/", blank=True, null=True, verbose_name="Hình ảnh thiết bị")

    cap = models.PositiveSmallIntegerField(default=0, editable=False, verbose_name="Cấp")
    thu_tu = models.PositiveIntegerField(default=0, verbose_name="Thứ tự hiển thị")
    slug = models.SlugField(max_length=255, blank=True)

    class Meta:
        db_table = "thiet_bi"
        verbose_name = "Thiết bị"
        verbose_name_plural = "Thiết bị"
        indexes = [
            models.Index(fields=["cha", "thu_tu"]),
            models.Index(fields=["cap", "ten"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["cha", "ma"], name="uq_thietbi_cha_ma"),
        ]
        ordering = ["cha__id", "thu_tu", "ten"]

    def __str__(self):
        return f"{self.ma_day_du} - {self.ten}"

    def save(self, *args, **kwargs):
        # tính cấp
        self.cap = (self.cha.cap + 1) if self.cha_id else 0
        # tính mã đầy đủ
        if self.cha_id:
            self.ma_day_du = f"{self.cha.ma_day_du}.{self.ma}"
        else:
            self.ma_day_du = self.ma
        # slug
        if not self.slug:
            self.slug = slugify(self.ma_day_du)
        super().save(*args, **kwargs)


# -------------------------
# DANH MỤC VẬT TƯ
# -------------------------
class VatTu(models.Model):
    ma_vat_tu = models.CharField(max_length=100, unique=True, verbose_name="Mã vật tư")
    ten_vat_tu = models.CharField(max_length=255, verbose_name="Tên vật tư")
    don_vi_tinh = models.CharField(max_length=32, blank=True, verbose_name="Đơn vị tính")
    quy_cach = models.CharField(max_length=255, blank=True, verbose_name="Quy cách/Mô tả")
    nha_che_tao = models.CharField(max_length=255, blank=True, verbose_name="Nhà chế tạo")
    nha_cung_cap = models.CharField(max_length=255, blank=True, verbose_name="Nhà cung cấp")

    class Meta:
        db_table = "vat_tu"
        verbose_name = "Vật tư"
        verbose_name_plural = "Vật tư"

    def __str__(self):
        return f"{self.ma_vat_tu} - {self.ten_vat_tu}"


class ThietBiVatTu(models.Model):
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.CASCADE, verbose_name="Thiết bị")
    vat_tu = models.ForeignKey(VatTu, on_delete=models.CASCADE, verbose_name="Vật tư")
    so_luong = models.DecimalField(max_digits=12, decimal_places=3, default=1, verbose_name="Số lượng")
    ghi_chu = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        db_table = "thiet_bi_vat_tu"
        verbose_name = "Vật tư gắn với thiết bị"
        verbose_name_plural = "Vật tư gắn với thiết bị"
        constraints = [
            models.UniqueConstraint(fields=["thiet_bi", "vat_tu"], name="uq_tb_vt"),
        ]


# -------------------------
# THÔNG SỐ VẬN HÀNH
# -------------------------
class ThongSoVanHanh(models.Model):
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.CASCADE, verbose_name="Thiết bị")
    ma_thong_so = models.CharField(max_length=100, blank=True, verbose_name="Mã thông số vận hành")
    ten_thong_so = models.CharField(max_length=128, verbose_name="Tên thông số")
    gia_tri = models.CharField(max_length=255, blank=True, null=True, verbose_name="Giá trị")
    don_vi = models.CharField(max_length=32, blank=True, verbose_name="Đơn vị")
    gia_tri_toi_thieu = models.CharField(max_length=64, blank=True, null=True,verbose_name="Min")
    gia_tri_toi_da = models.CharField(max_length=64, blank=True, null=True, verbose_name="Max")
    gia_tri_thiet_ke = models.CharField(max_length=64, blank=True, null=True, verbose_name="Giá trị thiết kế")
    ky_hieu_van_hanh = models.CharField(max_length=32, blank=True, verbose_name="Ký hiệu vận hành")
    nha_may = models.CharField(max_length=64, blank=True, verbose_name="Nhà máy")
    ghi_chu = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    # Thời điểm nhập thông số
    thoi_diem_nhap = models.DateTimeField(verbose_name="Thời điểm nhập thông số")
    ngay_nhap = models.DateField(verbose_name="Ngày nhập thông số")
    nguoi_nhap = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Người nhập", related_name="thongsovanhanh_nhap"
    )

    class Meta:
        db_table = "thong_so_van_hanh"
        verbose_name = "Thông số vận hành"
        verbose_name_plural = "Thông số vận hành"
        constraints = [
            models.UniqueConstraint(fields=["thiet_bi", "ten_thong_so", "thoi_diem_nhap"], name="uq_tsvh_tb_ten_time"),
        ]


# -------------------------
# AN TOÀN THIẾT BỊ
# -------------------------
class AnToanThietBi(models.Model):
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.CASCADE, verbose_name="Thiết bị")
    moi_nguy = models.CharField(max_length=255, verbose_name="Mối nguy")
    bien_phap = models.TextField(blank=True, verbose_name="Biện pháp")
    bao_ho_lao_dong = models.CharField(max_length=255, blank=True, verbose_name="PPE")
    ghi_chu = models.CharField(max_length=255, blank=True, verbose_name="Ghi chú")

    class Meta:
        db_table = "an_toan_thiet_bi"
        verbose_name = "An toàn thiết bị"
        verbose_name_plural = "An toàn thiết bị"


# -------------------------
# ĐÍNH KÈM
# -------------------------
class DinhKem(models.Model):
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.CASCADE, verbose_name="Thiết bị")
    tieu_de = models.CharField(max_length=255, verbose_name="Tiêu đề")
    tep = models.FileField(upload_to="dinh_kem/", blank=True, null=True, verbose_name="Tệp")
    duong_dan = models.URLField(blank=True, verbose_name="URL")
    dinh_dang = models.CharField(max_length=64, blank=True, verbose_name="MIME/Định dạng")
    ngay_tai_len = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tải lên")

    class Meta:
        db_table = "dinh_kem"
        verbose_name = "Đính kèm"
        verbose_name_plural = "Đính kèm"


# -------------------------
# THÔNG SỐ TỔ MÁY
# -------------------------
class ThongSoToMay(models.Model):
    # Thông tin cơ bản
    ten_thong_so = models.CharField(max_length=255, verbose_name="Tên thông số")
    ma_thong_so = models.CharField(max_length=100, verbose_name="Mã thông số")
    don_vi = models.CharField(max_length=50, verbose_name="Đơn vị")

    # Thông tin thiết bị
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.CASCADE, verbose_name="Thiết bị")
    nha_may = models.CharField(max_length=64, verbose_name="Nhà máy")
    ky_hieu_van_hanh = models.CharField(max_length=100, blank=True, verbose_name="Ký hiệu vận hành")

    # Dữ liệu thông số
    gia_tri = models.CharField(max_length=255, null=True, blank=True, verbose_name="Giá trị")
    ghi_chu = models.TextField(blank=True, verbose_name="Ghi chú")

    # Thời gian
    thoi_diem_nhap = models.DateTimeField(verbose_name="Thời điểm nhập")
    ngay_nhap = models.DateField(verbose_name="Ngày nhập")
    nguoi_nhap = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Người nhập", related_name="thongsotomay_nhap"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")

    class Meta:
        db_table = "thong_so_to_may"
        verbose_name = "Thông số tổ máy"
        verbose_name_plural = "Thông số tổ máy"
        unique_together = [['thiet_bi', 'ten_thong_so', 'thoi_diem_nhap', 'ngay_nhap']]
        indexes = [
            models.Index(fields=['ngay_nhap', 'thoi_diem_nhap']),
            models.Index(fields=['thiet_bi', 'ngay_nhap']),
            models.Index(fields=['ten_thong_so', 'ngay_nhap']),
        ]

    def __str__(self):
        return f"{self.ten_thong_so} - {self.thiet_bi.ten} - {self.ngay_nhap} {self.thoi_diem_nhap}"


# -------------------------
# THÔNG SỐ TRẠM 110KV
# -------------------------
class ThongSoTram110KV(models.Model):
    # Thông tin cơ bản
    ten_thong_so = models.CharField(max_length=255, verbose_name="Tên thông số")
    ma_thong_so = models.CharField(max_length=100, verbose_name="Mã thông số")
    don_vi = models.CharField(max_length=50, verbose_name="Đơn vị")

    # Thông tin thiết bị
    thiet_bi = models.ForeignKey(ThietBi, on_delete=models.CASCADE, verbose_name="Thiết bị")
    nha_may = models.CharField(max_length=64, verbose_name="Nhà máy")
    ky_hieu_van_hanh = models.CharField(max_length=100, blank=True, verbose_name="Ký hiệu vận hành")

    # Dữ liệu thông số
    gia_tri = models.CharField(max_length=255, null=True, blank=True, verbose_name="Giá trị")
    ghi_chu = models.TextField(blank=True, verbose_name="Ghi chú")

    # Thời gian
    thoi_diem_nhap = models.DateTimeField(verbose_name="Thời điểm nhập")
    ngay_nhap = models.DateField(verbose_name="Ngày nhập")
    nguoi_nhap = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Người nhập", related_name="thongsotram_nhap"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")

    class Meta:
        db_table = "thong_so_tram_110kv"
        verbose_name = "Thông số trạm 110kV"
        verbose_name_plural = "Thông số trạm 110kV"
        unique_together = [['thiet_bi', 'ten_thong_so', 'thoi_diem_nhap', 'ngay_nhap']]
        indexes = [
            models.Index(fields=['ngay_nhap', 'thoi_diem_nhap']),
            models.Index(fields=['thiet_bi', 'ngay_nhap']),
            models.Index(fields=['ten_thong_so', 'ngay_nhap']),
        ]

    def __str__(self):
        return f"{self.ten_thong_so} - {self.thiet_bi.ten} - {self.ngay_nhap} {self.thoi_diem_nhap}"


# -------------------------
# CẤU HÌNH NGƯỠNG THÔNG SỐ (ALARM, TRIP, ĐỊNH MỨC)
# -------------------------
class NguongThongSo(models.Model):
    nha_may = models.CharField(max_length=64, blank=True, verbose_name="Nhà máy")
    thiet_bi = models.ForeignKey(
        ThietBi, on_delete=models.CASCADE, null=True, blank=True,
        related_name="nguong_thong_so", verbose_name="Thiết bị"
    )
    ma_thong_so = models.CharField(max_length=100, db_index=True, verbose_name="Mã thông số")
    ten_thong_so = models.CharField(max_length=255, blank=True, verbose_name="Tên thông số")
    don_vi = models.CharField(max_length=50, blank=True, verbose_name="Đơn vị")

    alarm = models.FloatField(null=True, blank=True, verbose_name="Ngưỡng cảnh báo (Alarm)")
    trip = models.FloatField(null=True, blank=True, verbose_name="Ngưỡng sự cố (Trip)")
    rated = models.FloatField(null=True, blank=True, verbose_name="Giá trị định mức (Rated)")
    min_value = models.FloatField(null=True, blank=True, verbose_name="Giá trị nhỏ nhất (Min)")
    max_value = models.FloatField(null=True, blank=True, verbose_name="Giá trị lớn nhất (Max)")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")

    class Meta:
        db_table = "nguong_thong_so"
        verbose_name = "Ngưỡng thông số"
        verbose_name_plural = "Ngưỡng thông số"
        unique_together = [['nha_may', 'thiet_bi', 'ma_thong_so']]

    def clean(self):
        super().clean()

        # Tự động ánh xạ thiết bị nếu bị bỏ trống nhưng có mã thông số
        if not self.thiet_bi and self.ma_thong_so:
            from django.db.models import Q
            from quanlyvanhanh.models import ThongSoToMay, ThongSoTram110KV, ThongSoVanHanh

            # 1. Thử tìm thiết bị từ ThongSoToMay
            qs = ThongSoToMay.objects.filter(ma_thong_so=self.ma_thong_so)
            if self.nha_may:
                qs = qs.filter(Q(nha_may=self.nha_may) | Q(nha_may__icontains=self.nha_may))
            rec = qs.first()
            if rec and rec.thiet_bi:
                self.thiet_bi = rec.thiet_bi
                return

            # 2. Thử tìm thiết bị từ ThongSoTram110KV
            qs = ThongSoTram110KV.objects.filter(ma_thong_so=self.ma_thong_so)
            if self.nha_may:
                qs = qs.filter(Q(nha_may=self.nha_may) | Q(nha_may__icontains=self.nha_may))
            rec = qs.first()
            if rec and rec.thiet_bi:
                self.thiet_bi = rec.thiet_bi
                return

            # 3. Thử tìm thiết bị từ ThongSoVanHanh
            qs = ThongSoVanHanh.objects.filter(ma_thong_so=self.ma_thong_so)
            if self.nha_may:
                qs = qs.filter(Q(nha_may=self.nha_may) | Q(nha_may__icontains=self.nha_may))
            rec = qs.first()
            if rec and rec.thiet_bi:
                self.thiet_bi = rec.thiet_bi
                return

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        device_str = self.thiet_bi.ma_day_du if self.thiet_bi else "Mặc định"
        return f"{self.nha_may} - {device_str} - {self.ma_thong_so}"


