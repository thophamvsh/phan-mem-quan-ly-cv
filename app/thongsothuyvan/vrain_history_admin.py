from django.contrib import admin
from .vrain_history_models import VrainStation, VrainSyncRun, VrainSourceSample, VrainRainfallRevision, VrainRainfallInterval, VrainBackfillJob


@admin.register(VrainStation)
class VrainStationAdmin(admin.ModelAdmin):
    list_display = ("source_station_code", "name", "plant", "enabled")
    list_filter = ("plant", "enabled")
    readonly_fields = ("provider", "source_station_code", "plant", "metadata")
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


class HistoryReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VrainSyncRun)
class VrainSyncRunAdmin(HistoryReadOnlyAdmin):
    list_display = ("id", "window_start", "window_end", "status", "error_code", "contract_verified")
    list_filter = ("status", "contract_verified")


for model in (VrainSourceSample, VrainRainfallRevision, VrainRainfallInterval, VrainBackfillJob):
    admin.site.register(model, HistoryReadOnlyAdmin)
