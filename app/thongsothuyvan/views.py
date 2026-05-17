import base64
import io
import json
import os
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import pandas as pd
from .models import (
    MucnuocQuytrinh,
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
    MucnuocQuytrinhSerializer,
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
    "mucnuoc_gioihan_tuan_ho_a",
    "mucnuoc_gioihan_tuan_ho_b",
    "mucnuoc_thuongluu_ho_b",
    "mucnuoc_thuongluu_ho_c",
    "luuluong_ve_ho_b",
    "luuluong_ve_ho_c",
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


def user_can_delete_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_delete_hydrology_data)


def user_can_view_realtime_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_view_realtime_hydrology)


def user_can_update_realtime_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_update_realtime_hydrology)


def user_can_modify_hydrology_object(user, obj):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    created_by_id = getattr(obj, "created_by_id", None)
    return created_by_id is None or created_by_id == user.id


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


MUCNUOC_QUYTRINH_EXPORT_COLUMNS = {
    "ngay_bat_dau": "Ngày bắt đầu",
    "ngay_ket_thuc": "Ngày kết thúc",
    "muc_nuoc_bat_dau": "Mực nước hồ từ",
    "muc_nuoc_ket_thuc": "Mực nước hồ kết thúc",
}

MUCNUOC_QUYTRINH_IMPORT_COLUMNS = {
    "ngay_bat_dau": "ngay_bat_dau",
    "ngày bắt đầu": "ngay_bat_dau",
    "ngay bat dau": "ngay_bat_dau",
    "ngay_ket_thuc": "ngay_ket_thuc",
    "ngày kết thúc": "ngay_ket_thuc",
    "ngay ket thuc": "ngay_ket_thuc",
    "muc_nuoc_bat_dau": "muc_nuoc_bat_dau",
    "mực nước hồ từ": "muc_nuoc_bat_dau",
    "muc nuoc ho tu": "muc_nuoc_bat_dau",
    "muc_nuoc_ket_thuc": "muc_nuoc_ket_thuc",
    "mực nước hồ kết thúc": "muc_nuoc_ket_thuc",
    "muc nuoc ho ket thuc": "muc_nuoc_ket_thuc",
}


def normalize_excel_header(value):
    return str(value or "").strip().lower()


def parse_excel_month_day(value):
    if value in (None, "") or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.strftime("%d/%m")

    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if not pd.isna(parsed):
        return parsed.strftime("%d/%m")

    for date_format in ("%d/%m", "%d-%m", "%d-%b", "%d-%B"):
        try:
            return datetime.strptime(str(value).strip(), date_format).strftime("%d/%m")
        except ValueError:
            continue
    return None


def parse_excel_float(value):
    if value in (None, "") or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(" ", "")
        if value in {"", "-", "--", "nan", "NaN", "None"}:
            return None
        if "," in value and "." in value:
            if value.rfind(",") > value.rfind("."):
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", "")
        elif "," in value:
            value = value.replace(",", ".")
    return float(value)


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

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        obj = self.get_object()
        if not user_can_modify_hydrology_object(self.request.user, obj):
            raise PermissionDenied("Ban chi duoc sua du lieu do chinh ban cap nhat.")
        save_kwargs = {"updated_by": self.request.user}
        if obj.created_by_id is None:
            save_kwargs["created_by"] = self.request.user
        serializer.save(**save_kwargs)

    def perform_destroy(self, instance):
        if not user_can_modify_hydrology_object(self.request.user, instance):
            raise PermissionDenied("Ban chi duoc xoa du lieu do chinh ban cap nhat.")
        instance.delete()


def get_year_offset_date(value, offset):
    if not value:
        return None

    try:
        return value.replace(year=value.year - offset)
    except ValueError:
        return value.replace(year=value.year - offset, day=28)


def get_quarter_bounds(value):
    if not value:
        return None, None

    start_month = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, start_month, 1), value


def add_record(record_map, record):
    if record:
        record_map[record.id] = record


def add_queryset_records(record_map, queryset):
    for record in queryset:
        add_record(record_map, record)


def get_latest_record_before(plant, target_date=None):
    queryset = ThongsoSanxuat.objects.filter(nha_may=plant)
    if target_date:
        queryset = queryset.filter(thoi_gian__date__lte=target_date)
    return queryset.order_by("-thoi_gian").first()


def get_latest_record_in_month(plant, target_date):
    if not target_date:
        return None

    return (
        ThongsoSanxuat.objects.filter(
            nha_may=plant,
            thoi_gian__date__year=target_date.year,
            thoi_gian__date__month=target_date.month,
            thoi_gian__date__lte=target_date,
        )
        .order_by("-thoi_gian")
        .first()
    )


def get_latest_record_in_year(plant, target_date):
    if not target_date:
        return None

    return (
        ThongsoSanxuat.objects.filter(
            nha_may=plant,
            thoi_gian__date__year=target_date.year,
            thoi_gian__date__lte=target_date,
        )
        .order_by("-thoi_gian")
        .first()
    )


def build_dashboard_records_for_plant(plant, target_date=None):
    record_map = {}
    latest_record = get_latest_record_before(plant, target_date)
    latest_date = latest_record.thoi_gian.date() if latest_record else None
    report_date = target_date or latest_date

    add_record(record_map, latest_record)

    comparison_dates = [
        report_date,
        get_year_offset_date(report_date, 1),
        get_year_offset_date(report_date, 2),
    ]

    for comparison_date in comparison_dates:
        if not comparison_date:
            continue

        add_record(
            record_map,
            ThongsoSanxuat.objects.filter(
                nha_may=plant,
                thoi_gian__date=comparison_date,
            )
            .order_by("-thoi_gian")
            .first(),
        )
        add_record(record_map, get_latest_record_in_month(plant, comparison_date))
        add_record(record_map, get_latest_record_in_year(plant, comparison_date))

        quarter_start, quarter_end = get_quarter_bounds(comparison_date)
        if quarter_start and quarter_end:
            add_queryset_records(
                record_map,
                ThongsoSanxuat.objects.filter(
                    nha_may=plant,
                    thoi_gian__date__gte=quarter_start,
                    thoi_gian__date__lte=quarter_end,
                ).order_by("-thoi_gian"),
            )

    return sorted(record_map.values(), key=lambda record: record.thoi_gian, reverse=True)


class DashboardSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        target_date = None

        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        data_by_plant = {}
        for plant in ("songhinh", "vinhson", "thuongkontum"):
            records = build_dashboard_records_for_plant(plant, target_date)
            data_by_plant[plant] = ThongsoSanxuatSerializer(records, many=True).data

        return Response({"data_by_plant": data_by_plant})


class MucnuocQuytrinhViewSet(viewsets.ModelViewSet):
    serializer_class = MucnuocQuytrinhSerializer
    pagination_class = None
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = MucnuocQuytrinh.objects.filter(nha_may="songhinh")
        ngay_bat_dau = self.request.query_params.get("ngay_bat_dau")
        ngay_ket_thuc = self.request.query_params.get("ngay_ket_thuc")
        if ngay_bat_dau:
            queryset = queryset.filter(ngay_ket_thuc__gte=ngay_bat_dau)
        if ngay_ket_thuc:
            queryset = queryset.filter(ngay_bat_dau__lte=ngay_ket_thuc)
        return queryset.order_by("ngay_bat_dau", "ngay_ket_thuc")

    def perform_create(self, serializer):
        serializer.save(
            nha_may="songhinh",
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        obj = self.get_object()
        if not user_can_modify_hydrology_object(self.request.user, obj):
            raise PermissionDenied("Ban chi duoc sua du lieu do chinh ban cap nhat.")
        save_kwargs = {"nha_may": "songhinh", "updated_by": self.request.user}
        if obj.created_by_id is None:
            save_kwargs["created_by"] = self.request.user
        serializer.save(**save_kwargs)

    def perform_destroy(self, instance):
        if not user_can_modify_hydrology_object(self.request.user, instance):
            raise PermissionDenied("Ban chi duoc xoa du lieu do chinh ban cap nhat.")
        instance.delete()

    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        rows = []
        for item in self.get_queryset():
            rows.append(
                {
                    "ngay_bat_dau": item.ngay_bat_dau,
                    "ngay_ket_thuc": item.ngay_ket_thuc,
                    "muc_nuoc_bat_dau": item.muc_nuoc_bat_dau,
                    "muc_nuoc_ket_thuc": item.muc_nuoc_ket_thuc,
                }
            )

        df = pd.DataFrame(rows, columns=MUCNUOC_QUYTRINH_EXPORT_COLUMNS.keys())
        df = df.rename(columns=MUCNUOC_QUYTRINH_EXPORT_COLUMNS)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Muc nuoc quy trinh")

        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            'attachment; filename="mucnuoc_quytrinh_songhinh.xlsx"'
        )
        return response

    @action(detail=False, methods=["post"], url_path="import-excel")
    def import_excel(self, request):
        excel_file = request.FILES.get("file")
        if not excel_file:
            return Response(
                {"error": "Vui long chon file Excel voi field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            df = pd.read_excel(excel_file)
        except Exception as exc:
            return Response(
                {"error": f"Khong doc duoc file Excel: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_columns = {}
        for column in df.columns:
            key = normalize_excel_header(column)
            normalized_columns[column] = MUCNUOC_QUYTRINH_IMPORT_COLUMNS.get(key, key)
        df = df.rename(columns=normalized_columns)

        required_fields = (
            "ngay_bat_dau",
            "ngay_ket_thuc",
            "muc_nuoc_bat_dau",
            "muc_nuoc_ket_thuc",
        )
        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            return Response(
                {"error": "Thieu cot bat buoc: " + ", ".join(missing_fields)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        imported_count = 0
        updated_count = 0
        errors = []

        for index, row in df.iterrows():
            row_number = index + 2
            if all(pd.isna(row.get(field)) for field in required_fields):
                continue

            try:
                ngay_bat_dau = parse_excel_month_day(row.get("ngay_bat_dau"))
                ngay_ket_thuc = parse_excel_month_day(row.get("ngay_ket_thuc"))
                muc_nuoc_bat_dau = parse_excel_float(row.get("muc_nuoc_bat_dau"))
                muc_nuoc_ket_thuc = parse_excel_float(row.get("muc_nuoc_ket_thuc"))

                if not ngay_bat_dau or not ngay_ket_thuc:
                    raise ValueError("Ngay bat dau/ngay ket thuc khong hop le")
                if muc_nuoc_bat_dau is None or muc_nuoc_ket_thuc is None:
                    raise ValueError("Muc nuoc bat dau/ket thuc khong hop le")

                obj, created = MucnuocQuytrinh.objects.get_or_create(
                    nha_may="songhinh",
                    ngay_bat_dau=ngay_bat_dau,
                    ngay_ket_thuc=ngay_ket_thuc,
                    defaults={"created_by": request.user},
                )
                obj.muc_nuoc_bat_dau = muc_nuoc_bat_dau
                obj.muc_nuoc_ket_thuc = muc_nuoc_ket_thuc
                obj.updated_by = request.user
                if obj.created_by_id is None:
                    obj.created_by = request.user
                obj.save()
                if created:
                    imported_count += 1
                else:
                    updated_count += 1
            except Exception as exc:
                errors.append({"row": row_number, "error": str(exc)})

        response_status = (
            status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        )
        return Response(
            {
                "message": "Import Excel muc nuoc quy trinh hoan tat",
                "imported_count": imported_count,
                "updated_count": updated_count,
                "errors": errors,
            },
            status=response_status,
        )


class ThongsoGioPhatViewSet(viewsets.ModelViewSet):
    serializer_class = ThongsoGioPhatSerializer
    pagination_class = None

    def get_queryset(self):
        nhamay = normalize_plant_code(self.request.query_params.get('nhamay', 'songhinh'))
        return ThongsoGioPhat.objects.filter(nha_may=nhamay).order_by('-ngay', 'to_may')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        obj = self.get_object()
        if not user_can_modify_hydrology_object(self.request.user, obj):
            raise PermissionDenied("Ban chi duoc sua du lieu do chinh ban cap nhat.")
        save_kwargs = {"updated_by": self.request.user}
        if obj.created_by_id is None:
            save_kwargs["created_by"] = self.request.user
        serializer.save(**save_kwargs)

    def perform_destroy(self, instance):
        if not user_can_modify_hydrology_object(self.request.user, instance):
            raise PermissionDenied("Ban chi duoc xoa du lieu do chinh ban cap nhat.")
        instance.delete()


class SongHinhRealtimeSnapshotViewSet(viewsets.ModelViewSet):
    serializer_class = SongHinhRealtimeSnapshotSerializer
    pagination_class = None

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


class DeletePlantDataByDateAPIView(APIView):
    def post(self, request):
        if not user_can_delete_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen xoa du lieu thuy van."},
                status=status.HTTP_403_FORBIDDEN,
            )

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
        total_available = sanluong_qs.count() + giophat_qs.count()
        if not request.user.is_superuser:
            sanluong_qs = sanluong_qs.filter(created_by=request.user)
            giophat_qs = giophat_qs.filter(created_by=request.user)

        sanluong_deleted = sanluong_qs.count()
        giophat_deleted = giophat_qs.count()
        total_deleted = sanluong_deleted + giophat_deleted

        if total_available > 0 and total_deleted == 0:
            return Response(
                {
                    "success": False,
                    "error": "Ban chi duoc xoa du lieu do chinh ban cap nhat.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        sanluong_qs.delete()
        giophat_qs.delete()

        return Response(
            {
                "success": True,
                "message": f"Da xoa du lieu ngay {target_date.isoformat()} cho {nhamay}",
                "deleted": {
                    "sanluong": sanluong_deleted,
                    "giophat": giophat_deleted,
                    "total": total_deleted,
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
                if not user_can_modify_hydrology_object(request.user, existing):
                    return Response(
                        {"error": "Ban chi duoc sua du lieu do chinh ban cap nhat."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                for field, value in defaults.items():
                    setattr(existing, field, value)
                update_fields = [*SANLUONG_FIELDS, "updated_by"]
                if existing.created_by_id is None:
                    existing.created_by = request.user
                    update_fields.append("created_by")
                existing.updated_by = request.user
                existing.save(update_fields=update_fields)
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
                    created_by=request.user,
                    updated_by=request.user,
                    **defaults,
                )
                sanluong_created = True

            gio_phat_results = []
            for to_may in (1, 2):
                gio_phat = request.data.get(f"gio_phat_h{to_may}")
                gio_ngung = request.data.get(f"gio_ngung_h{to_may}")

                if gio_phat in (None, "") and gio_ngung in (None, ""):
                    continue

                existing_gio_phat = ThongsoGioPhat.objects.filter(
                    nha_may=nhamay,
                    ngay=target_date,
                    to_may=to_may,
                ).first()
                if existing_gio_phat and not user_can_modify_hydrology_object(
                    request.user,
                    existing_gio_phat,
                ):
                    return Response(
                        {"error": "Ban chi duoc sua du lieu gio phat do chinh ban cap nhat."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                obj, created = ThongsoGioPhat.objects.update_or_create(
                    nha_may=nhamay,
                    ngay=target_date,
                    to_may=to_may,
                    defaults={
                        "gio_phat_dien": parse_float_or_none(gio_phat),
                        "gio_ngung": parse_float_or_none(gio_ngung),
                        "updated_by": request.user,
                        **(
                            {}
                            if existing_gio_phat and existing_gio_phat.created_by_id
                            else {"created_by": request.user}
                        ),
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
