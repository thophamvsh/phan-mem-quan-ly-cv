from django.apps import AppConfig


class TochucConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tochuc"
    verbose_name = "Tổ chức"

    def ready(self):
        from auditlog.registry import auditlog

        from .models import BoPhan, DonViToChuc, NhaMay, NhanSu

        for model in (NhaMay, DonViToChuc, BoPhan, NhanSu):
            if not auditlog.contains(model):
                auditlog.register(model)
