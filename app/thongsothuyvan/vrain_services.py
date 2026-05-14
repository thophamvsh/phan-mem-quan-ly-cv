import os
from datetime import datetime, timedelta

import pytz
import requests
from django.conf import settings

from .models import TramDoMuaVrain


STATIONS_MAPPING = {
    "957833": "Xa_Ea_M_doan",
    "036606": "Xa_Ea_M_doan",
    "036605": "Thon_10_Xa_Ea_M_Doal",
    "036620": "UBND_xa_Song_Hinh",
    "036608": "Cu_Kroa",
    "036607": "Xa_Ea_Trang",
    "036604": "Dap_Tran",
    "036616": "Ho_A_TD_Vinh_Son",
    "036617": "Ho_B_TD_Vinh_Son",
    "036618": "Ho_C_TD_Vinh_Son",
}

VRAIN_STATS_URL = "https://kttv-open.vrain.vn/v1/stations/stats"


class VrainNoDataError(ValueError):
    pass


class VrainConfigError(RuntimeError):
    pass


def _get_api_key():
    api_key = getattr(settings, "VRAIN_API_KEY", os.environ.get("VRAIN_API_KEY"))
    if not api_key:
        raise VrainConfigError("VRAIN_API_KEY chua duoc cau hinh tren server")
    return api_key


def _fetch_station_stats(start_time, end_time):
    response = requests.get(
        VRAIN_STATS_URL,
        params={"start_time": start_time, "end_time": end_time},
        headers={
            "x-api-key": _get_api_key(),
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if not response.ok:
        raise requests.HTTPError(
            f"Loi goi VRAIN API: HTTP {response.status_code}",
            response=response,
        )
    return response.json()


def _sum_station_totals(stats_data):
    all_stations_data = stats_data.get("Data") or []
    if not all_stations_data:
        raise VrainNoDataError("VRAIN khong tra du lieu luong mua.")

    station_totals = {field: 0.0 for field in set(STATIONS_MAPPING.values())}
    matched_station_count = 0

    for station_data in all_stations_data:
        station_id = str(station_data.get("station_id"))
        field_name = STATIONS_MAPPING.get(station_id)
        if not field_name:
            continue

        matched_station_count += 1
        values = station_data.get("value") or []

        total_depth = 0.0
        for value in values:
            try:
                total_depth += float(value.get("depth") or 0)
            except (ValueError, TypeError):
                pass

        station_totals[field_name] += total_depth

    if matched_station_count == 0:
        raise VrainNoDataError("VRAIN khong tra du lieu cho cac tram dang theo doi.")

    return {key: round(value, 2) for key, value in station_totals.items()}


def _vn_now():
    return datetime.now(pytz.timezone("Asia/Ho_Chi_Minh"))


def _parse_date(date_value):
    if not date_value:
        return _vn_now().date()
    if hasattr(date_value, "year") and hasattr(date_value, "month"):
        return date_value
    return datetime.strptime(str(date_value), "%Y-%m-%d").date()


def sync_vrain_daily_rainfall(date_value=None):
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now_vn = _vn_now()
    target_date = _parse_date(date_value)
    start_time = f"{target_date} 00:00:00"
    end_time = (
        f"{target_date} {str(now_vn.hour).zfill(2)}:59:59"
        if target_date == now_vn.date()
        else f"{target_date} 23:59:59"
    )

    station_totals = _sum_station_totals(_fetch_station_stats(start_time, end_time))
    db_time = vn_tz.localize(datetime.combine(target_date, datetime.min.time()))

    obj = TramDoMuaVrain.objects.filter(Thoi_gian=db_time).order_by("id").first()
    created = obj is None
    if created:
        obj = TramDoMuaVrain.objects.create(Thoi_gian=db_time, **station_totals)
    else:
        for field_name, value in station_totals.items():
            setattr(obj, field_name, value)
        obj.save(update_fields=list(station_totals.keys()))

    return {
        "ok": True,
        "message": "Dong bo thanh cong",
        "date": str(target_date),
        "created": created,
        "data": station_totals,
    }


def get_vrain_realtime_24h():
    now_vn = _vn_now()
    past_24h = now_vn - timedelta(hours=23, minutes=59, seconds=59)
    start_time = past_24h.strftime("%Y-%m-%d %H:%M:%S")
    end_time = now_vn.strftime("%Y-%m-%d %H:%M:%S")
    station_totals = _sum_station_totals(_fetch_station_stats(start_time, end_time))

    return {
        "ok": True,
        "start_time": start_time,
        "end_time": end_time,
        "data": station_totals,
    }
