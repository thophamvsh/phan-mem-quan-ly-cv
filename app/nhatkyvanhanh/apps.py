from django.apps import AppConfig


class NhatkyvanhanhConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "nhatkyvanhanh"
    verbose_name = "Nhật ký vận hành"

    def ready(self):
        import nhatkyvanhanh.signals

