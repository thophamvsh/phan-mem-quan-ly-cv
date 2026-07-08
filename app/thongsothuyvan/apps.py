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
        from .models import (
            SonghinhMnh,
            ThuongKonTumMnh,
            ThongSoThuyVanCaiDat,
            Vinhson_HoA,
            Vinhson_HoB,
            Vinhson_Hoc,
        )
        from .hydrology_services import (
            get_all_weekly_settings_cached,
            get_capacity_bounds_for_reservoir,
            get_capacity_levels_for_reservoir,
            get_capacity_points_for_reservoir,
            get_operating_capacity_range_for_reservoir,
            get_settings_week_number,
            get_setting_value,
        )

        def clear_hydrology_caches(sender, **kwargs):
            get_all_weekly_settings_cached.cache_clear()
            get_settings_week_number.cache_clear()
            get_setting_value.cache_clear()

        def clear_capacity_caches(sender, **kwargs):
            get_capacity_points_for_reservoir.cache_clear()
            get_capacity_levels_for_reservoir.cache_clear()
            get_capacity_bounds_for_reservoir.cache_clear()
            get_operating_capacity_range_for_reservoir.cache_clear()

        post_save.connect(
            clear_hydrology_caches,
            sender=ThongSoThuyVanCaiDat,
            dispatch_uid="thongsothuyvan.clear_hydrology_caches.save",
        )
        post_delete.connect(
            clear_hydrology_caches,
            sender=ThongSoThuyVanCaiDat,
            dispatch_uid="thongsothuyvan.clear_hydrology_caches.delete",
        )

        for model in (SonghinhMnh, ThuongKonTumMnh, Vinhson_HoA, Vinhson_HoB, Vinhson_Hoc):
            post_save.connect(
                clear_capacity_caches,
                sender=model,
                dispatch_uid=f"thongsothuyvan.clear_capacity_caches.{model.__name__}.save",
            )
            post_delete.connect(
                clear_capacity_caches,
                sender=model,
                dispatch_uid=f"thongsothuyvan.clear_capacity_caches.{model.__name__}.delete",
            )
