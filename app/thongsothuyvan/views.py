import base64
import json
import os
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from django.conf import settings
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import (
    RealtimeUpdateState,
    SongHinhRealtimeSnapshot,
    SonghinhMnh,
    ThuongKonTumMnh,
    VinhSonRealtimeSnapshot,
    Vinhson_HoA,
    Vinhson_HoB,
    Vinhson_Hoc,
    ThongsoGioPhat,
    ThongsoSanxuat,
)
from .serializers import (
    SongHinhRealtimeSnapshotSerializer,
    SonghinhMnhSerializer,
    ThuongKonTumMnhSerializer,
    VinhSonRealtimeSnapshotSerializer,
    Vinhson_HoASerializer,
    Vinhson_HoBSerializer,
    Vinhson_HocSerializer,
    ThongsoSanxuatSerializer,
    ThongsoGioPhatSerializer
)
from .plants import HYDROLOGY_PLANTS, get_hydrology_plants, normalize_plant_code
from .realtime_services import (
    enrich_songhinh_payload,
    enrich_vinhson_payload,
    fetch_realtime_payload as fetch_realtime_payload_data,
    save_all_realtime_snapshots,
    serialize_realtime_state,
)

def get_env_value(name):
    value = os.environ.get(name)
    if value:
        return value

    env_path = os.path.join(settings.BASE_DIR.parent, ".env")
    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, raw_value = line.split("=", 1)
            if key.strip() == name:
                return raw_value.strip().strip('"').strip("'")

    return None


def get_capacity_by_level(model_class, mucnuoc):
    try:
        level = Decimal(str(mucnuoc))
    except (InvalidOperation, TypeError, ValueError):
        return None

    lower = (
        model_class.objects.filter(Mucnuoc__lte=level)
        .order_by("-Mucnuoc")
        .first()
    )
    upper = (
        model_class.objects.filter(Mucnuoc__gte=level)
        .order_by("Mucnuoc")
        .first()
    )

    if not lower and not upper:
        return None
    if lower and not upper:
        return float(lower.dungtich)
    if upper and not lower:
        return float(upper.dungtich)

    lower_level = lower.Mucnuoc
    upper_level = upper.Mucnuoc
    if lower_level == upper_level:
        return float(lower.dungtich)

    ratio = (level - lower_level) / (upper_level - lower_level)
    capacity = lower.dungtich + ratio * (upper.dungtich - lower.dungtich)
    return float(capacity)


def get_songhinh_capacity_by_level(mucnuoc):
    return get_capacity_by_level(SonghinhMnh, mucnuoc)

SANLUONG_FIELDS = [
    "cot_c",
    "cot_d",
    "cot_f",
    "cot_g",
    "cot_h",
    "cot_i",
    "cot_j",
    "cot_k",
    "cot_l",
    "cot_m",
    "cot_n",
    "cot_o",
    "cot_p",
    "cot_q",
    "cot_r",
    "cot_s",
    "cot_t",
    "cot_u",
    "cot_v",
    "cot_w",
    "cot_x",
    "sanluong_kh_thang",
    "mucnuoc_gioihan_tuan",
]

def user_can_write_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(
        profile
        and (
            profile.can_create_hydrology_data
            or profile.can_edit_hydrology_data
        )
    )


def user_can_access_plant(user, nhamay):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False
    if profile.is_all_factories:
        return True

    user_factory = getattr(profile, "nha_may", None)
    user_factory_code = getattr(user_factory, "ma_nha_may", "")
    return normalize_plant_code(user_factory_code) == normalize_plant_code(nhamay)


def parse_float_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("Gia tri so khong hop le")


class SonghinhMnhViewSet(viewsets.ModelViewSet):
    queryset = SonghinhMnh.objects.all()
    serializer_class = SonghinhMnhSerializer


class ThuongKonTumMnhViewSet(viewsets.ModelViewSet):
    queryset = ThuongKonTumMnh.objects.all()
    serializer_class = ThuongKonTumMnhSerializer


class Vinhson_HoAViewSet(viewsets.ModelViewSet):
    queryset = Vinhson_HoA.objects.all()
    serializer_class = Vinhson_HoASerializer


class Vinhson_HoBViewSet(viewsets.ModelViewSet):
    queryset = Vinhson_HoB.objects.all()
    serializer_class = Vinhson_HoBSerializer


class Vinhson_HocViewSet(viewsets.ModelViewSet):
    queryset = Vinhson_Hoc.objects.all()
    serializer_class = Vinhson_HocSerializer

class ThongsoSanxuatViewSet(viewsets.ModelViewSet):
    serializer_class = ThongsoSanxuatSerializer
    pagination_class = None

    def get_queryset(self):
        nhamay = normalize_plant_code(self.request.query_params.get('nhamay', 'songhinh'))
        return ThongsoSanxuat.objects.filter(nha_may=nhamay).order_by('-thoi_gian')

class ThongsoGioPhatViewSet(viewsets.ModelViewSet):
    serializer_class = ThongsoGioPhatSerializer
    pagination_class = None

    def get_queryset(self):
        nhamay = normalize_plant_code(self.request.query_params.get('nhamay', 'songhinh'))
        return ThongsoGioPhat.objects.filter(nha_may=nhamay).order_by('-ngay', 'to_may')


class SongHinhRealtimeSnapshotViewSet(viewsets.ModelViewSet):
    serializer_class = SongHinhRealtimeSnapshotSerializer

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

    def get_queryset(self):
        queryset = VinhSonRealtimeSnapshot.objects.all().order_by("-time_stamp")
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            queryset = queryset.filter(time_stamp__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(time_stamp__date__lte=date_to)
        return queryset


class HydrologyPlantsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plants = [
            plant
            for plant in get_hydrology_plants()
            if user_can_access_plant(request.user, plant["code"])
        ]
        return Response(
            {
                "success": True,
                "data": plants,
                "submenu": [
                    {
                        "label": plant["name"],
                        "code": plant["code"],
                        "dashboard_slug": plant["dashboard_slug"],
                        "api_params": {"nhamay": plant["code"]},
                    }
                    for plant in plants
                ],
            }
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
        return Response(serialize_realtime_state())

    def patch(self, request):
        state = RealtimeUpdateState.get_solo()
        state.auto_update_enabled = bool(request.data.get("auto_update_enabled"))
        state.save(update_fields=["auto_update_enabled", "updated_at"])
        state_data = serialize_realtime_state(state)
        return Response(state_data)


class RealtimeManualSaveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        state, results = save_all_realtime_snapshots(is_manual=True)
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


class DeletePlantDataByDateAPIView(APIView):
    def post(self, request):
        nhamay = normalize_plant_code(
            request.data.get("nhamay") or request.query_params.get("nhamay", "songhinh")
        )
        date_str = request.data.get("date") or request.query_params.get("date")

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return Response(
                {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sanluong_qs = ThongsoSanxuat.objects.filter(
            nha_may=nhamay,
            thoi_gian__date=target_date,
        )
        giophat_qs = ThongsoGioPhat.objects.filter(
            nha_may=nhamay,
            ngay=target_date,
        )

        sanluong_deleted = sanluong_qs.count()
        giophat_deleted = giophat_qs.count()

        sanluong_qs.delete()
        giophat_qs.delete()

        return Response(
            {
                "success": True,
                "message": f"Da xoa du lieu ngay {target_date.isoformat()} cho {nhamay}",
                "deleted": {
                    "sanluong": sanluong_deleted,
                    "giophat": giophat_deleted,
                    "total": sanluong_deleted + giophat_deleted,
                },
            }
        )


class ManualHydrologyDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_can_write_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen nhap du lieu thuy van."},
                status=status.HTTP_403_FORBIDDEN,
            )

        nhamay = normalize_plant_code(request.data.get("nhamay") or "songhinh")
        if nhamay not in HYDROLOGY_PLANTS:
            return Response(
                {"error": "Nha may khong hop le."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Ban khong co quyen nhap du lieu cho nha may nay."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_str = request.data.get("date")
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return Response(
                {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            defaults = {}
            for field in SANLUONG_FIELDS:
                if field == "cot_c":
                    defaults[field] = request.data.get(field) or None
                else:
                    defaults[field] = parse_float_or_none(request.data.get(field))

            existing = (
                ThongsoSanxuat.objects.filter(
                    nha_may=nhamay,
                    thoi_gian__date=target_date,
                )
                .order_by("-thoi_gian")
                .first()
            )

            if existing:
                for field, value in defaults.items():
                    setattr(existing, field, value)
                existing.save(update_fields=SANLUONG_FIELDS)
                sanluong_created = False
                sanluong_obj = existing
            else:
                thoi_gian = timezone.make_aware(
                    datetime.combine(target_date, time.min),
                    timezone.get_current_timezone(),
                )
                sanluong_obj = ThongsoSanxuat.objects.create(
                    nha_may=nhamay,
                    thoi_gian=thoi_gian,
                    **defaults,
                )
                sanluong_created = True

            gio_phat_results = []
            for to_may in (1, 2):
                gio_phat = request.data.get(f"gio_phat_h{to_may}")
                gio_ngung = request.data.get(f"gio_ngung_h{to_may}")

                if gio_phat in (None, "") and gio_ngung in (None, ""):
                    continue

                obj, created = ThongsoGioPhat.objects.update_or_create(
                    nha_may=nhamay,
                    ngay=target_date,
                    to_may=to_may,
                    defaults={
                        "gio_phat_dien": parse_float_or_none(gio_phat),
                        "gio_ngung": parse_float_or_none(gio_ngung),
                    },
                )
                gio_phat_results.append(
                    {
                        "to_may": obj.to_may,
                        "created": created,
                    }
                )
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "message": f"Da luu du lieu nhap tay ngay {target_date.isoformat()} cho {nhamay}",
                "sanluong": {
                    "id": sanluong_obj.id,
                    "created": sanluong_created,
                },
                "giophat": gio_phat_results,
            }
        )
