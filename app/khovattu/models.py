# apps/kho/models.py
import  uuid as _uuid
import urllib.parse
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.db.models import Q  # <-- BỔ SUNG: cần cho CheckConstraint
from django.contrib.auth.models import AbstractUser

# ===== Danh mục =====

class Bang_nha_may(models.Model):
    id = models.BigAutoField(primary_key=True)
    ma_nha_may = models.CharField(max_length=50, unique=True)
    ten_nha_may = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Nhà máy"
        verbose_name_plural = "Nhà máy"

    def __str__(self):
        return f"{self.ma_nha_may} - {self.ten_nha_may}"


class Bang_vi_tri(models.Model):
    id = models.BigAutoField(primary_key=True)
    # Mã vị trí rút gọn do kho quy ước, ví dụ "A1"
    ma_vi_tri = models.CharField(max_length=50, unique=True)
    # Quy chiếu chi tiết
    ma_he_thong = models.CharField(max_length=100)            # VD: "Đập tràn"
    kho = models.CharField(max_length=20)                      # "1", "2", ...
    ke = models.CharField(max_length=20)                       # "A", "B", ...
    ngan = models.CharField(max_length=20)                     # "1", "2", ...
    tang = models.CharField(max_length=20)                     # "1", "2", ...
    mo_ta = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Vị trí kho"
        verbose_name_plural = "Vị trí kho"
        indexes = [models.Index(fields=["ma_vi_tri"])]

    def __str__(self):
        return f"{self.ma_vi_tri} | Hệ:{self.ma_he_thong} Kho:{self.kho} Kệ:{self.ke} Ngăn:{self.ngan} Tầng:{self.tang}"


class Bang_xuat_xu(models.Model):
    """
    Bảng mã xuất xứ để map country code từ mã Bravo
    """
    ma_country = models.CharField(max_length=10, primary_key=True, help_text="Mã country (VIE, USA, KOR, etc.)")
    ten_nuoc = models.CharField(max_length=100, help_text="Tên nước đầy đủ")
    ten_viet_tat = models.CharField(max_length=50, blank=True, null=True, help_text="Tên viết tắt")
    mo_ta = models.TextField(blank=True, null=True, help_text="Mô tả thêm")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bang_xuat_xu"
        verbose_name = "Xuất xứ"
        verbose_name_plural = "Danh sách xuất xứ"

    def __str__(self):
        return f"{self.ma_country} - {self.ten_nuoc}"


# ===== Vật tư =====

class Bang_vat_tu(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True)

    # Thông tin vật tư
    ten_vat_tu = models.CharField(max_length=255)
    don_vi = models.CharField(max_length=50)
    thong_so_ky_thuat = models.CharField(max_length=500, blank=True, null=True)

    # Liên kết danh mục
    ma_vi_tri = models.ForeignKey(
        Bang_vi_tri, on_delete=models.PROTECT, related_name="vat_tu", null=True, blank=True
    )
    bang_nha_may = models.ForeignKey(
        Bang_nha_may, on_delete=models.PROTECT, related_name="vat_tu", null=True, blank=True
    )
    xuat_xu = models.ForeignKey(
        Bang_xuat_xu, on_delete=models.PROTECT, related_name="vat_tu", null=True, blank=True,
        help_text="Xuất xứ vật tư (tự động map từ mã Bravo)"
    )

    # Định danh duy nhất dùng để FK ở các bảng nghiệp vụ
    ma_bravo = models.CharField(max_length=100, db_index=True)

    # Tồn kho & kế hoạch (không âm)
    ton_kho = models.IntegerField(default=0)
    so_luong_kh = models.IntegerField(default=0)

    # QR & hình ảnh
    ma_QR = models.ImageField(upload_to="qr_codes/", blank=True, null=True)
    hinh_anh_vt = models.ImageField(upload_to="vat_tu/", blank=True, null=True)  # Hình ảnh chính (giữ lại để tương thích)

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Vật tư"
        verbose_name_plural = "Vật tư"
        indexes = [
            models.Index(fields=["ten_vat_tu"]),
            models.Index(fields=["ma_bravo"]),   # dù đã unique, index giúp query nhanh
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["bang_nha_may", "ma_bravo"], name="uniq_vattu_nhamay_mabravo"
            ),
            models.CheckConstraint(check=Q(ton_kho__gte=0), name="chk_vattu_ton_kho_gte_0"),
            models.CheckConstraint(check=Q(so_luong_kh__gte=0), name="chk_vattu_so_luong_kh_gte_0"),
        ]

    def __str__(self):
        return f"{self.ma_bravo} - {self.ten_vat_tu}"

    def ensure_qr_image(self, force=False):
        """
        Tạo QR code cho vật tư nếu chưa có hoặc force=True
        """
        if not force and self.ma_QR:
            return  # Đã có QR code và không force

        try:
            import qrcode
            from PIL import Image, ImageDraw
            from django.core.files.base import ContentFile
            import io

            # Tạo QR code data - URL dẫn đến trang chi tiết vật tư
            # Format: http://192.168.0.4:3000/kho/vat-tu/{ma_nha_may}/{ma_bravo}
            from django.conf import settings
            base_url = getattr(settings, 'KHO_QR_FRONTEND_BASE', 'http://192.168.0.4:3000')
            ma_nha_may = self.bang_nha_may.ma_nha_may if self.bang_nha_may else 'VS'
            qr_data = f"{base_url}/kho/vat-tu/{ma_nha_may}/{self.ma_bravo}"

            # Tạo QR code với kích thước 15x15mm (tương đương 57x57 pixels ở 96 DPI)
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=4,
                border=2,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)

            # Tạo image
            qr_image = qr.make_image(fill_color="black", back_color="white")

            # Resize về kích thước 15x15mm (57x57 pixels ở 96 DPI)
            qr_image = qr_image.resize((57, 57), Image.Resampling.LANCZOS)

            # Thêm border trắng để dễ cắt
            final_size = 80  # 80x80 pixels
            final_image = Image.new('RGB', (final_size, final_size), 'white')
            paste_x = (final_size - 57) // 2
            paste_y = (final_size - 57) // 2
            final_image.paste(qr_image, (paste_x, paste_y))

            # Lưu vào memory
            img_io = io.BytesIO()
            final_image.save(img_io, format='PNG', quality=95)
            img_io.seek(0)

            # Tạo tên file
            filename = f"qr_{self.ma_bravo.replace('.', '_')}.png"

            # Lưu vào field ma_QR
            self.ma_QR.save(
                filename,
                ContentFile(img_io.getvalue()),
                save=False
            )

        except Exception as e:
            # Log error nhưng không crash
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating QR for {self.ma_bravo}: {e}")
            # Không raise exception để không làm crash import process


# ===== Hình ảnh vật tư (nhiều hình) =====

class Bang_hinh_anh_vat_tu(models.Model):
    """
    Model để lưu nhiều hình ảnh cho mỗi vật tư
    """
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=_uuid.uuid4, editable=False, unique=True)

    # Liên kết với vật tư
    vat_tu = models.ForeignKey(
        Bang_vat_tu,
        on_delete=models.CASCADE,
        related_name="hinh_anh_list",
        help_text="Vật tư liên kết"
    )

    # Hình ảnh
    hinh_anh = models.ImageField(
        upload_to="vat_tu/images/",
        help_text="Hình ảnh vật tư"
    )

    # Thông tin bổ sung
    mo_ta = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Mô tả hình ảnh (tùy chọn)"
    )

    # Thứ tự hiển thị
    thu_tu = models.PositiveIntegerField(
        default=0,
        help_text="Thứ tự hiển thị hình ảnh"
    )

    # Trạng thái
    is_active = models.BooleanField(
        default=True,
        help_text="Trạng thái hoạt động"
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hình ảnh vật tư"
        verbose_name_plural = "Hình ảnh vật tư"
        ordering = ['thu_tu', 'created_at']
        indexes = [
            models.Index(fields=["vat_tu", "thu_tu"]),
            models.Index(fields=["vat_tu", "is_active"]),
        ]

    def __str__(self):
        ma_bravo = self.vat_tu.ma_bravo if self.vat_tu else "Unknown"
        return f"{ma_bravo} - Hình {self.thu_tu}"




# ===== Nghiệp vụ: kiểm kê / đề nghị nhập / đề nghị xuất =====

class Bang_kiem_ke(models.Model):
    id = models.BigAutoField(primary_key=True)
    so_thu_tu = models.IntegerField()
    # Thêm trường để so sánh trực tiếp
    ma_bravo = models.CharField(max_length=100, default="", help_text="Mã Bravo để so sánh với bảng vật tư")
    ma_nha_may = models.CharField(max_length=20, default="", help_text="Mã nhà máy để so sánh với bảng vật tư")
    # Liên kết qua ma_bravo (to_field)
    vat_tu = models.ForeignKey(Bang_vat_tu, on_delete=models.PROTECT, related_name="kiem_ke", null=True, blank=True)  # <— có thể null
    ten_vat_tu = models.CharField(max_length=255)
    don_vi = models.CharField(max_length=50)
    so_luong = models.IntegerField(help_text="Số lượng kiểm kê (dự kiến)")
    so_luong_thuc_te = models.IntegerField(default=0, help_text="Số lượng thực tế khi kiểm kê")

    class Meta:
        verbose_name = "Phiếu kiểm kê"
        verbose_name_plural = "Phiếu kiểm kê"


class Bang_de_nghi_nhap(models.Model):
    id = models.BigAutoField(primary_key=True)
    stt = models.IntegerField()
    vat_tu = models.ForeignKey(Bang_vat_tu, on_delete=models.PROTECT, related_name="de_nghi_nhap")  # <— không to_field
    ma_bravo_text = models.CharField(max_length=100, blank=True)  # lưu lại mã gốc trong file Excel (log)
    ten_vat_tu = models.CharField(max_length=255)
    don_vi = models.CharField(max_length=50)
    so_luong = models.IntegerField()
    don_gia = models.BigIntegerField(default=0)  # Đơn giá (VND)
    thanh_tien = models.BigIntegerField(default=0)
    so_de_nghi_cap = models.CharField(max_length=50, blank=True)  # Số đề nghị cung cấp (String)
    ngay_de_nghi = models.DateTimeField()
    bo_phan = models.CharField(max_length=100, blank=True)  # Bộ phận đề nghị
    ghi_chu = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        verbose_name = "Đề nghị nhập"
        verbose_name_plural = "Đề nghị nhập"


class Bang_de_nghi_xuat(models.Model):
    id = models.BigAutoField(primary_key=True)
    stt = models.IntegerField()
    vat_tu = models.ForeignKey(Bang_vat_tu, on_delete=models.PROTECT, related_name="de_nghi_xuat")  # <— không to_field
    ma_bravo_text = models.CharField(max_length=100, blank=True)
    ten_vat_tu = models.CharField(max_length=255)
    don_vi = models.CharField(max_length=50)
    so_luong = models.IntegerField()
    ngay_de_nghi_xuat = models.DateTimeField()
    ghi_chu = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        verbose_name = "Đề nghị xuất"
        verbose_name_plural = "Đề nghị xuất"



