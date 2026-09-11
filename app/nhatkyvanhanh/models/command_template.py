import uuid

from django.conf import settings
from django.db import models


NHOM_MAU_CHOICES = (
    ("khoi_dong_hoa_luoi", "Khởi động & Hòa lưới"),
    ("dung_tach_may", "Dừng & Tách lưới"),
    ("dong_cat_mc", "Thao tác Đóng/Cắt MC"),
    ("phieu_thao_tac", "Phiếu thao tác"),
    ("phieu_cong_tac", "Phiếu công tác"),
    ("dieu_do_p", "Thay đổi công suất"),
    ("cong_tac_co_lap", "Công tác & Cô lập"),
    ("thuy_van_van_tran", "Thủy văn & Van tràn"),
    ("khac", "Khác"),
)


class MauNoiDungVanHanh(models.Model):
    """
    Model lưu trữ mẫu câu lệnh / nội dung vận hành động cho Sổ Giao Nhận Ca VH.
    Hỗ trợ mẫu chung toàn hệ thống (nha_may=None, la_mau_he_thong=True)
    và mẫu tùy biến riêng theo từng nhà máy (nha_may=X, ghi đè mẫu hệ thống cùng ma_mau).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="mau_noi_dung_van_hanh",
        verbose_name="Nhà máy",
        help_text="Để trống nếu là mẫu chung hệ thống",
    )
    ma_mau = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name="Mã mẫu",
        help_text="Mã định danh duy nhất của mẫu (ví dụ: hoa_luoi, dung_may, lenh_dieu_do_p)",
    )
    ten_mau = models.CharField(
        max_length=150,
        verbose_name="Tên mẫu",
        help_text="Tên hiển thị trực quan của mẫu câu",
    )
    nhom_mau = models.CharField(
        max_length=50,
        choices=NHOM_MAU_CHOICES,
        default="khac",
        verbose_name="Nhóm nghiệp vụ",
    )
    dinh_dang_tieu_de = models.CharField(
        max_length=255,
        verbose_name="Định dạng tiêu đề",
        help_text="Cú pháp tiêu đề chứa placeholders {ten_tham_so}",
    )
    dinh_dang_mau = models.TextField(
        verbose_name="Định dạng nội dung mẫu",
        help_text="Cú pháp nội dung chứa placeholders {ten_tham_so}",
    )
    danh_sach_tham_so = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Danh sách tham số",
        help_text="Cấu hình danh sách các trường tham số điền nhanh (JSON schema)",
    )
    thu_tu = models.PositiveIntegerField(
        default=0,
        verbose_name="Thứ tự hiển thị",
    )
    phien_ban = models.PositiveIntegerField(
        default=1,
        verbose_name="Phiên bản",
    )
    dang_ap_dung = models.BooleanField(
        default=True,
        verbose_name="Đang áp dụng",
        help_text="Chỉ có duy nhất 1 phiên bản được áp dụng cho mỗi mã mẫu trong cùng phạm vi",
    )
    la_mau_he_thong = models.BooleanField(
        default=False,
        verbose_name="Mẫu hệ thống",
        help_text="Mẫu mặc định của toàn hệ thống, không thể xóa",
    )
    ghi_chu = models.TextField(
        blank=True,
        default="",
        verbose_name="Ghi chú",
    )
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mau_noi_dung_vh_da_tao",
        verbose_name="Người tạo",
    )
    nguoi_cap_nhat = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mau_noi_dung_vh_da_cap_nhat",
        verbose_name="Người cập nhật",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["thu_tu", "ma_mau", "-phien_ban"]
        verbose_name = "Mẫu nội dung vận hành"
        verbose_name_plural = "Mẫu nội dung vận hành"
        constraints = [
            # Ràng buộc 1: Mỗi phiên bản của mã mẫu chung hệ thống là duy nhất
            models.UniqueConstraint(
                fields=["ma_mau", "phien_ban"],
                condition=models.Q(nha_may__isnull=True),
                name="uq_mau_noi_dung_vh_global_ma_phien_ban",
            ),
            # Ràng buộc 2: Mỗi phiên bản của mã mẫu tại từng nhà máy là duy nhất
            models.UniqueConstraint(
                fields=["nha_may", "ma_mau", "phien_ban"],
                condition=models.Q(nha_may__isnull=False),
                name="uq_mau_noi_dung_vh_plant_ma_phien_ban",
            ),
            # Ràng buộc 3: Chỉ có tối đa 1 phiên bản đang áp dụng cho mỗi mã mẫu hệ thống
            models.UniqueConstraint(
                fields=["ma_mau"],
                condition=models.Q(nha_may__isnull=True, dang_ap_dung=True),
                name="uq_mau_noi_dung_vh_global_active",
            ),
            # Ràng buộc 4: Chỉ có tối đa 1 phiên bản đang áp dụng cho mỗi mã mẫu tại nhà máy
            models.UniqueConstraint(
                fields=["nha_may", "ma_mau"],
                condition=models.Q(nha_may__isnull=False, dang_ap_dung=True),
                name="uq_mau_noi_dung_vh_plant_active",
            ),
        ]
        permissions = [
            ("activate_maunoidungvanhanh", "Có quyền kích hoạt mẫu nội dung vận hành"),
        ]

    def __str__(self):
        plant_label = self.nha_may.ma_nha_may if self.nha_may else "Hệ thống"
        return f"{self.ten_mau} ({self.ma_mau} v{self.phien_ban}) - {plant_label}"
