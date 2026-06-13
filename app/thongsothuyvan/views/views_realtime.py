import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import (
    SongHinhRealtimeSnapshot,
    VinhSonRealtimeSnapshot,
    RealtimeUpdateState,
)
from ..serializers import (
    SongHinhRealtimeSnapshotSerializer,
    VinhSonRealtimeSnapshotSerializer,
)
from ..plants import normalize_plant_code
from ..realtime_services import (
    enrich_songhinh_payload,
    enrich_vinhson_payload,
    fetch_realtime_payload as fetch_realtime_payload_data,
    save_all_realtime_snapshots,
    serialize_realtime_state,
)
from .views_sanxuat import (
    user_can_view_realtime_hydrology,
    user_can_update_realtime_hydrology,
    get_env_value,
)


def fetch_realtime_payload(prefix):
    realtime_url = get_env_value(f"{prefix}_URL")
    realtime_user = get_env_value(f"{prefix}_USER") or ""
    realtime_pass = get_env_value(f"{prefix}_PASS") or ""

    if not realtime_url:
        return None, Response(
            {"error": f"Chua cau hinh {prefix}_URL trong .env backend."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    headers = {"Accept": "application/json"}
    if realtime_user or realtime_pass:
        token = base64.b64encode(
            f"{realtime_user}:{realtime_pass}".encode("ascii")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {token}"

    try:
        upstream_request = Request(realtime_url, headers=headers, method="GET")
        with urlopen(upstream_request, timeout=15) as upstream_response:
            charset = upstream_response.headers.get_content_charset() or "utf-8"
            payload = upstream_response.read().decode(charset)
            return json.loads(payload), None
    except HTTPError as exc:
        return None, Response(
            {"error": f"Realtime API tra ve loi {exc.code}."},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except (URLError, TimeoutError) as exc:
        return None, Response(
            {"error": f"Khong ket noi duoc realtime API: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except (ValueError, json.JSONDecodeError):
        return None, Response(
            {"error": "Realtime API khong tra ve JSON hop le."},
            status=status.HTTP_502_BAD_GATEWAY,
        )


class SongHinhRealtimeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_can_view_realtime_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen xem du lieu realtime."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            return Response(enrich_songhinh_payload(fetch_realtime_payload_data("SONGHINH")))
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class VinhSonRealtimeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_can_view_realtime_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen xem du lieu realtime."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            return Response(enrich_vinhson_payload(fetch_realtime_payload_data("VINHSON")))
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class RealtimeUpdateStateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_can_view_realtime_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen xem trang realtime."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(serialize_realtime_state())

    def patch(self, request):
        if not user_can_update_realtime_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen cap nhat realtime."},
                status=status.HTTP_403_FORBIDDEN,
            )
        state = RealtimeUpdateState.get_solo()
        state.auto_update_enabled = bool(request.data.get("auto_update_enabled"))
        state.save(update_fields=["auto_update_enabled", "updated_at"])
        state_data = serialize_realtime_state(state)
        return Response(state_data)


class RealtimeManualSaveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_can_update_realtime_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen cap nhat realtime."},
                status=status.HTTP_403_FORBIDDEN,
            )
        plant = normalize_plant_code(request.data.get("plant") or "")
        plants = [plant] if plant else None
        state, results = save_all_realtime_snapshots(is_manual=True, plants=plants)
        return Response(
            {
                "state": serialize_realtime_state(state),
                "results": [
                    {
                        "plant": result.plant,
                        "saved": result.saved,
                        "snapshot_id": result.snapshot_id,
                        "error": result.error,
                    }
                    for result in results
                ],
            },
            status=(
                status.HTTP_207_MULTI_STATUS
                if any(not result.saved for result in results)
                else status.HTTP_201_CREATED
            ),
        )


class SongHinhRealtimeSnapshotViewSet(viewsets.ModelViewSet):
    serializer_class = SongHinhRealtimeSnapshotSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = SongHinhRealtimeSnapshot.objects.all().order_by("-time_stamp")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(time_stamp__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(time_stamp__date__lte=date_to)
        return queryset


class VinhSonRealtimeSnapshotViewSet(viewsets.ModelViewSet):
    serializer_class = VinhSonRealtimeSnapshotSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = VinhSonRealtimeSnapshot.objects.all().order_by("-time_stamp")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        limit = self.request.query_params.get("limit")
        if date_from:
            queryset = queryset.filter(time_stamp__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(time_stamp__date__lte=date_to)
        if limit:
            try:
                limit_value = max(1, min(int(limit), 500))
                queryset = queryset[:limit_value]
            except (TypeError, ValueError):
                pass
        return queryset
