import uuid

from django.conf import settings
from django.db import models


class MauTomLuocGiaoCaVH(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.PROTECT,
        related_name="mau_tom_luoc_giao_ca_vh",
        verbose_name="Nhà máy",
    )
    ten_mau = models.CharField(max_length=255, verbose_name="Tên mẫu")
    phien_ban = models.PositiveIntegerField(default=1, verbose_name="Phiên bản")
    dang_ap_dung = models.BooleanField(default=False, verbose_name="Đang áp dụng")
    ghi_chu = models.TextField(blank=True, verbose_name="Ghi chú")
    nguoi_tao = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mau_tom_luoc_giao_ca_vh_da_tao",
        null=True,
        blank=True,
        verbose_name="Người tạo",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nha_may__ten_nha_may", "-phien_ban"]
        constraints = [
            models.UniqueConstraint(
                fields=["nha_may", "phien_ban"],
                name="uq_mau_tom_luoc_vh_nha_may_phien_ban",
            ),
            models.UniqueConstraint(
                fields=["nha_may"],
                condition=models.Q(dang_ap_dung=True),
                name="uq_mau_tom_luoc_vh_dang_ap_dung",
            ),
        ]
        permissions = [
            ("activate_mautomluocgiaocavh", "Có quyền kích hoạt mẫu tóm lược giao ca vận hành"),
        ]
        verbose_name = "Mẫu tóm lược giao ca vận hành"
        verbose_name_plural = "Mẫu tóm lược giao ca vận hành"

    @property
    def da_duoc_su_dung(self):
        return self.so_giao_nhan_ca_vh.exists()

    def __str__(self):
        return f"{self.nha_may} - {self.ten_mau} v{self.phien_ban}"


class HangMucMauTomLuocGiaoCaVH(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mau = models.ForeignKey(
        MauTomLuocGiaoCaVH,
        on_delete=models.CASCADE,
        related_name="hang_muc",
        verbose_name="Mẫu",
    )
    ten_hang_muc = models.CharField(max_length=255, verbose_name="Hạng mục")
    noi_dung_mac_dinh = models.TextField(blank=True, verbose_name="Nội dung mặc định")
    ghi_chu_mac_dinh = models.CharField(max_length=500, blank=True, verbose_name="Ghi chú mặc định")
    bat_buoc = models.BooleanField(default=False, verbose_name="Bắt buộc")
    thu_tu = models.PositiveIntegerField(default=1, verbose_name="Thứ tự")

    class Meta:
        ordering = ["thu_tu", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["mau", "ten_hang_muc"],
                name="uq_hang_muc_mau_tom_luoc_vh",
            ),
        ]
        verbose_name = "Hạng mục mẫu tóm lược giao ca vận hành"
        verbose_name_plural = "Hạng mục mẫu tóm lược giao ca vận hành"

    def __str__(self):
        return self.ten_hang_muc
