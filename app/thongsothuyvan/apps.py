from django.apps import AppConfig


class ThongsothuyvanConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "thongsothuyvan"
    verbose_name = "Thong so thuy van"

    def ready(self):
        from .realtime_scheduler import start_realtime_scheduler

        start_realtime_scheduler()

        # Connect signals to clear hydrology services caches on setting save or delete
        from django.db.models.signals import post_save, post_delete
        from .models import ThongSoThuyVanCaiDat
        from .hydrology_services import (
            get_all_weekly_settings_cached,
            get_settings_week_number,
            get_setting_value,
        )

        def clear_hydrology_caches(sender, **kwargs):
            get_all_weekly_settings_cached.cache_clear()
            get_settings_week_number.cache_clear()
            get_setting_value.cache_clear()

        post_save.connect(clear_hydrology_caches, sender=ThongSoThuyVanCaiDat)
        post_delete.connect(clear_hydrology_caches, sender=ThongSoThuyVanCaiDat)

