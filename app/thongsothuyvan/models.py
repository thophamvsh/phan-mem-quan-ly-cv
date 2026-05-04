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