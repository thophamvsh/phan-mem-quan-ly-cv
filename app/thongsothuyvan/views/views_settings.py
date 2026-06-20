from datetime import date, datetime, timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from ..models import ThongSoThuyVanCaiDat
from ..plants import HYDROLOGY_PLANTS, get_hydrology_plants, normalize_plant_code


def get_year_weeks(year):
    last_iso_week = date(year, 12, 28).isocalendar().week
    weeks = []

    for week_number in range(1, last_iso_week + 1):
        week_start = date.fromisocalendar(year, week_number, 1)
        week_end = week_start + timedelta(days=6)
        weeks.append(
            {
                "week": week_number,
                "start_date": week_start,
                "end_date": week_end,
            }
        )
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
    from .views_sanxuat import parse_float_or_none, user_can_edit_hydrology_settings

    numeric_defaults = {
        field: parse_float_or_none(value)
        for field, value in values.items()
        if field not in {"tuan_bat_dau", "tuan_ket_thuc"}
    }
    existing = get_setting_record(nhamay, nam, loai, thang=thang, tuan=tuan)
    if existing is None and not any(value is not None for value in numeric_defaults.values()):
        return None, False
    if existing is not None and not user_can_edit_hydrology_settings(user):
        raise PermissionDenied("Bạn không có quyền sửa thông số cài đặt thủy văn.")

    defaults = {**numeric_defaults}
    defaults["updated_by"] = user
    if "tuan_bat_dau" in values:
        defaults["tuan_bat_dau"] = values["tuan_bat_dau"]
    if "tuan_ket_thuc" in values:
        defaults["tuan_ket_thuc"] = values["tuan_ket_thuc"]

    if existing is not None:
        for field, value in defaults.items():
            setattr(existing, field, value)

        update_fields = [*defaults.keys(), "updated_at"]
        if existing.created_by_id is None:
            existing.created_by = user
            update_fields.append("created_by")
        existing.save(update_fields=update_fields)
        return existing, False

    obj = ThongSoThuyVanCaiDat.objects.create(
        nha_may=nhamay,
        nam=nam,
        loai=loai,
        thang=thang,
        tuan=tuan,
        created_by=user,
        **defaults,
    )
    return obj, True


def build_hydrology_settings_payload(year, plant_codes):
    settings_lookup = {
        (record.nha_may, record.loai, record.thang, record.tuan): record
        for record in ThongSoThuyVanCaiDat.objects.filter(
            nha_may__in=plant_codes,
            nam=year,
        )
    }

    def get_prefetched_value(nhamay, loai, field, thang=0, tuan=0):
        record = settings_lookup.get((nhamay, loai, thang, tuan))
        return getattr(record, field, None) if record else None

    annual = {}
    monthly = {}

    for plant_code in plant_codes:
        annual[plant_code] = get_prefetched_value(
            plant_code,
            ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
            "sanluong_kehoach_nam",
        )
        monthly[plant_code] = {}
        for month in range(1, 13):
            monthly[plant_code][str(month)] = get_prefetched_value(
                plant_code,
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
                "mucnuoc_gioihan_tuan": get_prefetched_value(
                    "songhinh",
                    ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                    "mucnuoc_gioihan_tuan",
                    tuan=week["week"],
                )
            }
        if "thuongkontum" in plant_codes:
            row["thuongkontum"] = {
                "mucnuoc_gioihan_tuan": get_prefetched_value(
                    "thuongkontum",
                    ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                    "mucnuoc_gioihan_tuan",
                    tuan=week["week"],
                )
            }
        if "vinhson" in plant_codes:
            row["vinhson"] = {
                "mucnuoc_gioihan_tuan_ho_a": get_prefetched_value(
                    "vinhson",
                    ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                    "mucnuoc_gioihan_tuan_ho_a",
                    tuan=week["week"],
                ),
                "mucnuoc_gioihan_tuan_ho_b": get_prefetched_value(
                    "vinhson",
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


# --- API Views ---

class HydrologyPlantsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .views_sanxuat import user_can_access_plant
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
        from .views_sanxuat import (
            user_can_view_hydrology_settings,
            user_can_access_plant,
        )
        if not user_can_view_hydrology_settings(request.user):
            return Response(
                {"error": "Bạn không có quyền xem thông số thủy văn cài đặt."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            year = int(request.query_params.get("year") or timezone.localdate().year)
        except (TypeError, ValueError):
            return Response(
                {"error": "Năm không hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if year < 1900 or year > 2100:
            return Response(
                {"error": "Năm không hợp lệ."},
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
        from .views_sanxuat import (
            user_can_edit_hydrology_settings,
            user_can_access_plant,
        )
        if not user_can_edit_hydrology_settings(request.user):
            return Response(
                {"error": "Bạn không có quyền cài đặt thông số thủy văn."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            year = int(request.data.get("year") or timezone.localdate().year)
        except (TypeError, ValueError):
            return Response(
                {"error": "Năm không hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if year < 1900 or year > 2100:
            return Response(
                {"error": "Năm không hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        annual = request.data.get("annual") or {}
        monthly = request.data.get("monthly") or {}
        weekly = request.data.get("weekly") or []
        valid_week_numbers = {week["week"] for week in get_year_weeks(year)}
        changed = 0

        try:
            for plant_code, value in annual.items():
                nhamay = normalize_plant_code(plant_code)
                if nhamay not in HYDROLOGY_PLANTS:
                    continue
                if not user_can_access_plant(request.user, nhamay):
                    return Response(
                        {"error": "Bạn không có quyền cài đặt nhà máy này."},
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
                        {"error": "Bạn không có quyền cài đặt nhà máy này."},
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
                    week_number = int(row.get("week") or 0)
                    target_date = datetime.strptime(
                        row.get("start_date"),
                        "%Y-%m-%d",
                    ).date()
                    end_date = datetime.strptime(
                        row.get("end_date"),
                        "%Y-%m-%d",
                    ).date()
                except (TypeError, ValueError):
                    continue
                if week_number not in valid_week_numbers:
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
                    obj, _created = upsert_hydrology_setting(
                        request.user,
                        nhamay,
                        year,
                        ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                        {
                            **values,
                            "tuan_bat_dau": target_date,
                            "tuan_ket_thuc": end_date,
                        },
                        tuan=week_number,
                    )
                    if obj:
                        changed += 1

        except (TypeError, ValueError):
            return Response(
                {"error": "Giá trị số không hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "year": year,
                "updated": changed,
                "message": "Đã lưu thông số cài đặt thủy văn.",
            }
        )
