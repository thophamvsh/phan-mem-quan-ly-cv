import requests
from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .vrain_services import (
    VrainConfigError,
    VrainNoDataError,
    get_vrain_realtime_24h,
    sync_vrain_daily_rainfall,
)


def _vrain_error_response(error):
    if isinstance(error, VrainConfigError):
        return Response(
            {"ok": False, "error": str(error)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if isinstance(error, VrainNoDataError):
        return Response(
            {"ok": False, "error": str(error)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    if isinstance(error, requests.HTTPError):
        return Response(
            {"ok": False, "error": str(error)},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    if isinstance(error, requests.RequestException):
        return Response(
            {"ok": False, "error": f"Loi ket noi den VRAIN API: {error}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    if isinstance(error, ValueError):
        return Response(
            {"ok": False, "error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(
        {"ok": False, "error": f"Loi he thong: {error}"},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


class SyncVrainRainfallAPIView(APIView):
    permission_classes = [AllowAny]

    def process_sync(self, request):
        date_param = request.GET.get("date") or request.data.get("date")
        try:
            return Response(sync_vrain_daily_rainfall(date_param))
        except Exception as error:
            return _vrain_error_response(error)

    def get(self, request):
        return self.process_sync(request)

    def post(self, request):
        return self.process_sync(request)


class VrainRealtimeAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cache_key = "vrain_realtime_24h_data"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        try:
            response_data = get_vrain_realtime_24h()
        except Exception as error:
            return _vrain_error_response(error)

        cache.set(cache_key, response_data, 600)
        return Response(response_data)
