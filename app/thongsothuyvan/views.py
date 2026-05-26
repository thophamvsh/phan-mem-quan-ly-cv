import base64
import io
import json
import os
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from django.conf import settings
from django.db.models import Count, Sum
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
    ThongSoThuyVanCaiDat,
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


def parse_filter_date(date_str):
    if not date_str:
        return None

    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
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


def user_can_view_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(
        profile
        and (
            profile.can_view_hydrology_data
            or profile.can_view_realtime_hydrology
            or profile.can_view_hydrology_settings
            or profile.can_edit_hydrology_settings
            or profile.can_create_hydrology_data
            or profile.can_edit_hydrology_data
        )
    )


def user_can_edit_hydrology_settings(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_edit_hydrology_settings)


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


def get_year_weeks(year):
    current = date(year, 1, 1)
    end_of_year = date(year, 12, 31)
    weeks = []
    week_number = 1

    while current <= end_of_year:
        if week_number == 1:
            week_start = current
        else:
            week_start = current + timedelta(days=(7 - current.weekday()) % 7)
        if week_start > end_of_year:
            break
        week_end = min(week_start + timedelta(days=6), end_of_year)
        weeks.append(
            {
                "week": week_number,
                "start_date": week_start,
                "end_date": week_end,
            }
        )
        current = week_end + timedelta(days=1)
        week_number += 1

    return weeks


def get_setting_record(nhamay, nam, loai, thang=0, tuan=0):
    return ThongSoThuyVanCaiDat.objects.filter(
        nha_may=nhamay,
        nam=nam,
        loai=loai,
        thang=thang,
        tuan=tuan,
    ).first()


def get_setting_field_value(nhamay, nam, loai, field, thang=0, tuan=0):
    record = get_setting_record(nhamay, nam, loai, thang=thang, tuan=tuan)
    return getattr(record, field, None) if record else None


def upsert_hydrology_setting(user, nhamay, nam, loai, values, thang=0, tuan=0):
    numeric_defaults = {
        field: parse_float_or_none(value)
        for field, value in values.items()
        if field not in {"tuan_bat_dau", "tuan_ket_thuc"}
    }
    existing = get_setting_record(nhamay, nam, loai, thang=thang, tuan=tuan)
    if existing is None and not any(value is not None for value in numeric_defaults.values()):
        return None, False

    defaults = {**numeric_defaults}
    defaults["updated_by"] = user
    if "tuan_bat_dau" in values:
        defaults["tuan_bat_dau"] = values["tuan_bat_dau"]
    if "tuan_ket_thuc" in values:
        defaults["tuan_ket_thuc"] = values["tuan_ket_thuc"]

    obj, created = ThongSoThuyVanCaiDat.objects.update_or_create(
        nha_may=nhamay,
        nam=nam,
        loai=loai,
        thang=thang,
        tuan=tuan,
        defaults=defaults,
    )
    if created:
        obj.created_by = user
        obj.save(update_fields=["created_by"])
    return obj, created


def build_hydrology_settings_payload(year, plant_codes):
    annual = {}
    monthly = {}

    for plant_code in plant_codes:
        annual[plant_code] = get_setting_field_value(
            plant_code,
            year,
            ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
            "sanluong_kehoach_nam",
        )
        monthly[plant_code] = {}
        for month in range(1, 13):
            monthly[plant_code][str(month)] = get_setting_field_value(
                plant_code,
                year,
                ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
                "sanluong_kehoach_thang",
                thang=month,
            )

    weekly = []
    for week in get_year_weeks(year):
        row = {
            "week": week["week"],
            "start_date": week["start_date"].isoformat(),
            "end_date": week["end_date"].isoformat(),
        }
        if "songhinh" in plant_codes:
            row["songhinh"] = {
                "mucnuoc_gioihan_tuan": get_setting_field_value(
                    "songhinh",
                    year,
                    ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                    "mucnuoc_gioihan_tuan",
                    tuan=week["week"],
                )
            }
        if "thuongkontum" in plant_codes:
            row["thuongkontum"] = {
                "mucnuoc_gioihan_tuan": get_setting_field_value(
                    "thuongkontum",
                    year,
                    ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                    "mucnuoc_gioihan_tuan",
                    tuan=week["week"],
                )
            }
        if "vinhson" in plant_codes:
            row["vinhson"] = {
                "mucnuoc_gioihan_tuan_ho_a": get_setting_field_value(
                    "vinhson",
                    year,
                    ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                    "mucnuoc_gioihan_tuan_ho_a",
                    tuan=week["week"],
                ),
                "mucnuoc_gioihan_tuan_ho_b": get_setting_field_value(
                    "vinhson",
                    year,
                    ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                    "mucnuoc_gioihan_tuan_ho_b",
                    tuan=week["week"],
                ),
            }
        weekly.append(row)

    return {
        "year": year,
        "annual": annual,
        "monthly": monthly,
        "weekly": weekly,
    }


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
        queryset = ThongsoSanxuat.objects.filter(nha_may=nhamay)

        date_from = parse_filter_date(self.request.query_params.get("date_from"))
        date_to = parse_filter_date(self.request.query_params.get("date_to"))
        if date_from:
            queryset = queryset.filter(thoi_gian__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(thoi_gian__date__lte=date_to)

        queryset = queryset.order_by('-thoi_gian')
        try:
            limit = int(self.request.query_params.get("limit") or 0)
        except (TypeError, ValueError):
            limit = 0

        return queryset[:limit] if limit > 0 else queryset

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

    if not report_date:
        return []

    previous_year_date = get_year_offset_date(report_date, 1)
    if previous_year_date:
        add_record(
            record_map,
            ThongsoSanxuat.objects.filter(
                nha_may=plant,
                thoi_gian__date=previous_year_date,
            )
            .order_by("-thoi_gian")
            .first(),
        )

    quarter_start, quarter_end = get_quarter_bounds(report_date)
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


def build_operation_hours_for_records(plant, records):
    latest_record = records[0] if records else None
    if not latest_record or not latest_record.thoi_gian:
        return {"h1Year": None, "h2Year": None}

    report_date = latest_record.thoi_gian.date()
    year_start = date(report_date.year, 1, 1)
    rows = (
        ThongsoGioPhat.objects.filter(
            nha_may=plant,
            ngay__gte=year_start,
            ngay__lte=report_date,
        )
        .values("to_may")
        .annotate(year=Sum("gio_phat_dien"))
        .order_by()
    )
    totals = {str(row["to_may"]): row["year"] or 0 for row in rows}

    return {
        "h1Year": totals.get("1"),
        "h2Year": totals.get("2"),
    }


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
        operation_hours_by_plant = {}
        for plant in ("songhinh", "vinhson", "thuongkontum"):
            records = build_dashboard_records_for_plant(plant, target_date)
            data_by_plant[plant] = ThongsoSanxuatSerializer(records, many=True).data
            operation_hours_by_plant[plant] = build_operation_hours_for_records(
                plant,
                records,
            )

        report_year = (
            target_date.year
            if target_date
            else timezone.localdate().year
        )
        hydrology_settings = build_hydrology_settings_payload(
            report_year,
            ["songhinh", "vinhson", "thuongkontum"],
        )

        return Response(
            {
                "data_by_plant": data_by_plant,
                "operation_hours_by_plant": operation_hours_by_plant,
                "hydrology_settings": hydrology_settings,
            }
        )


class GioPhatSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        nhamay = normalize_plant_code(request.query_params.get("nhamay", "songhinh"))
        dates_str = request.query_params.get("dates")

        if dates_str:
            dates_list = sorted({d.strip() for d in dates_str.split(",") if d.strip()})
            parsed_dates = []
            for d_str in dates_list:
                try:
                    parsed_dates.append(datetime.strptime(d_str, "%Y-%m-%d").date())
                except ValueError:
                    continue

            if not parsed_dates:
                return Response(
                    {"error": "Khong tim thay ngay hop le trong danh sach dates"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            min_year = min(d.year for d in parsed_dates)
            max_date = max(parsed_dates)

            records = list(
                ThongsoGioPhat.objects.filter(
                    nha_may=nhamay,
                    ngay__gte=date(min_year, 1, 1),
                    ngay__lte=max_date,
                ).order_by("ngay", "to_may")
            )
            machines_set = {str(record.to_may) for record in records}
            running_sums = {}
            results = {}
            record_index = 0

            for d in sorted(parsed_dates):
                day_values = {}
                while record_index < len(records) and records[record_index].ngay <= d:
                    record = records[record_index]
                    machine = str(record.to_may)
                    value = record.gio_phat_dien or 0.0
                    sum_key = (record.ngay.year, machine)
                    running_sums[sum_key] = running_sums.get(sum_key, 0.0) + value
                    if record.ngay == d:
                        day_values[machine] = day_values.get(machine, 0.0) + value
                    record_index += 1

                d_str = d.isoformat()
                results[d_str] = {
                    "nha_may": nhamay,
                    "date": d_str,
                    "year": d.year,
                    "machines": {}
                }
                for m in machines_set:
                    results[d_str]["machines"][m] = {
                        "day": day_values.get(m, 0.0),
                        "year": running_sums.get((d.year, m), 0.0),
                    }

            return Response(results)

        date_str = request.query_params.get("date")
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            target_date = timezone.localdate()

        year_start = date(target_date.year, 1, 1)
        machines = {}

        day_rows = (
            ThongsoGioPhat.objects.filter(nha_may=nhamay, ngay=target_date)
            .values("to_may")
            .annotate(total=Sum("gio_phat_dien"))
            .order_by()
        )
        year_rows = (
            ThongsoGioPhat.objects.filter(
                nha_may=nhamay,
                ngay__gte=year_start,
                ngay__lte=target_date,
            )
            .values("to_may")
            .annotate(total=Sum("gio_phat_dien"))
            .order_by()
        )

        for row in day_rows:
            machine = str(row["to_may"])
            machines.setdefault(machine, {"day": 0, "year": 0})
            machines[machine]["day"] = row["total"] or 0

        for row in year_rows:
            machine = str(row["to_may"])
            machines.setdefault(machine, {"day": 0, "year": 0})
            machines[machine]["year"] = row["total"] or 0

        return Response(
            {
                "nha_may": nhamay,
                "date": target_date.isoformat(),
                "year": target_date.year,
                "machines": machines,
            }
        )


class GioPhatYearSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        nhamay = normalize_plant_code(request.query_params.get("nhamay", "songhinh"))
        date_str = request.query_params.get("date")

        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            target_date = timezone.localdate()

        year_start = date(target_date.year, 1, 1)
        queryset = ThongsoGioPhat.objects.filter(
            nha_may=nhamay,
            ngay__gte=year_start,
            ngay__lte=target_date,
        )

        rows = (
            queryset.values("to_may")
            .annotate(
                year=Sum("gio_phat_dien"),
                row_count=Count("id"),
            )
            .order_by("to_may")
        )

        machines = {
            str(row["to_may"]): {
                "year": row["year"] or 0,
                "row_count": row["row_count"],
            }
            for row in rows
        }

        return Response(
            {
                "nha_may": nhamay,
                "date": target_date.isoformat(),
                "date_from": year_start.isoformat(),
                "date_to": target_date.isoformat(),
                "year": target_date.year,
                "row_count": queryset.count(),
                "machines": machines,
            }
        )


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
        queryset = ThongsoGioPhat.objects.filter(nha_may=nhamay)

        date_from = parse_filter_date(self.request.query_params.get("date_from"))
        date_to = parse_filter_date(self.request.query_params.get("date_to"))
        if date_from:
            queryset = queryset.filter(ngay__gte=date_from)
        if date_to:
            queryset = queryset.filter(ngay__lte=date_to)

        queryset = queryset.order_by('-ngay', 'to_may')
        try:
            limit = int(self.request.query_params.get("limit") or 0)
        except (TypeError, ValueError):
            limit = 0

        return queryset[:limit] if limit > 0 else queryset

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


class HydrologySettingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not user_can_view_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen xem thong so thuy van."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            year = int(request.query_params.get("year") or timezone.localdate().year)
        except (TypeError, ValueError):
            return Response(
                {"error": "Nam khong hop le."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if year < 1900 or year > 2100:
            return Response(
                {"error": "Nam khong hop le."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plants = [
            plant
            for plant in get_hydrology_plants()
            if user_can_access_plant(request.user, plant["code"])
        ]
        plant_codes = [plant["code"] for plant in plants]
        settings_payload = build_hydrology_settings_payload(year, plant_codes)

        return Response(
            {
                "success": True,
                "year": year,
                "plants": plants,
                "annual": settings_payload["annual"],
                "monthly": settings_payload["monthly"],
                "weekly": settings_payload["weekly"],
            }
        )

    def post(self, request):
        if not user_can_edit_hydrology_settings(request.user):
            return Response(
                {"error": "Ban khong co quyen cai dat thong so thuy van."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            year = int(request.data.get("year") or timezone.localdate().year)
        except (TypeError, ValueError):
            return Response(
                {"error": "Nam khong hop le."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if year < 1900 or year > 2100:
            return Response(
                {"error": "Nam khong hop le."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        annual = request.data.get("annual") or {}
        monthly = request.data.get("monthly") or {}
        weekly = request.data.get("weekly") or []
        changed = 0

        try:
            for plant_code, value in annual.items():
                nhamay = normalize_plant_code(plant_code)
                if nhamay not in HYDROLOGY_PLANTS:
                    continue
                if not user_can_access_plant(request.user, nhamay):
                    return Response(
                        {"error": "Ban khong co quyen cai dat nha may nay."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                obj, _created = upsert_hydrology_setting(
                    request.user,
                    nhamay,
                    year,
                    ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
                    {"sanluong_kehoach_nam": value},
                )
                if obj:
                    changed += 1

            for plant_code, month_values in monthly.items():
                nhamay = normalize_plant_code(plant_code)
                if nhamay not in HYDROLOGY_PLANTS:
                    continue
                if not user_can_access_plant(request.user, nhamay):
                    return Response(
                        {"error": "Ban khong co quyen cai dat nha may nay."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                for month_key, value in (month_values or {}).items():
                    month = int(month_key)
                    if month < 1 or month > 12:
                        continue
                    obj, _created = upsert_hydrology_setting(
                        request.user,
                        nhamay,
                        year,
                        ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
                        {"sanluong_kehoach_thang": value},
                        thang=month,
                    )
                    if obj:
                        changed += 1

            for row in weekly:
                try:
                    target_date = datetime.strptime(
                        row.get("start_date"),
                        "%Y-%m-%d",
                    ).date()
                except (TypeError, ValueError):
                    continue
                if target_date.year != year:
                    continue

                weekly_fields = {
                    "songhinh": {
                        "mucnuoc_gioihan_tuan": (row.get("songhinh") or {}).get(
                            "mucnuoc_gioihan_tuan"
                        ),
                    },
                    "thuongkontum": {
                        "mucnuoc_gioihan_tuan": (
                            row.get("thuongkontum") or {}
                        ).get("mucnuoc_gioihan_tuan"),
                    },
                    "vinhson": {
                        "mucnuoc_gioihan_tuan_ho_a": (
                            row.get("vinhson") or {}
                        ).get("mucnuoc_gioihan_tuan_ho_a"),
                        "mucnuoc_gioihan_tuan_ho_b": (
                            row.get("vinhson") or {}
                        ).get("mucnuoc_gioihan_tuan_ho_b"),
                    },
                }
                for nhamay, values in weekly_fields.items():
                    if nhamay not in HYDROLOGY_PLANTS:
                        continue
                    if not user_can_access_plant(request.user, nhamay):
                        continue
                    week_number = row.get("week") or 0
                    obj, _created = upsert_hydrology_setting(
                        request.user,
                        nhamay,
                        year,
                        ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                        {
                            **values,
                            "tuan_bat_dau": target_date,
                            "tuan_ket_thuc": datetime.strptime(
                                row.get("end_date"),
                                "%Y-%m-%d",
                            ).date(),
                        },
                        tuan=int(week_number),
                    )
                    if obj:
                        changed += 1

        except (TypeError, ValueError):
            return Response(
                {"error": "Gia tri so khong hop le."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "year": year,
                "updated": changed,
                "message": "Da luu thong so cai dat thuy van.",
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
