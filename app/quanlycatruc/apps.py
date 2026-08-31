from django.apps import AppConfig


class QuanLyCaTrucConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "quanlycatruc"
    verbose_name = "Quản lý lịch trực ca"

    def ready(self):
        from auditlog.registry import auditlog
        from .models import KipTruc, LichTrucCa, MauChuKyCaTruc, NgayTrucCa, NhanSu, ThanhVienKipTruc

        for model in (NhanSu, KipTruc, ThanhVienKipTruc, MauChuKyCaTruc, LichTrucCa, NgayTrucCa):
            if not auditlog.contains(model):
                auditlog.register(model)
