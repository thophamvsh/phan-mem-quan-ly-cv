from django.db import models


class BaseThuyVan(models.Model):
    Mucnuoc = models.DecimalField(max_digits=10, decimal_places=2)
    dungtich = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class SonghinhMnh(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Sông Hinh Mnh"
        verbose_name_plural = "Sông Hinh Mnh"


class ThuongKonTumMnh(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Thượng Kon Tum Mnh"
        verbose_name_plural = "Thượng Kon Tum Mnh"


class Vinhson_HoA(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Vĩnh Sơn - Hồ A"
        verbose_name_plural = "Vĩnh Sơn - Hồ A"


class Vinhson_HoB(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Vĩnh Sơn - Hồ B"
        verbose_name_plural = "Vĩnh Sơn - Hồ B"


class Vinhson_Hoc(BaseThuyVan):
    class Meta(BaseThuyVan.Meta):
        verbose_name = "Vĩnh Sơn - Hồ C"
        verbose_name_plural = "Vĩnh Sơn - Hồ C"

class ThongsoSanxuat(models.Model):
    nha_may = models.CharField(max_length=50, default='songhinh')
    thoi_gian = models.DateTimeField()
    
    # Các cột từ C đến X (trừ E)
    cot_c = models.CharField(verbose_name="Hồ chứa", max_length=100, null=True, blank=True)
    cot_d = models.FloatField(verbose_name="Mực nước kế hoạch", null=True, blank=True)
    # Bỏ qua cột E theo yêu cầu
    cot_f = models.FloatField(verbose_name="Mực nước chết (m)", null=True, blank=True)
    cot_g = models.FloatField(verbose_name="Mực nước thượng lưu (m)", null=True, blank=True)
    cot_h = models.FloatField(verbose_name="Dung tích hữu ích (tr.m3)", null=True, blank=True)
    cot_i = models.FloatField(verbose_name="Lưu lượng nước về Qv (m3/s)", null=True, blank=True)
    cot_j = models.FloatField(verbose_name="Lưu lượng qua máy Qcm (m3/s)", null=True, blank=True)
    cot_k = models.FloatField(verbose_name="Lưu lượng xả lũ Qxl (m3/s)", null=True, blank=True)
    cot_l = models.FloatField(verbose_name="Sản lượng Qc ngày", null=True, blank=True)
    cot_m = models.FloatField(verbose_name="Đầu cực ngày", null=True, blank=True)
    cot_n = models.FloatField(verbose_name="Thương phẩm ngày", null=True, blank=True)
    cot_o = models.FloatField(verbose_name="Sản lượng Qc Ao giao tháng", null=True, blank=True)
    cot_p = models.FloatField(verbose_name="Sản lượng Qc lũy kế tháng", null=True, blank=True)
    cot_q = models.FloatField(verbose_name="Đầu cực tháng", null=True, blank=True)
    cot_r = models.FloatField(verbose_name="Thương phẩm tháng", null=True, blank=True)
    cot_s = models.FloatField(verbose_name="Sản lượng Qc năm Ao giao", null=True, blank=True)
    cot_t = models.FloatField(verbose_name="Sản lượng Qc lũy kế năm", null=True, blank=True)
    cot_u = models.FloatField(verbose_name="Đầu cực năm", null=True, blank=True)
    cot_v = models.FloatField(verbose_name="Thương phẩm năm", null=True, blank=True)
    cot_w = models.FloatField(verbose_name="Sản lượng kế hoạch năm", null=True, blank=True)
    cot_x = models.FloatField(verbose_name="Sản lượng tự dùng ngày", null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-thoi_gian"]
        unique_together = ('thoi_gian', 'nha_may')
        verbose_name = "Thông số sản xuất"
        verbose_name_plural = "Thông số sản xuất"

class ThongsoGioPhat(models.Model):
    nha_may = models.CharField(max_length=50, default='songhinh')
    ngay = models.DateField()
    to_may = models.IntegerField()
    gio_phat_dien = models.FloatField(null=True, blank=True)
    gio_ngung = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-ngay", "to_may"]
        unique_together = ('ngay', 'to_may', 'nha_may')
        verbose_name = "Thông số giờ phát"
        verbose_name_plural = "Thông số giờ phát"
