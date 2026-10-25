from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .rain_forecast_models import RainForecastLocation
from .rain_forecast_services import location_forecast
from .views.views_sanxuat import user_can_access_plant, user_can_view_realtime_hydrology


class RainForecastAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plant = request.query_params.get("plant")
        if plant not in {"songhinh", "vinhson"}:
            return Response({"detail": "Nhà máy không hợp lệ."}, status=400)
        if not user_can_view_realtime_hydrology(request.user) or not user_can_access_plant(request.user, plant):
            return Response({"detail": "Không có quyền xem nhà máy này."}, status=403)
        enabled = getattr(settings, "RAIN_FORECAST_ENABLED", False)
        response = Response({"enabled": enabled, "plant": plant, "timezone": "Asia/Ho_Chi_Minh",
                             "provider": "Open-Meteo", "attribution_url": "https://open-meteo.com/",
                             "locations": [location_forecast(loc) for loc in RainForecastLocation.objects.filter(plant=plant, enabled=True).order_by("code")] if enabled else []})
        response["Cache-Control"] = "private, no-store"
        return response
