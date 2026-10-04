import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Q

from ..models import (
    SongHinhRealtimeSnapshot,
    VinhSonRealtimeSnapshot,
    RealtimeUpdateState,
    ThongsoSanxuat,
)
from ..serializers import (
    SongHinhRealtimeSnapshotSerializer,
    VinhSonRealtimeSnapshotSerializer,
)
from ..plants import normalize_plant_code
from ..hydrology_services import get_operating_capacity_by_level
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
    user_can_access_plant,
    get_env_value,
)


def fetch_realtime_payload(prefix):
    realtime_url = get_env_value(f"{prefix}_URL")
    realtime_user = get_env_value(f"{prefix}_USER") or ""
    realtime_pass = get_env_value(f"{prefix}_PASS") or ""

    if not realtime_url:
        return None, Response(
            {"error": f"Chưa cấu hình {prefix}_URL trong .env backend."},
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
            {"error": f"Realtime API trả về lỗi {exc.code}."},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except (URLError, TimeoutError) as exc:
        return None, Response(
            {"error": f"Không kết nối được realtime API: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except (ValueError, json.JSONDecodeError):
        return None, Response(
            {"error": "Realtime API không trả về JSON hợp lệ."},
            status=status.HTTP_502_BAD_GATEWAY,
        )


class SongHinhRealtimeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_can_view_realtime_hydrology(request.user) or not user_can_access_plant(request.user, "songhinh"):
            return Response(
                {"error": "Bạn không có quyền xem dữ liệu realtime."},
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
        if not user_can_view_realtime_hydrology(request.user) or not user_can_access_plant(request.user, "vinhson"):
            return Response(
                {"error": "Bạn không có quyền xem dữ liệu realtime."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            return Response(enrich_vinhson_payload(fetch_realtime_payload_data("VINHSON")))
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )


class ThuongKonTumLatestDailyHydrologyAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_can_view_realtime_hydrology(request.user) or not user_can_access_plant(request.user, "thuongkontum"):
            raise PermissionDenied("Bạn không có quyền xem dữ liệu Thượng Kon Tum.")

        record = (
            ThongsoSanxuat.objects.filter(
                thoi_gian__date__lte=timezone.localdate(),
            )
            .filter(Q(nha_may__iexact="thuongkontum") | Q(nha_may__iexact="TKT"))
            .order_by("-thoi_gian", "-pk")
            .first()
        )
        if not record:
            return Response({"recordDate": None, "waterLevelM": None, "capacityMcm": None})
        return Response({
            "recordDate": timezone.localtime(record.thoi_gian).date().isoformat(),
            "waterLevelM": record.cot_g,
            "capacityMcm": get_operating_capacity_by_level("thuongkontum", record.cot_g) if record.cot_g is not None else None,
        })


class RealtimeUpdateStateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_can_view_realtime_hydrology(request.user):
            return Response(
                {"error": "Bạn không có quyền xem trang realtime."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(serialize_realtime_state())

    def patch(self, request):
        if not user_can_update_realtime_hydrology(request.user) or not all(
            user_can_access_plant(request.user, plant) for plant in ("songhinh", "vinhson")
        ):
            return Response(
                {"error": "Bạn không có quyền cập nhật realtime."},
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
                {"error": "Bạn không có quyền cập nhật realtime."},
                status=status.HTTP_403_FORBIDDEN,
            )
        plant = normalize_plant_code(request.data.get("plant") or "")
        allowed_plants = [
            code for code in ("songhinh", "vinhson")
            if user_can_access_plant(request.user, code)
        ]
        if plant and plant not in allowed_plants:
            raise PermissionDenied("Bạn không có quyền cập nhật realtime nhà máy này.")
        if not allowed_plants:
            raise PermissionDenied("Bạn không có quyền cập nhật realtime nhà máy.")
        plants = [plant] if plant else allowed_plants
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

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        can_access = (
            user_can_view_realtime_hydrology(request.user)
            if request.method in ("GET", "HEAD", "OPTIONS")
            else user_can_update_realtime_hydrology(request.user)
        )
        if not can_access or not user_can_access_plant(request.user, "songhinh"):
            raise PermissionDenied("Bạn không có quyền truy cập snapshot Sông Hinh.")

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

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        can_access = (
            user_can_view_realtime_hydrology(request.user)
            if request.method in ("GET", "HEAD", "OPTIONS")
            else user_can_update_realtime_hydrology(request.user)
        )
        if not can_access or not user_can_access_plant(request.user, "vinhson"):
            raise PermissionDenied("Bạn không có quyền truy cập snapshot Vĩnh Sơn.")

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
