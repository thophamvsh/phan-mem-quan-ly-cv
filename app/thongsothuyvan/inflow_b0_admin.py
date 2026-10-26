from django.contrib import admin
from .inflow_b0_models import InflowB0Forecast,InflowB0Run,InflowB0Evaluation


class B0ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False


@admin.register(InflowB0Forecast)
class ForecastAdmin(B0ReadOnlyAdmin):
    list_display=("id","issued_at","target_day","predicted_qve","source_day","last_checked_at")
    list_filter=("model_version","target_day")
    date_hierarchy="issued_at"


@admin.register(InflowB0Run)
class RunAdmin(B0ReadOnlyAdmin):
    list_display=("id","action","trigger","started_at","status","error_code","forecast_id")
    list_filter=("action","status","trigger")


@admin.register(InflowB0Evaluation)
class EvaluationAdmin(B0ReadOnlyAdmin):
    list_display=("forecast_id","revision","checked_at","status","actual_qve","signed_error","absolute_error")
    list_filter=("status",)
