from django.contrib import admin
from .rain_forecast_models import RainForecastFetch, RainForecastLocation, RainForecastRevision


@admin.register(RainForecastLocation)
class RainForecastLocationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "plant", "station_code", "latitude", "longitude", "enabled")
    list_filter = ("plant", "enabled")
    readonly_fields = ("code", "plant", "station_code")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyForecastAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RainForecastFetch)
class RainForecastFetchAdmin(ReadOnlyForecastAdmin):
    list_display = ("location", "started_at", "finished_at", "status", "error_code", "revision_id")
    list_filter = ("status", "location")
    list_select_related = ("location",)


@admin.register(RainForecastRevision)
class RainForecastRevisionAdmin(ReadOnlyForecastAdmin):
    list_display = ("location", "received_at", "provider", "source_issued_at")
    list_filter = ("location",)
    list_select_related = ("location",)
