from __future__ import annotations

import statistics
import unicodedata
from datetime import datetime, time
from typing import Iterable

from django.utils import timezone
from django.utils.dateparse import parse_date

import hydro_data_repository
from thongsothuyvan.models import SongHinhRealtimeSnapshot, VinhSonRealtimeSnapshot


RAINFALL_STATIONS = {
    "songhinh": [
        "Xa_Ea_M_doan",
        "Thon_10_Xa_Ea_M_Doal",
        "UBND_xa_Song_Hinh",
        "Cu_Kroa",
        "Xa_Ea_Trang",
        "Dap_Tran",
    ],
    "vinhson": [
        "Ho_A_TD_Vinh_Son",
        "Ho_B_TD_Vinh_Son",
        "Ho_C_TD_Vinh_Son",
    ],
}


def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return " ".join(text.replace("-", " ").replace("_", " ").lower().split())


def _parse_day(value: str | None):
    if not value:
        return None
    value = value.strip()
    parsed = parse_date(value)
    if parsed:
        return parsed
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _date_bounds(start_date: str | None, end_date: str | None):
    start = _parse_day(start_date)
    end = _parse_day(end_date)
    if start and end and start > end:
        start, end = end, start
    return start, end


def _aware_start(day):
    return timezone.make_aware(datetime.combine(day, time.min)) if timezone.is_naive(datetime.combine(day, time.min)) else datetime.combine(day, time.min)


def _aware_end(day):
    return timezone.make_aware(datetime.combine(day, time.max)) if timezone.is_naive(datetime.combine(day, time.max)) else datetime.combine(day, time.max)


def _factory_key(reservoir: str | None) -> str:
    normalized = _normalize_text(reservoir)
    if any(token in normalized for token in ("vinh son", "vinhson", "vs")):
        return "vinhson"
    return "songhinh"


def _station_list(reservoir: str | None, stations: list[str] | None = None):
    if stations:
        return stations
    return RAINFALL_STATIONS[_factory_key(reservoir)]


def _stats(values: Iterable[float]):
    values = [float(v) for v in values if v is not None]
    if not values:
        return {
            "count": 0,
            "total": 0.0,
            "avg": 0.0,
            "min": 0.0,
            "max": 0.0,
            "stdev": 0.0,
        }
    return {
        "count": len(values),
        "total": sum(values),
        "avg": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
    }


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def _render_stats_table(rows):
    table = ["| Chỉ tiêu | Số mẫu | Tổng | Trung bình | Nhỏ nhất | Lớn nhất | Độ lệch chuẩn |"]
    table.append("|---|---:|---:|---:|---:|---:|---:|")
    for label, stat, unit in rows:
        table.append(
            "| {label} | {count} | {total} {unit} | {avg} {unit} | {minv} {unit} | {maxv} {unit} | {stdev} {unit} |".format(
                label=label,
                count=stat["count"],
                total=_fmt(stat["total"]),
                avg=_fmt(stat["avg"]),
                minv=_fmt(stat["min"]),
                maxv=_fmt(stat["max"]),
                stdev=_fmt(stat["stdev"]),
                unit=unit,
            )
        )
    return "\n".join(table)


def _rainfall_stats(start_date=None, end_date=None, reservoir=None, stations=None, limit=300):
    start, end = _date_bounds(start_date, end_date)
    rows = hydro_data_repository.query_rainfall_data(
        start.isoformat() if start else None,
        end.isoformat() if end else None,
        limit=limit,
    )
    selected = _station_list(reservoir, stations)
    result_rows = []
    for station in selected:
        result_rows.append((station, _stats(row.get(station) for row in rows), "mm"))
    return rows, result_rows, selected


def _water_volume_curve_stats(reservoir=None, limit=300):
    model = hydro_data_repository._model_for_reservoir(reservoir or "Song Hinh")
    records = list(model.objects.order_by("Mucnuoc")[:limit])
    levels = [float(record.Mucnuoc) for record in records]
    volumes = [float(record.dungtich) for record in records]
    slopes = []
    for idx in range(1, len(records)):
        dh = levels[idx] - levels[idx - 1]
        if dh:
            slopes.append((volumes[idx] - volumes[idx - 1]) / dh)
    return records, [
        ("Mực nước", _stats(levels), "m"),
        ("Dung tích", _stats(volumes), "triệu m³"),
        ("dV/dH", _stats(slopes), "triệu m³/m"),
    ]


def _realtime_queryset(reservoir=None, start_date=None, end_date=None, limit=300):
    start, end = _date_bounds(start_date, end_date)
    factory = _factory_key(reservoir)
    model = VinhSonRealtimeSnapshot if factory == "vinhson" else SongHinhRealtimeSnapshot
    qs = model.objects.all().order_by("-time_stamp")
    if start:
        qs = qs.filter(time_stamp__gte=_aware_start(start))
    if end:
        qs = qs.filter(time_stamp__lte=_aware_end(end))
    return list(qs[:limit]), factory


def _realtime_stats(reservoir=None, start_date=None, end_date=None, limit=300):
    rows, factory = _realtime_queryset(reservoir, start_date, end_date, limit)
    if factory == "vinhson":
        stat_rows = [
            ("Mực nước hồ A", _stats(row.mntla for row in rows), "m"),
            ("Mực nước hồ B", _stats(row.mntlb for row in rows), "m"),
            ("Mực nước hồ C", _stats(row.mntlc for row in rows), "m"),
            ("Qcm", _stats(row.qcm for row in rows), "m³/s"),
            ("Q xả tràn", _stats(row.qtran for row in rows), "m³/s"),
        ]
    else:
        stat_rows = [
            ("Mực nước hồ", _stats(row.mnhl for row in rows), "m"),
            ("Qcm", _stats(row.qcm for row in rows), "m³/s"),
            ("Q xả tràn", _stats(row.qtran for row in rows), "m³/s"),
            ("Dung tích hồ", _stats(row.dung_tich_ho for row in rows), "triệu m³"),
            ("Dung tích phòng lũ", _stats(row.dung_tich_phong_lu for row in rows), "triệu m³"),
        ]
    return rows, stat_rows


def analyze_hydro_data(data_type, reservoir="Song Hinh", start_date=None, end_date=None, stations=None, limit=300):
    limit = max(10, min(int(limit or 300), 1000))
    if data_type == "rainfall":
        rows, stat_rows, selected = _rainfall_stats(start_date, end_date, reservoir, stations, limit)
        title = f"### Phân tích dữ liệu mưa - {reservoir or 'theo phạm vi mặc định'}"
        notes = f"- Khoảng ngày: {start_date or 'không giới hạn'} đến {end_date or 'không giới hạn'}\n- Trạm dùng: {', '.join(selected)}\n- Số bản ghi đọc: {len(rows)}"
    elif data_type == "realtime_water_level":
        rows, stat_rows = _realtime_stats(reservoir, start_date, end_date, limit)
        title = f"### Phân tích dữ liệu realtime - {reservoir or 'Sông Hinh'}"
        notes = f"- Khoảng ngày: {start_date or 'không giới hạn'} đến {end_date or 'không giới hạn'}\n- Số bản ghi đọc: {len(rows)}"
    elif data_type == "water_volume_curve":
        rows, stat_rows = _water_volume_curve_stats(reservoir, limit)
        title = f"### Phân tích bảng quan hệ mực nước - dung tích - {reservoir or 'Sông Hinh'}"
        notes = f"- Bảng H-V là dữ liệu quan hệ tĩnh, không lọc theo ngày.\n- Số bản ghi đọc: {len(rows)}"
    else:
        return f"Không hỗ trợ data_type: {data_type}"

    return "\n\n".join(
        [
            title,
            _render_stats_table(stat_rows),
            "#### Phạm vi và giả định",
            notes,
            "#### Lưu ý",
            "Workspace này chỉ đọc dữ liệu và phục vụ phân tích nhanh. Các tính toán vận hành chính thức vẫn nên dùng các tool chuyên dụng như water_tools.",
        ]
    )


def compare_hydro_periods(data_type, current_start, current_end, compare_start, compare_end, reservoir="Song Hinh", stations=None):
    if data_type == "rainfall":
        _, current_rows, selected = _rainfall_stats(current_start, current_end, reservoir, stations, 1000)
        _, compare_rows, _ = _rainfall_stats(compare_start, compare_end, reservoir, selected, 1000)
        unit = "mm"
    elif data_type == "realtime_water_level":
        _, current_rows = _realtime_stats(reservoir, current_start, current_end, 1000)
        _, compare_rows = _realtime_stats(reservoir, compare_start, compare_end, 1000)
        unit = ""
    else:
        return f"Không hỗ trợ so sánh data_type: {data_type}"

    compare_by_label = {label: stat for label, stat, _unit in compare_rows}
    lines = [
        f"### So sánh dữ liệu {data_type} - {reservoir or 'Sông Hinh'}",
        f"**Kỳ hiện tại:** {current_start} đến {current_end}",
        f"**Kỳ so sánh:** {compare_start} đến {compare_end}",
        "",
        "| Chỉ tiêu | TB hiện tại | TB so sánh | Chênh lệch | % thay đổi |",
        "|---|---:|---:|---:|---:|",
    ]
    for label, current_stat, row_unit in current_rows:
        compare_stat = compare_by_label.get(label, _stats([]))
        diff = current_stat["avg"] - compare_stat["avg"]
        pct = (diff / compare_stat["avg"] * 100) if compare_stat["avg"] else 0.0
        display_unit = row_unit or unit
        lines.append(
            f"| {label} | {_fmt(current_stat['avg'])} {display_unit} | {_fmt(compare_stat['avg'])} {display_unit} | {_fmt(diff)} {display_unit} | {_fmt(pct, 1)}% |"
        )
    lines.extend(
        [
            "",
            "#### Phạm vi và giả định",
            "- So sánh dựa trên trung bình các bản ghi trong từng khoảng ngày.",
            "- Workspace này chỉ đọc dữ liệu. Nếu cần kết luận vận hành chính thức, dùng tiếp các tool tính toán chuyên dụng.",
        ]
    )
    return "\n".join(lines)
