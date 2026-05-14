from django.apps import AppConfig


class ThongsothuyvanConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "thongsothuyvan"
    verbose_name = "Thong so thuy van"

    def ready(self):
        from .realtime_scheduler import start_realtime_scheduler

        start_realtime_scheduler()
