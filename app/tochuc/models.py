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
