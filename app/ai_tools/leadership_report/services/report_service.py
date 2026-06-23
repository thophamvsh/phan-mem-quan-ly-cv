import requests
from datetime import datetime, time, timedelta
from django.utils import timezone

from ..config import (
    LEADERSHIP_PRODUCTION_PLANTS,
    LEADERSHIP_RAINFALL_STATIONS,
    LEADERSHIP_RESERVOIR_STATS,
    LEADERSHIP_WEATHER_LOCATIONS,
    LEADERSHIP_WEEKLY_LIMIT_RESERVOIRS,
)
from ..utils.formatting import (
    add_report_totals,
    as_float,
    escape_markdown_cell,
    fmt_report_decimal,
    fmt_report_direct_pct,
    fmt_report_number,
    fmt_report_pct,
    record_value,
    sum_record_field,
)


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CODE_TEXT = {
    0: "Trời quang",
    1: "Ít mây",
    2: "Mây rải rác",
    3: "Nhiều mây",
    45: "Sương mù",
    48: "Sương mù đóng băng",
    51: "Mưa phùn nhẹ",
    53: "Mưa phùn",
    55: "Mưa phùn dày",
    61: "Mưa nhỏ",
    63: "Mưa vừa",
    65: "Mưa to",
    80: "Mưa rào nhẹ",
    81: "Mưa rào",
    82: "Mưa rào mạnh",
    95: "Dông",
    96: "Dông, có mưa đá",
    99: "Dông mạnh, có mưa đá",
}


def _fmt_report_date(value):
    if not value:
        return "-"
    return value.strftime("%d/%m/%Y")


def _fmt_report_datetime(value):
    if not value:
        return "-"
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")


def _weather_text(code):
    try:
        return WEATHER_CODE_TEXT.get(int(code), f"Mã {code}")
    except (TypeError, ValueError):
        return "-"


def _fetch_weather_forecast(location):
    response = requests.get(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "daily": ",".join(
                (
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "precipitation_probability_max",
                )
            ),
            "forecast_days": 7,
            "timezone": "Asia/Bangkok",
        },
        timeout=10,
    )
    response.raise_for_status()
    daily = response.json().get("daily") or {}
    times = daily.get("time") or []
    weather_codes = daily.get("weather_code") or []
    temp_max_values = daily.get("temperature_2m_max") or []
    temp_min_values = daily.get("temperature_2m_min") or []
    precipitation_values = daily.get("precipitation_sum") or []
    precipitation_probability_values = daily.get("precipitation_probability_max") or []
    return [
        {
            "date": day,
            "weather_code": weather_codes[index] if index < len(weather_codes) else None,
            "temperature_max": temp_max_values[index] if index < len(temp_max_values) else None,
            "temperature_min": temp_min_values[index] if index < len(temp_min_values) else None,
            "precipitation": precipitation_values[index] if index < len(precipitation_values) else None,
            "precipitation_probability": (
                precipitation_probability_values[index] if index < len(precipitation_probability_values) else None
            ),
        }
        for index, day in enumerate(times[:7])
    ]


def _rainfall_records_by_period(start_date, end_date):
    from thongsothuyvan.models import TramDoMuaVrain

    return list(
        TramDoMuaVrain.objects.filter(
            Thoi_gian__date__gte=start_date,
            Thoi_gian__date__lte=end_date,
        ).order_by("Thoi_gian", "id")
    )


def _date_range(start_date, days_count):
    return [start_date + timedelta(days=offset) for offset in range(days_count)]


def _rainfall_daily_table(records, start_date, days_count):
    daily_station_totals = {}
    for record in records:
        record_date = timezone.localtime(record.Thoi_gian).date()
        if record_date not in daily_station_totals:
            daily_station_totals[record_date] = {}
        for field_name, _station_name in LEADERSHIP_RAINFALL_STATIONS:
            value = record_value(record, field_name)
            if value is None:
                continue
            daily_station_totals[record_date][field_name] = (
                daily_station_totals[record_date].get(field_name, 0.0) + value
            )

    station_headers = [station_name for _field_name, station_name in LEADERSHIP_RAINFALL_STATIONS]
    header = "| Ngày | {stations} | Tổng ngày (mm) |".format(stations=" | ".join(station_headers))
    separator = "|------|{station_separators}----------------|".format(
        station_separators="".join("--------|" for _station in station_headers)
    )
    rows = []
    for report_date in _date_range(start_date, days_count):
        station_values = daily_station_totals.get(report_date, {})
        values = [station_values.get(field_name) for field_name, _station_name in LEADERSHIP_RAINFALL_STATIONS]
        total = sum(value for value in values if value is not None) if any(value is not None for value in values) else None
        rows.append(
            "| {date} | {values} | {total} |".format(
                date=_fmt_report_date(report_date),
                values=" | ".join(fmt_report_decimal(value, 1) for value in values),
                total=fmt_report_decimal(total, 1),
            )
        )
    return header, separator, rows


def _weather_forecast_rows():
    rows = []
    for location in LEADERSHIP_WEATHER_LOCATIONS:
        try:
            forecasts = _fetch_weather_forecast(location)
        except Exception:
            rows.append(f"| {location['name']} | Không lấy được dự báo | - | - | - | - |")
            continue

        if not forecasts:
            rows.append(f"| {location['name']} | Không có dữ liệu dự báo | - | - | - | - |")
            continue

        for forecast in forecasts[:7]:
            rows.append(
                "| {location} | {date} | {weather} | {temperature} | {rain} | {rain_prob} |".format(
                    location=location["name"],
                    date=forecast.get("date") or "-",
                    weather=_weather_text(forecast.get("weather_code")),
                    temperature=(
                        "{min_temp}-{max_temp}°C".format(
                            min_temp=fmt_report_decimal(forecast.get("temperature_min"), 1),
                            max_temp=fmt_report_decimal(forecast.get("temperature_max"), 1),
                        )
                        if forecast.get("temperature_min") is not None and forecast.get("temperature_max") is not None
                        else "-"
                    ),
                    rain=fmt_report_decimal(forecast.get("precipitation"), 1),
                    rain_prob=fmt_report_direct_pct(forecast.get("precipitation_probability")),
                )
            )
    return rows


def build_leadership_rainfall_weather_report(reference_date=None):
    reference_date = reference_date or timezone.localdate()
    days_count = 7
    start_date = reference_date - timedelta(days=days_count - 1)
    rainfall_records = _rainfall_records_by_period(start_date, reference_date)
    rainfall_header, rainfall_separator, rainfall_rows = _rainfall_daily_table(rainfall_records, start_date, days_count)
    weather_rows = _weather_forecast_rows()

    return f"""
### Tổng hợp lượng mưa và dự báo thời tiết

**Mưa đo:** {_fmt_report_date(start_date)} - {_fmt_report_date(reference_date)}

{rainfall_header}
{rainfall_separator}
{chr(10).join(rainfall_rows)}

**Dự báo thời tiết 7 ngày tới**

| Khu vực | Ngày | Thời tiết | Nhiệt độ | Mưa dự báo (mm) | Xác suất mưa |
|--------|------|-----------|----------|-----------------|--------------|
{chr(10).join(weather_rows)}

**Nguồn:** Mưa đo lấy từ bảng trạm đo mưa VRAIN trong database; dự báo thời tiết lấy từ Open-Meteo API.
""".strip()


def _latest_operating_records(reference_date):
    from thongsothuyvan.models import ThongsoSanxuat

    plant_codes = {config["plant_code"] for config in LEADERSHIP_WEEKLY_LIMIT_RESERVOIRS}
    records = {}
    for plant_code in plant_codes:
        records[plant_code] = (
            ThongsoSanxuat.objects.filter(
                nha_may=plant_code,
                thoi_gian__date__lte=reference_date,
            )
            .order_by("-thoi_gian", "-id")
            .first()
        )
    return records


def _weekly_setting_records(reference_date, week_number):
    from thongsothuyvan.models import ThongSoThuyVanCaiDat

    records = {}
    # Thử tìm các record bao phủ reference_date trước
    db_records = ThongSoThuyVanCaiDat.objects.filter(
        loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
        tuan_bat_dau__lte=reference_date,
        tuan_ket_thuc__gte=reference_date,
    )
    for record in db_records:
        records[record.nha_may] = record

    if records:
        return records

    # Fallback theo năm ISO
    monday = reference_date - timedelta(days=reference_date.weekday())
    iso_year = monday.isocalendar()[0]
    for record in ThongSoThuyVanCaiDat.objects.filter(
        nam=iso_year,
        loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
        thang=0,
        tuan=week_number,
    ):
        records[record.nha_may] = record
    return records


def _week_end_from_settings(settings_by_plant, reference_date):
    dates = [
        record.tuan_ket_thuc
        for record in settings_by_plant.values()
        if getattr(record, "tuan_ket_thuc", None)
    ]
    if dates:
        return max(dates)
    return reference_date


def _week_start_from_settings(settings_by_plant, reference_date):
    dates = [
        record.tuan_bat_dau
        for record in settings_by_plant.values()
        if getattr(record, "tuan_bat_dau", None)
    ]
    if dates:
        return min(dates)
    return reference_date - timedelta(days=reference_date.weekday())


def _remaining_seconds_to_week_end(reference_time, week_end_date):
    end_time = timezone.make_aware(datetime.combine(week_end_date, time.max))
    return max((end_time - timezone.localtime(reference_time)).total_seconds(), 0)


def _operating_level_by_capacity(reservoir_key, target_capacity):
    from thongsothuyvan.hydrology_services import get_capacity_by_reservoir_level, get_capacity_points_for_reservoir

    if target_capacity is None:
        return None
    points = get_capacity_points_for_reservoir(reservoir_key)
    if not points:
        return None

    min_level = points[0][0]
    min_capacity = get_capacity_by_reservoir_level(reservoir_key, min_level)
    if min_capacity is None:
        return None

    absolute_capacity = float(min_capacity) + float(target_capacity)
    capacity_points = [(float(level), float(capacity)) for level, capacity in points]
    if absolute_capacity <= capacity_points[0][1]:
        return capacity_points[0][0]
    if absolute_capacity >= capacity_points[-1][1]:
        return capacity_points[-1][0]

    for index in range(1, len(capacity_points)):
        lower_level, lower_capacity = capacity_points[index - 1]
        upper_level, upper_capacity = capacity_points[index]
        if lower_capacity <= absolute_capacity <= upper_capacity:
            if upper_capacity == lower_capacity:
                return lower_level
            ratio = (absolute_capacity - lower_capacity) / (upper_capacity - lower_capacity)
            return lower_level + ratio * (upper_level - lower_level)
    return None


def _forecast_weekly_limit_status(forecast_level, weekly_limit):
    if forecast_level is None or weekly_limit is None:
        return "Chưa đủ dữ liệu dự báo"
    gap = forecast_level - weekly_limit
    if gap > 0:
        return f"Dự báo cuối tuần cao hơn MNGH {fmt_report_decimal(gap, 2)} m"
    if gap < 0:
        return f"Dự báo cuối tuần thấp hơn MNGH {fmt_report_decimal(abs(gap), 2)} m"
    return "Dự báo cuối tuần bằng MNGH"


def _current_weekly_limit_status(current_level, weekly_limit):
    if current_level is None or weekly_limit is None:
        return "Chưa đủ dữ liệu hiện trạng"
    gap = current_level - weekly_limit
    if gap > 0:
        return f"Hiện tại cao hơn MNGH {fmt_report_decimal(gap, 2)} m"
    if gap < 0:
        return f"Hiện tại thấp hơn MNGH {fmt_report_decimal(abs(gap), 2)} m"
    return "Hiện tại bằng MNGH"


def _format_weekly_limit_row(config, record, setting, week_start_date, reference_date, week_end_date):
    from thongsothuyvan.hydrology_services import get_operating_capacity_by_reservoir_level
    from django.db.models import Avg
    from thongsothuyvan.models import ThongsoSanxuat

    if not record:
        return f"| {config['name']} | Không có dữ liệu | - | - | - | - | - | - | - | - | - | - |"

    current_level = record_value(record, config["level_field"])
    weekly_limit = record_value(setting, config["limit_field"]) if config.get("limit_field") else None
    current_capacity = get_operating_capacity_by_reservoir_level(config["reservoir_key"], current_level)
    limit_capacity = get_operating_capacity_by_reservoir_level(config["reservoir_key"], weekly_limit)
    level_gap = current_level - weekly_limit if current_level is not None and weekly_limit is not None else None
    capacity_gap = limit_capacity - current_capacity if current_capacity is not None and limit_capacity is not None else None

    # Lấy lưu lượng trung bình từ đầu tuần đến ngày báo cáo
    avg_qve = None
    avg_qcm = None

    filter_kwargs = {
        "nha_may": config["plant_code"],
        "thoi_gian__date__gte": week_start_date,
        "thoi_gian__date__lte": reference_date,
    }
    aggregate_args = {}
    if config.get("qve_field"):
        from django.db.models import Avg
        if config["plant_code"] == "vinhson" and config["reservoir_key"] == "vinhson_a":
            from django.db.models import F
            from django.db.models.functions import Coalesce
            aggregate_args["avg_qve"] = Avg(
                F("cot_i") - Coalesce(F("luuluong_ve_ho_b"), 0.0) - Coalesce(F("luuluong_ve_ho_c"), 0.0)
            )
        else:
            aggregate_args["avg_qve"] = Avg(config["qve_field"])
    if config.get("qcm_field"):
        from django.db.models import Avg
        aggregate_args["avg_qcm"] = Avg(config["qcm_field"])

    if aggregate_args:
        aggregates = ThongsoSanxuat.objects.filter(**filter_kwargs).aggregate(**aggregate_args)
        avg_qve = aggregates.get("avg_qve")
        avg_qcm = aggregates.get("avg_qcm")

    qve = avg_qve
    qcm = avg_qcm

    forecast_capacity = None
    forecast_level = None
    current_status = _current_weekly_limit_status(current_level, weekly_limit)
    forecast_note = "Chưa đủ dữ liệu Qcm/điều tiết để dự báo"
    if current_capacity is not None and qve is not None and qcm is not None:
        remaining_seconds = _remaining_seconds_to_week_end(record.thoi_gian, week_end_date)
        delta_capacity = (qve - qcm) * remaining_seconds / 1_000_000
        forecast_capacity = current_capacity + delta_capacity
        forecast_level = _operating_level_by_capacity(config["reservoir_key"], forecast_capacity)
        forecast_note = _forecast_weekly_limit_status(forecast_level, weekly_limit)

    status = forecast_note if weekly_limit is None else f"{current_status}; {forecast_note}"

    return (
        "| {reservoir} | {time} | {current_level} | {weekly_limit} | {level_gap} | {current_capacity} | "
        "{capacity_gap} | {qve} | {qcm} | {forecast_level} | {forecast_capacity} | {status} |"
    ).format(
        reservoir=config["name"],
        time=_fmt_report_datetime(record.thoi_gian),
        current_level=fmt_report_decimal(current_level, 2),
        weekly_limit=fmt_report_decimal(weekly_limit, 2),
        level_gap=fmt_report_decimal(level_gap, 2),
        current_capacity=fmt_report_decimal(current_capacity, 3),
        capacity_gap=fmt_report_decimal(capacity_gap, 3),
        qve=fmt_report_decimal(qve, 2),
        qcm=fmt_report_decimal(qcm, 2),
        forecast_level=fmt_report_decimal(forecast_level, 2),
        forecast_capacity=fmt_report_decimal(forecast_capacity, 3),
        status=status,
    )


def build_leadership_weekly_limit_report(reference_date=None):
    from thongsothuyvan.hydrology_services import get_settings_week_number

    reference_date = reference_date or timezone.localdate()
    week_number = get_settings_week_number(reference_date)
    settings_by_plant = _weekly_setting_records(reference_date, week_number)
    week_start_date = _week_start_from_settings(settings_by_plant, reference_date)
    week_end_date = _week_end_from_settings(settings_by_plant, reference_date)
    latest_records = _latest_operating_records(reference_date)
    rows = [
        _format_weekly_limit_row(
            config,
            latest_records.get(config["plant_code"]),
            settings_by_plant.get(config["plant_code"]),
            week_start_date,
            reference_date,
            week_end_date,
        )
        for config in LEADERSHIP_WEEKLY_LIMIT_RESERVOIRS
    ]

    return f"""
### Mực nước giới hạn tuần và phân tích

**Tuần:** {week_number} ({_fmt_report_date(week_start_date)} - {_fmt_report_date(week_end_date)})

| Hồ | Thời điểm số liệu | MN hiện tại (m) | MNGH tuần (m) | Chênh MN hiện tại-GH (m) | DT hiện tại (tr.m³) | Dung tích còn tới GH (tr.m³) | Qve (m³/s) | Qcm (m³/s) | MN dự báo cuối tuần (m) | DT dự báo cuối tuần (tr.m³) | Đánh giá |
|----|-------------------|-----------------|---------------|--------------------------|---------------------|------------------------------|------------|------------|-------------------------|------------------------------|----------|
{chr(10).join(rows)}

**Ghi chú:** MN dự báo cuối tuần = dung tích hiện tại + (Qve - Qcm) * thời gian còn lại đến cuối tuần / 1.000.000. Vĩnh Sơn B hiện chưa có Qcm riêng trong dữ liệu nên chỉ phân tích hiện trạng khi thiếu dữ liệu điều tiết ra.
""".strip()


def _format_production_report_row(plant_name, metrics):
    return (
        "| {plant} | {day} | {qc_day} | {pct_day} | {month} | {qc_month} | {pct_month} | {year} | {plan_year} | {pct_year} |"
    ).format(
        plant=plant_name,
        day=fmt_report_number(metrics["commercial_day"]),
        qc_day=fmt_report_number(metrics["qc_day"]),
        pct_day=fmt_report_pct(metrics["commercial_day"], metrics["qc_day"]),
        month=fmt_report_number(metrics["commercial_month"]),
        qc_month=fmt_report_number(metrics["qc_month"]),
        pct_month=fmt_report_pct(metrics["commercial_month"], metrics["qc_month"]),
        year=fmt_report_number(metrics["commercial_year"]),
        plan_year=fmt_report_number(metrics["plan_year"]),
        pct_year=fmt_report_pct(metrics["commercial_year"], metrics["plan_year"]),
    )


def _format_hydrology_report_row(config, record):
    from thongsothuyvan.hydrology_services import (
        get_operating_capacity_by_reservoir_level,
        get_operating_capacity_range_for_reservoir,
    )

    if not record:
        return f"| {config['name']} | Không có dữ liệu | - | - | - | - | - | - |"

    level = record_value(record, config["level_field"])
    useful_capacity = get_operating_capacity_by_reservoir_level(config["reservoir_key"], level)
    useful_capacity_range = get_operating_capacity_range_for_reservoir(config["reservoir_key"])
    max_useful_capacity = as_float(useful_capacity_range.get("max"))
    useful_percent = None
    if useful_capacity is not None and max_useful_capacity and max_useful_capacity > 0:
        useful_percent = max(min(useful_capacity / max_useful_capacity * 100, 100), 0)

    qve_val = None
    if config["plant_code"] == "vinhson" and config["reservoir_key"] == "vinhson_a":
        tot_qve = record_value(record, "cot_i")
        if tot_qve is not None:
            qb = record_value(record, "luuluong_ve_ho_b") or 0.0
            qc = record_value(record, "luuluong_ve_ho_c") or 0.0
            qve_val = tot_qve - qb - qc
    else:
        qve_val = record_value(record, config["qve_field"])

    return (
        "| {reservoir} | {level} | {total_capacity} | {useful_capacity} | {useful_percent} | {qve} | {qcm} | {spill} |"
    ).format(
        reservoir=config["name"],
        level=fmt_report_decimal(level, 2),
        total_capacity=fmt_report_decimal(useful_capacity, 3),
        useful_capacity=fmt_report_decimal(useful_capacity, 3),
        useful_percent=fmt_report_direct_pct(useful_percent),
        qve=fmt_report_decimal(qve_val, 2),
        qcm=fmt_report_decimal(record_value(record, config["qcm_field"]), 2),
        spill=fmt_report_decimal(record_value(record, config["spill_field"]), 2),
    )


def build_leadership_hydrology_report(report_date):
    from thongsothuyvan.models import ThongsoSanxuat

    plant_codes = {config["plant_code"] for config in LEADERSHIP_RESERVOIR_STATS}
    latest_records = {}
    for plant_code in plant_codes:
        latest_records[plant_code] = (
            ThongsoSanxuat.objects.filter(
                nha_may=plant_code,
                thoi_gian__date=report_date,
            )
            .order_by("-thoi_gian", "-id")
            .first()
        )

    rows = [
        _format_hydrology_report_row(config, latest_records.get(config["plant_code"]))
        for config in LEADERSHIP_RESERVOIR_STATS
    ]

    return f"""
### Thông số thủy văn

| Hồ | Mực nước hồ (m) | Dung tích hồ (tr.m³) | DT hữu ích còn lại (tr.m³) | Còn lại | Qve (m³/s) | Qcm (m³/s) | Qxả tràn (m³/s) |
|----|-----------------|----------------------|----------------------------|---------|------------|------------|-----------------|
{chr(10).join(rows)}

**Ghi chú:** Dung tích hồ trong bảng là dung tích vận hành hữu ích theo mực nước hiện tại; tỷ lệ phần trăm được tính trên dung tích vận hành hữu ích tối đa của từng hồ. Vĩnh Sơn B/C không có chỉ tiêu Qcm và Qxả tràn riêng trong bảng dữ liệu hiện tại.
""".strip()


def build_leadership_production_report(report_date):
    from thongsothuyvan.models import ThongSoThuyVanCaiDat, ThongsoSanxuat

    plant_codes = [plant_code for plant_code, _ in LEADERSHIP_PRODUCTION_PLANTS]
    monthly_settings = {
        record.nha_may: record.sanluong_kehoach_thang
        for record in ThongSoThuyVanCaiDat.objects.filter(
            nha_may__in=plant_codes,
            nam=report_date.year,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=report_date.month,
        )
        if record.sanluong_kehoach_thang is not None
    }
    annual_settings = {
        record.nha_may: record.sanluong_kehoach_nam
        for record in ThongSoThuyVanCaiDat.objects.filter(
            nha_may__in=plant_codes,
            nam=report_date.year,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
        )
        if record.sanluong_kehoach_nam is not None
    }

    rows = []
    totals = {
        "commercial_day": None,
        "qc_day": None,
        "commercial_month": None,
        "qc_month": None,
        "commercial_year": None,
        "plan_year": None,
    }

    for plant_code, plant_name in LEADERSHIP_PRODUCTION_PLANTS:
        records = list(
            ThongsoSanxuat.objects.filter(
                nha_may=plant_code,
                thoi_gian__date=report_date,
            ).order_by("cot_c", "thoi_gian")
        )

        if not records:
            rows.append(f"| {plant_name} | Không có dữ liệu | - | - | - | - | - | - | - | - |")
            continue

        commercial_day = sum_record_field(records, "cot_n")
        qc_day = sum_record_field(records, "cot_l")
        commercial_month = sum_record_field(records, "cot_r")
        qc_month = monthly_settings.get(plant_code)
        if qc_month is None:
            qc_month = sum_record_field(records, "sanluong_kh_thang")
        if qc_month is None:
            qc_month = sum_record_field(records, "cot_p")
        commercial_year = sum_record_field(records, "cot_v")
        plan_year = annual_settings.get(plant_code)
        if plan_year is None:
            plan_year = sum_record_field(records, "cot_w")
        if plan_year is None:
            plan_year = sum_record_field(records, "cot_t")

        metrics = {
            "commercial_day": commercial_day,
            "qc_day": qc_day,
            "commercial_month": commercial_month,
            "qc_month": qc_month,
            "commercial_year": commercial_year,
            "plan_year": plan_year,
        }
        add_report_totals(totals, metrics)
        rows.append(_format_production_report_row(plant_name, metrics))

    rows.append(_format_production_report_row("Tổng cộng", totals))
    hydrology_report = build_leadership_hydrology_report(report_date)

    return f"""
### Báo cáo tình hình sản xuất 3 nhà máy

**Ngày báo cáo:** {report_date.strftime("%d/%m/%Y")}

| Nhà máy | TP ngày | Qc ngày | Đạt ngày | TP tháng | Qc/KH tháng | Đạt tháng | TP năm | KH năm | Đạt năm |
|---------|---------|---------|----------|----------|-------------|-----------|--------|--------|---------|
{chr(10).join(rows)}

**Ghi chú:** Tỷ lệ ngày = TP ngày/Qc ngày; tỷ lệ tháng = TP tháng/QKH tháng trong thông số cài đặt (nếu có); tỷ lệ năm = TP năm/KH năm.

{hydrology_report}
""".strip()


def build_leadership_event_report(reference_date=None):
    from django.db.models import OuterRef, Prefetch, Q, Subquery
    from django.utils import timezone
    from datetime import timedelta
    from nhatkyvanhanh.models import KhacPhucSuKien, SuKien

    reference_date = reference_date or timezone.localdate()
    start_date = reference_date - timedelta(days=6)
    plant_codes = ["SH", "VS", "TKT"]
    pending_statuses = [
        SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
        SuKien.TrangThaiXuLy.DANG_XU_LY,
    ]
    latest_remediation_time = KhacPhucSuKien.objects.filter(
        su_kien=OuterRef("pk")
    ).order_by("-thoi_gian_xu_ly", "-created_at")
    remediation_prefetch = Prefetch(
        "khac_phuc_su_kiens",
        queryset=KhacPhucSuKien.objects.order_by("-thoi_gian_xu_ly", "-created_at"),
    )

    # 1. Thống kê sự kiện:
    # - Các sự kiện Chưa xử lý xong & Đang xử lý: lấy tất cả không giới hạn thời gian (tồn đọng)
    # - Các sự kiện Đã xử lý xong: chỉ lấy sự kiện được xử lý hoặc xảy ra trong vòng 7 ngày qua
    all_events = (
        SuKien.objects.filter(nha_may__ma_nha_may__in=plant_codes)
        .select_related("nha_may")
        .prefetch_related(remediation_prefetch)
        .annotate(latest_remediation_time=Subquery(latest_remediation_time.values("thoi_gian_xu_ly")[:1]))
        .filter(
            Q(trang_thai__in=pending_statuses)
            | Q(
                trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
                latest_remediation_time__date__gte=start_date,
                latest_remediation_time__date__lte=reference_date,
            )
            | Q(
                trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
                latest_remediation_time__isnull=True,
                thoi_gian_xay_ra__date__gte=start_date,
                thoi_gian_xay_ra__date__lte=reference_date,
            )
        )
    )

    stats = {
        "SH": {"total": 0, "chua_xu_ly": 0, "dang_xu_ly": 0, "xu_ly_xong": 0},
        "VS": {"total": 0, "chua_xu_ly": 0, "dang_xu_ly": 0, "xu_ly_xong": 0},
        "TKT": {"total": 0, "chua_xu_ly": 0, "dang_xu_ly": 0, "xu_ly_xong": 0},
    }

    for event in all_events:
        code = event.nha_may.ma_nha_may if event.nha_may else None
        if code in stats:
            if event.trang_thai == SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG:
                stats[code]["chua_xu_ly"] += 1
                stats[code]["total"] += 1
            elif event.trang_thai == SuKien.TrangThaiXuLy.DANG_XU_LY:
                stats[code]["dang_xu_ly"] += 1
                stats[code]["total"] += 1
            elif event.trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG:
                # Kiểm tra xem sự kiện được hoàn thành/xử lý trong 7 ngày qua hay không
                resolved_time = event.thoi_gian_xu_ly or event.thoi_gian_xay_ra
                if resolved_time:
                    resolved_date = timezone.localtime(resolved_time).date()
                    if start_date <= resolved_date <= reference_date:
                        stats[code]["xu_ly_xong"] += 1
                        stats[code]["total"] += 1

    # 2. Danh sách sự kiện chưa khắc phục xong (tồn đọng)
    pending_events = (
        SuKien.objects.filter(
            nha_may__ma_nha_may__in=plant_codes,
            trang_thai__in=pending_statuses,
        )
        .select_related("nha_may")
        .order_by("-thoi_gian_xay_ra")
    )

    # Format bảng markdown cho các sự kiện tồn đọng
    rows = []
    for event in pending_events:
        plant_name = event.nha_may.ten_nha_may if event.nha_may else "-"
        # Viết gọn tên thiết bị
        device_name = event.ten_he_thong_thiet_bi
        if len(device_name) > 30:
            device_name = device_name[:27] + "..."

        # Viết gọn diễn biến
        hien_tuong = event.hien_tuong_dien_bien
        if len(hien_tuong) > 50:
            hien_tuong = hien_tuong[:47] + "..."

        time_str = timezone.localtime(event.thoi_gian_xay_ra).strftime("%d/%m/%Y %H:%M")
        status_label = event.get_trang_thai_display()

        # Chỉ đạo hiện tại
        chi_dao_text = event.chi_dao.strip() if event.chi_dao else "-"
        if chi_dao_text != "-" and len(chi_dao_text) > 40:
            chi_dao_text = chi_dao_text[:37] + "..."

        action_link = f"[Chỉ đạo](/quanlyvanhanh/nhatkysukien?event={event.id})"

        rows.append(
            "| {plant_name} | {device_name} | {event_type} | {time} | {description} | {status} | {direction} | {action} |".format(
                plant_name=escape_markdown_cell(plant_name),
                device_name=escape_markdown_cell(device_name),
                event_type=escape_markdown_cell(event.get_loai_display()),
                time=escape_markdown_cell(time_str),
                description=escape_markdown_cell(hien_tuong),
                status=escape_markdown_cell(status_label),
                direction=escape_markdown_cell(chi_dao_text),
                action=action_link,
            )
        )

    pending_table = ""
    if rows:
        pending_table = "\n".join(rows)
    else:
        pending_table = "| - | - | - | - | - | - | - | - |"

    return f"""
### Tình hình thiết bị sự kiện của 3 nhà máy

**Thời gian thống kê (7 ngày qua):** {start_date.strftime("%d/%m/%Y")} - {reference_date.strftime("%d/%m/%Y")}

* **Sông Hinh:** {stats['SH']['total']} sự kiện (Chưa xử lý: {stats['SH']['chua_xu_ly']}, Đang xử lý: {stats['SH']['dang_xu_ly']}, Đã xử lý: {stats['SH']['xu_ly_xong']})
* **Vĩnh Sơn:** {stats['VS']['total']} sự kiện (Chưa xử lý: {stats['VS']['chua_xu_ly']}, Đang xử lý: {stats['VS']['dang_xu_ly']}, Đã xử lý: {stats['VS']['xu_ly_xong']})
* **Thượng Kon Tum:** {stats['TKT']['total']} sự kiện (Chưa xử lý: {stats['TKT']['chua_xu_ly']}, Đang xử lý: {stats['TKT']['dang_xu_ly']}, Đã xử lý: {stats['TKT']['xu_ly_xong']})

**Danh sách sự kiện chưa khắc phục xong (tồn đọng):**

| Nhà máy | Thiết bị / Hệ thống | Loại | Thời gian xảy ra | Diễn biến / Hiện tượng | Trạng thái | Chỉ đạo hiện tại | Thao tác |
|---------|---------------------|------|------------------|------------------------|------------|------------------|----------|
{pending_table}

**Tham mưu:** Ngài có thể nhấn vào liên kết **[Chỉ đạo]** ở cột Thao tác để xem chi tiết sự kiện và cho ý kiến chỉ đạo trực tiếp trên hệ thống.
""".strip()


def _event_statistics_period_label(start_date, end_date, all_time):
    if all_time:
        return "Tất cả dữ liệu"
    if start_date == end_date:
        return _fmt_report_date(start_date)
    return f"{_fmt_report_date(start_date)} - {_fmt_report_date(end_date)}"


def build_leadership_event_statistics_report(
    *,
    plant_code,
    plant_name,
    start_date=None,
    end_date=None,
    all_time=False,
    include_details=True,
):
    from nhatkyvanhanh.models import SuKien

    status_order = [
        SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
        SuKien.TrangThaiXuLy.DANG_XU_LY,
        SuKien.TrangThaiXuLy.XU_LY_XONG,
    ]
    status_labels = {
        SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG: "Chưa xử lý",
        SuKien.TrangThaiXuLy.DANG_XU_LY: "Đang xử lý",
        SuKien.TrangThaiXuLy.XU_LY_XONG: "Đã xử lý",
    }

    queryset = (
        SuKien.objects.filter(nha_may__ma_nha_may=plant_code)
        .select_related("nha_may")
        .order_by("-thoi_gian_xay_ra", "-created_at")
    )
    if not all_time:
        queryset = queryset.filter(
            thoi_gian_xay_ra__date__gte=start_date,
            thoi_gian_xay_ra__date__lte=end_date,
        )

    events = list(queryset)
    stats = {status: 0 for status in status_order}
    for event in events:
        if event.trang_thai in stats:
            stats[event.trang_thai] += 1

    # Kept in the signature for existing callers; statistics reports always expose detail links.
    include_details = True
    header = "| STT | Thời gian | Tên sự kiện | Loại | Trạng thái | Chi tiết |"
    separator = "|-----|-----------|-------------|------|------------|----------|"

    rows = []
    for index, event in enumerate(events, start=1):
        cells = [
            str(index),
            _fmt_report_datetime(event.thoi_gian_xay_ra),
            escape_markdown_cell(event.ten_he_thong_thiet_bi),
            escape_markdown_cell(event.get_loai_display()),
            escape_markdown_cell(status_labels.get(event.trang_thai, event.get_trang_thai_display())),
        ]
        cells.append(f"[Xem chi tiết](/quanlyvanhanh/nhatkysukien?event={event.id})")
        rows.append("| " + " | ".join(cells) + " |")

    if not rows:
        empty_cells = ["-", "-", "-", "-", "-", "-"]
        rows.append("| " + " | ".join(empty_cells) + " |")

    return f"""
### Thống kê sự kiện {plant_name}

**Thời gian:** {_event_statistics_period_label(start_date, end_date, all_time)}

**Tổng số:** {len(events)} sự kiện
* **Chưa xử lý:** {stats[SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG]}
* **Đang xử lý:** {stats[SuKien.TrangThaiXuLy.DANG_XU_LY]}
* **Đã xử lý:** {stats[SuKien.TrangThaiXuLy.XU_LY_XONG]}

{header}
{separator}
{chr(10).join(rows)}
""".strip()
