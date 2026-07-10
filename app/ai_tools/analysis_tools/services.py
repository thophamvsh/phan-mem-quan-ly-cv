from __future__ import annotations

import statistics
import unicodedata
from datetime import datetime, time
from typing import Iterable

from django.utils import timezone
from django.utils.dateparse import parse_date
from django.conf import settings

import hydro_data_repository
from thongsothuyvan.models import SongHinhRealtimeSnapshot, VinhSonRealtimeSnapshot


# Load configurations from Django settings, fallback to defaults
RATED_POWER_MAP = getattr(
    settings,
    "AI_TOOLS_RATED_POWER_MAP",
    {
        "SH": 37.0,
        "VS": 33.0,
        "TKT": 110.0,
    }
)

RAINFALL_STATIONS = getattr(
    settings,
    "AI_TOOLS_RAINFALL_STATIONS",
    {
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
)


def _normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return " ".join(text.replace("-", " ").replace("_", " ").lower().split())


def _clean_str(val: str | None) -> str:
    if not val:
        return ""
    val = val.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    return " ".join(val.split())


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
        display_unit = row_unit or unit
        current_avg = current_stat["avg"]
        if compare_stat["count"] > 0:
            compare_avg = compare_stat["avg"]
            diff = current_avg - compare_avg
            pct = (diff / compare_avg * 100) if compare_avg else 0.0
            compare_avg_str = f"{_fmt(compare_avg)} {display_unit}"
            diff_str = f"{_fmt(diff)} {display_unit}"
            pct_str = f"{_fmt(pct, 1)}%"
        else:
            compare_avg_str = "-"
            diff_str = "-"
            pct_str = "-"
        lines.append(
            f"| {label} | {_fmt(current_avg)} {display_unit} | {compare_avg_str} | {diff_str} | {pct_str} |"
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


def get_unit_state_profile(device_code: str, date: str | None = None, time: str | None = None, window: str | None = "60m", parameter_code: str | None = None) -> str:
    from quanlyvanhanh.models import ThietBi, ThongSoToMay, ThongSoTram110KV, ThongSoVanHanh
    from quanlyvanhanh.services.thongso_history_service import get_metric_thresholds, parse_number
    from django.db.models import Max, Q
    import re
    import json
    from datetime import timedelta
    
    # 1. Tìm thiết bị chính
    try:
        device = ThietBi.objects.get(ma_day_du=device_code)
    except ThietBi.DoesNotExist:
        return f"Không tìm thấy thiết bị với mã đầy đủ: {device_code}"

    device_ten_clean = _clean_str(device.ten)

    # 2. Xác định ngày truy vấn
    target_date = None
    if date:
        target_date = _parse_day(date)
        
    if not target_date:
        # Tìm ngày gần nhất có dữ liệu
        if parameter_code:
            # Ưu tiên tìm ngày gần nhất có dữ liệu cho tham số này
            latest_tm = ThongSoToMay.objects.filter(
                thiet_bi__ma_day_du__startswith=device_code,
                ma_thong_so__icontains=parameter_code
            ).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
            latest_vh = ThongSoVanHanh.objects.filter(
                thiet_bi__ma_day_du__startswith=device_code,
                ma_thong_so__icontains=parameter_code
            ).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
            latest_tram = ThongSoTram110KV.objects.filter(
                thiet_bi__ma_day_du__startswith=device_code,
                ma_thong_so__icontains=parameter_code
            ).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
            
            # Nếu không tìm thấy, thử tìm bất kỳ ngày nào có dữ liệu cho thiết bị
            if not latest_tm and not latest_vh and not latest_tram:
                latest_tm = ThongSoToMay.objects.filter(thiet_bi__ma_day_du__startswith=device_code).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
                latest_vh = ThongSoVanHanh.objects.filter(thiet_bi__ma_day_du__startswith=device_code).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
                latest_tram = ThongSoTram110KV.objects.filter(thiet_bi__ma_day_du__startswith=device_code).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
        else:
            latest_tm = ThongSoToMay.objects.filter(thiet_bi__ma_day_du__startswith=device_code).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
            latest_vh = ThongSoVanHanh.objects.filter(thiet_bi__ma_day_du__startswith=device_code).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
            latest_tram = ThongSoTram110KV.objects.filter(thiet_bi__ma_day_du__startswith=device_code).aggregate(Max('ngay_nhap'))['ngay_nhap__max']
            
        dates = [d for d in [latest_tm, latest_vh, latest_tram] if d is not None]
        target_date = max(dates) if dates else timezone.localtime(timezone.now()).date()

    # Map MBA device_code to generator unit device_code to fetch power data
    generator_device_code = None
    if "TPP.110.T1" in device_code.upper() or "TPP.T1" in device_code.upper():
        if device_code.upper().startswith("SH"):
            generator_device_code = "SH.TB.H1"
        elif device_code.upper().startswith("VS"):
            generator_device_code = "VS.TB.H1"
    elif "TPP.110.T2" in device_code.upper() or "TPP.T2" in device_code.upper():
        if device_code.upper().startswith("SH"):
            generator_device_code = "SH.TB.H2"
        elif device_code.upper().startswith("VS"):
            generator_device_code = "VS.TB.H2"

    device_filter = Q(thiet_bi__ma_day_du__startswith=device_code)
    if generator_device_code:
        device_filter |= Q(thiet_bi__ma_day_du__startswith=generator_device_code)

    # 3. Lấy dữ liệu của ToMay và VanHanh trong khoảng 15 ngày để so sánh
    comparison_days = 15
    comparison_start_date = target_date - timedelta(days=comparison_days - 1)
    qs_tm = ThongSoToMay.objects.filter(
        device_filter,
        ngay_nhap__gte=comparison_start_date,
        ngay_nhap__lte=target_date,
    ).select_related('thiet_bi')
    qs_vh = ThongSoVanHanh.objects.filter(
        device_filter,
        ngay_nhap__gte=comparison_start_date,
        ngay_nhap__lte=target_date,
    ).select_related('thiet_bi')
    qs_tram = ThongSoTram110KV.objects.filter(
        device_filter,
        ngay_nhap__gte=comparison_start_date,
        ngay_nhap__lte=target_date,
    ).select_related('thiet_bi')

    if not qs_tm.exists() and not qs_vh.exists() and not qs_tram.exists():
        return f"Không tìm thấy dữ liệu vận hành cho thiết bị {device_ten_clean} ({device_code}) trong khoảng {comparison_start_date.strftime('%d/%m/%Y')} đến {target_date.strftime('%d/%m/%Y')}."

    # 4. Group dữ liệu theo ngày/thời điểm và căn chỉnh theo múi giờ Việt Nam
    all_aligned_data = {}
    param_meta = {}

    def make_signal_key(record):
        return "|".join([
            record.thiet_bi.ma_day_du or "",
            record.ma_thong_so or "",
        ])

    def process_records(queryset, source):
        for r in queryset:
            # If this record belongs to the generator unit, only keep active power
            if generator_device_code and r.thiet_bi.ma_day_du.startswith(generator_device_code):
                metric_code = r.ma_thong_so or ""
                is_active_power = "cong_suat_tac_dung" in metric_code or "cong_suat_thuc" in metric_code or metric_code == "P"
                if not is_active_power:
                    continue

            val = parse_number(r.gia_tri)
            if val is None:
                continue
            
            local_dt = timezone.localtime(r.thoi_diem_nhap)
            day_key = r.ngay_nhap or local_dt.date()
            t_str = local_dt.strftime('%H:%M')
            
            if day_key not in all_aligned_data:
                all_aligned_data[day_key] = {}
            if t_str not in all_aligned_data[day_key]:
                all_aligned_data[day_key][t_str] = {}
                
            signal_key = make_signal_key(r)
            all_aligned_data[day_key][t_str][signal_key] = val
            
            if signal_key not in param_meta:
                thresh = get_metric_thresholds(None, source, r.ma_thong_so, r.thiet_bi)
                param_meta[signal_key] = {
                    'name': _clean_str(r.ten_thong_so),
                    'metric_code': r.ma_thong_so,
                    'unit': _clean_str(r.don_vi or ''),
                    'source': source,
                    'alarm': thresh.get('alarm'),
                    'trip': thresh.get('trip'),
                    'rated': thresh.get('rated'),
                    'device_name': _clean_str(r.thiet_bi.ten),
                    'device_code': r.thiet_bi.ma_day_du or '',
                    'factory': _clean_str(r.nha_may or getattr(r.thiet_bi, 'nha_may', '')),
                }

    process_records(qs_tm, 'tomay')
    process_records(qs_vh, 'dien')
    process_records(qs_tram, 'tram')

    aligned_data = all_aligned_data.get(target_date, {})
    if not aligned_data:
        return f"Không tìm thấy dữ liệu vận hành cho thiết bị {device_ten_clean} ({device_code}) vào ngày {target_date.strftime('%d/%m/%Y')}."

    # Xác định mã tham số công suất và nhiệt độ nước vào sớm để phục vụ lọc
    power_code = None
    t_inlet_code = None
    for code, meta in param_meta.items():
        metric_code = meta.get('metric_code') or code
        if "cong_suat_tac_dung" in metric_code or "cong_suat_thuc" in metric_code or metric_code == "P":
            power_code = code
        elif "nhiet_do_nuoc_lam_mat_vao" in metric_code or "nhiet_do_moi_truong" in metric_code or "nhiet_do_gio_vao" in metric_code:
            t_inlet_code = code

    # Hàm phụ trợ tìm mã lưu lượng tương ứng với nhiệt độ (Bản đồ phụ thuộc)
    def get_related_flow_code(temp_code):
        t_lower = (param_meta.get(temp_code, {}).get('metric_code') or temp_code).lower()
        if "o_huong_tuabin" in t_lower or "o_huong_tb" in t_lower:
            for code_key, meta in param_meta.items():
                metric_code = (meta.get('metric_code') or code_key).lower()
                if "luu_luong_o_huong_tuabin" in metric_code or "luu_luong_o_huong_tb" in metric_code:
                    return code_key
        
        # Generator Guide Bearing (Ổ hướng máy phát)
        if "o_huong_may_phat" in t_lower or "o_huong_mp" in t_lower:
            for code_key, meta in param_meta.items():
                metric_code = (meta.get('metric_code') or code_key).lower()
                if "luu_luong_o_huong_may_phat" in metric_code or "luu_luong_o_huong_mp" in metric_code:
                    return code_key

        # Generator Thrust/Lower Guide Bearing (Ổ đỡ / Ổ đỡ hướng / Ổ hướng - ổ đỡ)
        if "o_do" in t_lower:
            for code_key, meta in param_meta.items():
                metric_code = (meta.get('metric_code') or code_key).lower()
                if "luu_luong_o_do" in metric_code:
                    return code_key

        if "chen_truc" in t_lower:
            for code_key, meta in param_meta.items():
                metric_code = (meta.get('metric_code') or code_key).lower()
                if "luu_luong_chen_truc" in metric_code:
                    return code_key
        return None

    def resolve_parameter_code(value):
        if not value:
            return None

        raw = value.strip()
        raw_norm = _normalize_text(raw)
        # Chuẩn hóa "số 1" -> "1", "số 2" -> "2"
        raw_norm = re.sub(r"\bso\s+(\d+)\b", r"\1", raw_norm)

        code_norms = {
            code: _normalize_text(" ".join([
                code,
                meta.get('device_code') or '',
                meta.get('metric_code') or '',
                meta.get('name') or '',
            ]))
            for code, meta in param_meta.items()
        }

        for code, meta in param_meta.items():
            metric_code = meta.get('metric_code') or code
            if raw == code or raw.lower() == code.lower() or raw.lower() == metric_code.lower():
                return code

        for code, code_norm in code_norms.items():
            if raw_norm and (raw_norm in code_norm or code_norm in raw_norm):
                return code

        is_temperature = "nhiet do" in raw_norm or raw_norm.startswith("nhiet")
        is_flow = "luu luong" in raw_norm or raw_norm.startswith("luu luong")
        mentions_turbine_guide = (
            "o huong tuabin" in raw_norm
            or "o huong turbine" in raw_norm
            or "o huong tuabine" in raw_norm
            or ("o huong" in raw_norm and any(token in raw_norm for token in ("tuabin", "turbine", "tuabine")))
        )

        preferred_codes = []
        if mentions_turbine_guide and is_temperature:
            preferred_codes = [
                "nhiet_do_o_huong_tuabin",
                "nhiet_do_o_huong_1_tuabin",
                "nhiet_do_o_huong_2_tuabin",
            ]
        elif mentions_turbine_guide and is_flow:
            preferred_codes = ["luu_luong_o_huong_tuabin"]
        elif is_temperature and any(token in raw_norm for token in ("cuon day", "stato", "stator", "loi sat")):
            if "loi sat" in raw_norm:
                if "1" in raw_norm:
                    preferred_codes = ["nhiet_do_loi_sat_stato_1"]
                elif "2" in raw_norm:
                    preferred_codes = ["nhiet_do_loi_sat_stato_2"]
                else:
                    preferred_codes = ["nhiet_do_loi_sat_stato_1", "nhiet_do_loi_sat_stato_2"]
            else:
                if "1" in raw_norm:
                    preferred_codes = ["nhiet_do_cuon_day_stato_1"]
                elif "2" in raw_norm:
                    preferred_codes = ["nhiet_do_cuon_day_stato_2"]
                else:
                    preferred_codes = [
                        "nhiet_do_cuon_day_stato_1",
                        "nhiet_do_cuon_day_stato_2",
                        "nhiet_do_cuon_day_stato"
                    ]

        for preferred in preferred_codes:
            for code, meta in param_meta.items():
                metric_code = meta.get('metric_code') or code
                if preferred in metric_code:
                    return code

        return None

    resolved_parameter_code = resolve_parameter_code(parameter_code)
    if resolved_parameter_code:
        parameter_code = resolved_parameter_code

    # Lọc bỏ các thông số hoàn toàn rỗng trong ngày và áp dụng parameter_code nếu có
    active_codes = set()
    for t_val, vals in aligned_data.items():
        for code, val in vals.items():
            if val is not None:
                active_codes.add(code)

    if parameter_code:
        # Kiểm tra xem có dữ liệu hoạt động cho tham số được yêu cầu không
        has_active_param = False
        for code in active_codes:
            meta = param_meta.get(code, {})
            metric_code = meta.get('metric_code') or code
            if parameter_code.lower() in code.lower() or parameter_code.lower() in metric_code.lower():
                has_active_param = True
                break
        if not has_active_param:
            return f"Không tìm thấy dữ liệu vận hành cho thông số '{parameter_code}' của thiết bị {device_ten_clean} ({device_code}) vào ngày {target_date.strftime('%d/%m/%Y')}."

    filtered_codes = None
    if parameter_code:
        related = {parameter_code}
        if power_code:
            related.add(power_code)
        if t_inlet_code:
            related.add(t_inlet_code)
            
        related_flow = get_related_flow_code(parameter_code)
        if related_flow:
            related.add(related_flow)
            
        for code_key in param_meta:
            metric_code = param_meta[code_key].get('metric_code') or code_key
            if "nhiet_do" in metric_code:
                if get_related_flow_code(code_key) == parameter_code:
                    related.add(code_key)
                    
        # Nếu parameter_code là chuỗi tìm kiếm chung (ví dụ "o_do"), ta giữ lại bất cứ mã nào chứa nó
        for code_key, meta in param_meta.items():
            metric_code = meta.get('metric_code') or code_key
            if parameter_code.lower() in code_key.lower() or parameter_code.lower() in metric_code.lower():
                related.add(code_key)
                rel_flow = get_related_flow_code(code_key)
                if rel_flow:
                    related.add(rel_flow)
                    
        filtered_codes = related
    else:
        filtered_codes = active_codes

    # Lọc param_meta
    param_meta = {c: m for c, m in param_meta.items() if c in filtered_codes}

    # Phân tích tham số window
    window_minutes = 60
    if window:
        m = re.match(r"(\d+)\s*(m|h|d|p)", window.strip().lower())
        if m:
            val = int(m.group(1))
            unit = m.group(2)
            if unit == "h":
                window_minutes = val * 60
            elif unit == "d":
                window_minutes = val * 1440
            else:
                window_minutes = val

    # Hàm chuyển đổi thời điểm thành datetime trên target_date để so sánh thời gian
    def to_dt(t_val):
        h, m = map(int, t_val.split(':'))
        return datetime.combine(target_date, datetime.min.time()) + timedelta(hours=h, minutes=m)

    def parse_time_label(value):
        if not value:
            return None
        normalized = value.strip()
        if len(normalized) == 4 and ':' in normalized:
            normalized = '0' + normalized
        try:
            datetime.strptime(normalized, '%H:%M')
        except ValueError:
            return None
        return normalized

    def times_having_any(codes):
        code_set = set(codes)
        return [
            t_val
            for t_val, vals in aligned_data.items()
            if any(vals.get(code_key) is not None for code_key in code_set)
        ]

    context_codes = {code for code in (power_code, t_inlet_code) if code}
    diagnostic_codes = [code for code in param_meta if code not in context_codes]
    if parameter_code:
        parameter_lower = parameter_code.lower()
        requested_codes = [code for code in param_meta if parameter_lower in code.lower()]
    else:
        requested_codes = []
    preferred_time_codes = requested_codes or diagnostic_codes or list(param_meta)

    # Nếu không chỉ định mốc thời gian cụ thể, ưu tiên mốc có dữ liệu chẩn đoán
    # thay vì mốc cuối toàn ngày. Tránh trường hợp mốc cuối chỉ có công suất,
    # làm nhiệt độ/lưu lượng liên quan bị N/A dù trong ngày có dữ liệu.
    time_str = time
    if not time_str:
        times = sorted(times_having_any(preferred_time_codes) or times_having_any(diagnostic_codes) or aligned_data.keys())
        if times:
            time_str = times[-1]

    if time_str:
        requested_time_str = parse_time_label(time_str)
        if not requested_time_str:
            return f"Mốc thời gian '{time_str}' không hợp lệ. Vui lòng dùng định dạng HH:MM, ví dụ 07:00."
            
        has_preferred_at_requested_time = (
            requested_time_str in aligned_data
            and any(aligned_data[requested_time_str].get(code_key) is not None for code_key in preferred_time_codes)
        )

        if requested_time_str not in aligned_data or (preferred_time_codes and not has_preferred_at_requested_time):
            # Chọn mốc thời gian gần nhất có dữ liệu chẩn đoán ưu tiên
            times = sorted(times_having_any(preferred_time_codes) or times_having_any(diagnostic_codes) or aligned_data.keys())
            if times:
                closest = min(times, key=lambda t: abs((to_dt(t) - to_dt(requested_time_str)).total_seconds()))
                time_str = closest
            else:
                return f"Không có dữ liệu tại mốc thời gian {requested_time_str} vào ngày {target_date}."
        else:
            time_str = requested_time_str

    # Tìm mốc thời gian lịch sử tương ứng với cửa sổ window
    prev_time_str = None
    if time_str:
        curr_dt = to_dt(time_str)
        target_prev_dt = curr_dt - timedelta(minutes=window_minutes)
        best_t_str = None
        best_diff = None
        for t_val in aligned_data.keys():
            dt = to_dt(t_val)
            diff = abs((dt - target_prev_dt).total_seconds()) / 60.0
            if diff <= 15.0: # Sai số tối đa 15 phút
                if best_diff is None or diff < best_diff:
                    best_diff = diff
                    best_t_str = t_val
        prev_time_str = best_t_str

    # Xác định công suất định mức
    factory_prefix = device_code.split('.')[0].upper() if '.' in device_code else device_code.upper()
    p_rated = RATED_POWER_MAP.get(factory_prefix, 37.0)

    curr_power = 0.0
    if time_str and power_code:
        curr_power = aligned_data[time_str].get(power_code, 0.0) or 0.0

    # Xác định xu hướng công suất
    power_trend = "stable"
    if time_str and prev_time_str and power_code:
        p_curr = aligned_data[time_str].get(power_code)
        p_prev = aligned_data[prev_time_str].get(power_code)
        if p_curr is not None and p_prev is not None:
            if p_curr - p_prev > 0.5:
                power_trend = "increasing"
            elif p_prev - p_curr > 0.5:
                power_trend = "decreasing"

    # Xác định chế độ vận hành
    op_mode_base = "offline"
    if curr_power > 30.0:
        op_mode_base = "high_load"
    elif curr_power > 10.0:
        op_mode_base = "medium_load"
    elif curr_power > 1.0:
        op_mode_base = "low_load"

    if power_trend != "stable" and op_mode_base != "offline":
        operating_mode = f"{op_mode_base}_transient"
    else:
        operating_mode = f"{op_mode_base}_stable"

    # Nhiệt độ nước làm mát vào
    t_inlet = 25.0
    if time_str and t_inlet_code:
        t_inlet = aligned_data[time_str].get(t_inlet_code, 25.0) or 25.0

    # Xây dựng cấu trúc Markdown phản hồi
    device_label = "Tổ máy" if re.search(r"\.H[12](\.|$)", device_code.upper()) else "Thiết bị"
    lines = []
    lines.append(f"### Hồ sơ trạng thái vận hành {device_label}: {device_ten_clean} ({device_code})")
    lines.append(f"- **Ngày báo cáo**: {target_date.strftime('%d/%m/%Y')}")
    lines.append(f"- **Khoảng so sánh**: {comparison_start_date.strftime('%d/%m/%Y')} đến {target_date.strftime('%d/%m/%Y')} ({comparison_days} ngày)")
    if time_str:
        lines.append(f"- **Mốc thời gian chẩn đoán**: {time_str} (Giờ địa phương)")
        lines.append(f"- **Cửa sổ thời gian so sánh**: {window_minutes} phút (so với {prev_time_str or 'không có dữ liệu'})")
        lines.append(f"- **Chế độ vận hành hiện tại**: `{operating_mode}` (Tải hiện tại: {curr_power:.2f} MW)")
    lines.append("")

    # Bảng 1: Ngưỡng thông số
    lines.append("#### 1. Ngưỡng giới hạn của các thông số giám sát")
    lines.append("| Tên thông số | Mã thông số | Mã thiết bị | Thiết bị thành phần | Nhà máy | Định mức (Rated) | Cảnh báo (Alarm) | Sự cố (Trip) | Đơn vị |")
    lines.append("|---|---|---|---|---|---:|---:|---:|---|")
    for code, meta in sorted(param_meta.items(), key=lambda x: x[0]):
        lines.append(
            f"| {meta['name']} | `{meta.get('metric_code') or code}` | `{meta.get('device_code') or '-'}` | {meta['device_name']} | {meta.get('factory') or '-'} | "
            f"{meta['rated'] if meta['rated'] is not None else '-'} | "
            f"{meta['alarm'] if meta['alarm'] is not None else '-'} | "
            f"{meta['trip'] if meta['trip'] is not None else '-'} | "
            f"{meta['unit']} |"
        )
    lines.append("")

    # Bảng 2: Dữ liệu vận hành & Chẩn đoán chi tiết
    signals_json = {}
    time_values = aligned_data.get(time_str, {}) if time_str else {}
    prev_values = aligned_data.get(prev_time_str, {}) if prev_time_str else {}

    if time_str:
        lines.append("#### 2. Dữ liệu vận hành & Chẩn đoán chuyên sâu")
        lines.append("| Tên thông số | Giá trị thực tế | Kỳ vọng (Expected) | Sai lệch (Residual) | Xu hướng | Tốc độ thay đổi | Chất lượng | Trạng thái |")
        lines.append("|---|---:|---:|---:|---|---|---|---|")
        
        for code, meta in sorted(param_meta.items(), key=lambda x: x[0]):
            metric_code = meta.get('metric_code') or code
            val = time_values.get(code)
            val_prev = prev_values.get(code)
            
            # Đánh giá chất lượng cảm biến
            quality = "good"
            if val is None:
                quality = "missing"
            elif meta['unit'] == "°C" and (val < 0.0 or val > 150.0):
                quality = "bad"
            elif meta['unit'] == "MW" and (val < -5.0 or val > 100.0):
                quality = "bad"
            elif meta['unit'] == "l/p" and (val < 0.0 or val > 10000.0):
                quality = "bad"

            # Tính tốc độ thay đổi và xu hướng
            rate_of_change = None
            trend = "stable"
            if val is not None and val_prev is not None:
                delta_val = val - val_prev
                delta_t = (to_dt(time_str) - to_dt(prev_time_str)).total_seconds() / 60.0
                if delta_t > 0:
                    rate_of_change = delta_val / delta_t
                
                epsilon = 0.1
                if "cong_suat" in metric_code or meta['unit'] == "MW":
                    epsilon = 0.5
                elif "luu_luong" in metric_code or meta['unit'] == "l/p":
                    epsilon = 0.5
                
                if delta_val > epsilon:
                    trend = "increasing"
                elif delta_val < -epsilon:
                    trend = "decreasing"

            # Tính giá trị kỳ vọng & Residual
            expected = None
            residual = None
            if val is not None and meta['unit'] == "°C" and "nhiet_do" in metric_code:
                if curr_power < 1.0:
                    expected = t_inlet
                else:
                    flow_code = get_related_flow_code(code)
                    f_val = time_values.get(flow_code) if flow_code else None
                    f_rated = 50.0
                    if flow_code and flow_code in param_meta:
                        f_rated = param_meta[flow_code].get("rated") or 50.0
                    
                    t_rated_temp = meta['rated'] or 65.0
                    if "cuon_day" in metric_code or "stato" in metric_code:
                        t_rated_temp = meta['rated'] or 85.0
                    
                    p_ratio = curr_power / p_rated
                    f_term = 1.0
                    if f_val is not None and f_val > 0.0:
                        f_term = (f_rated / f_val) ** 0.5
                    
                    expected = t_inlet + (t_rated_temp - t_inlet) * (0.4 + 0.6 * (p_ratio ** 2)) * f_term
                    expected = max(t_inlet, min(expected, t_rated_temp + 5.0))
                residual = val - expected

            # Tính trạng thái giới hạn cứng
            status = "Bình thường"
            alarm = meta['alarm']
            trip = meta['trip']
            rated = meta['rated']
            
            is_low_limit = False
            is_flow = "luu_luong" in metric_code or meta['unit'].lower() == "l/p"
            is_pressure = "ap_luc" in metric_code or "ap_suat" in metric_code or meta['unit'].lower() in ("bar", "mpa")
            if is_flow or is_pressure:
                is_low_limit = True
            if alarm is not None and trip is not None:
                is_low_limit = trip < alarm
            elif rated is not None:
                if alarm is not None:
                    is_low_limit = alarm < rated
                elif trip is not None:
                    is_low_limit = trip < rated

            alarm_margin = None
            trip_margin = None
            if val is not None:
                if alarm is not None:
                    alarm_margin = (val - alarm) if is_low_limit else (alarm - val)
                if trip is not None:
                    trip_margin = (val - trip) if is_low_limit else (trip - val)

                if trip is not None:
                    if (is_low_limit and val <= trip) or (not is_low_limit and val >= trip):
                        status = "🔴 SỰ CỐ (TRIP)"
                if status == "Bình thường" and alarm is not None:
                    margin_tol = abs(alarm - (rated or alarm * 0.9)) * 0.2 if rated is not None else (alarm * 0.02)
                    if is_low_limit:
                        if val <= alarm:
                            status = "🚨 CẢNH BÁO (ALARM)"
                        elif val <= alarm + margin_tol:
                            status = "⚠️ TIỆM CẬN ALARM (NEAR ALARM)"
                    else:
                        if val >= alarm:
                            status = "🚨 CẢNH BÁO (ALARM)"
                        elif val >= alarm - margin_tol:
                            status = "⚠️ TIỆM CẬN ALARM (NEAR ALARM)"

            # Lưu vào JSON
            signals_json[code] = {
                "device_code": meta.get('device_code'),
                "device_name": meta.get('device_name'),
                "metric_code": metric_code,
                "name": meta.get('name'),
                "source": meta.get('source'),
                "factory": meta.get('factory'),
                "val": val,
                "unit": meta['unit'],
                "alarm": alarm,
                "trip": trip,
                "rated": rated,
                "expected": round(expected, 2) if expected is not None else None,
                "residual": round(residual, 2) if residual is not None else None,
                "rate_of_change": round(rate_of_change, 3) if rate_of_change is not None else None,
                "trend": trend,
                "quality": quality,
                "alarm_margin": round(alarm_margin, 2) if alarm_margin is not None else None,
                "trip_margin": round(trip_margin, 2) if trip_margin is not None else None,
                "status": status
            }

            # Định dạng cột hiển thị
            val_display = f"**{val:.2f} {meta['unit']}**" if val is not None else "N/A"
            expected_display = f"{expected:.2f} °C" if expected is not None else "-"
            residual_display = f"{residual:+.2f} °C" if residual is not None else "-"
            
            trend_display = "➖ Ổn định"
            if trend == "increasing":
                trend_display = "📈 Tăng"
            elif trend == "decreasing":
                trend_display = "📉 Giảm"
                
            rate_display = f"{rate_of_change:+.3f} {meta['unit']}/phút" if rate_of_change is not None else "-"
            
            quality_display = "🟢 Tốt"
            if quality == "bad":
                quality_display = "🔴 Lỗi"
            elif quality == "missing":
                quality_display = "⚪ Thiếu"

            lines.append(
                f"| {meta['name']} ({meta['device_name']}) | {val_display} | "
                f"{expected_display} | {residual_display} | {trend_display} | "
                f"{rate_display} | {quality_display} | {status} |"
            )
            
    # Bảng 3: Dữ liệu vận hành trong các ngày so sánh
    lines.append("")
    lines.append("#### 3. Bảng diễn biến thông số trong các ngày so sánh")
    
    power_code_daily = None
    stator_temp_code_daily = None
    bearing_temp_code_daily = None
    shaft_seal_flow_code_daily = None
    turbine_flow_code_daily = None
    
    for code, meta in param_meta.items():
        metric_code = meta.get('metric_code') or code
        if "cong_suat_tac_dung" in metric_code:
            power_code_daily = code
        elif "nhiet_do_cuon_day_stato" in metric_code:
            stator_temp_code_daily = code
        elif "nhiet_do_o_do" in metric_code:
            bearing_temp_code_daily = code
        elif "luu_luong_chen_truc" in metric_code:
            shaft_seal_flow_code_daily = code
        elif "luu_luong_o_huong_tuabin" in metric_code:
            turbine_flow_code_daily = code
            
    headers = ["Ngày", "Mốc giờ"]
    col_codes = []
    col_labels = {}
    
    def add_col(code, label):
        if code and code not in col_codes:
            headers.append(label)
            col_codes.append(code)
            col_labels[code] = label
            
    add_col(power_code_daily, "Công suất (MW)")
    add_col(bearing_temp_code_daily, "Nhiệt độ ổ đỡ (°C)")
    add_col(stator_temp_code_daily, "Nhiệt độ Stato (°C)")
    add_col(shaft_seal_flow_code_daily, "Lưu lượng chèn trục (l/p)")
    add_col(turbine_flow_code_daily, "Lưu lượng ổ hướng TB (l/p)")

    for code, meta in sorted(param_meta.items()):
        metric_code = meta.get('metric_code') or code
        if code in col_codes:
            continue
        if "nhiet_do" in metric_code or "luu_luong" in metric_code:
            unit_suffix = f" ({meta['unit']})" if meta['unit'] else ""
            add_col(code, f"{meta['name']}{unit_suffix}")
    
    if len(col_codes) == 0:
        for code, meta in list(sorted(param_meta.items()))[:5]:
            unit_suffix = f" ({meta['unit']})" if meta['unit'] else ""
            add_col(code, f"{meta['name']}{unit_suffix}")
            
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---:"] * len(headers)) + " |")

    comparison_rows = []
    for offset in range(comparison_days):
        day = comparison_start_date + timedelta(days=offset)
        day_data = all_aligned_data.get(day, {})
        for day_time in sorted(day_data.keys()):
            row_vals = day_data[day_time]
            if not any(row_vals.get(code) is not None for code in col_codes):
                continue

            row = {
                "day": day,
                "time": day_time,
                "values": {code: row_vals.get(code) for code in col_codes},
            }
            comparison_rows.append(row)

            row_line = [f"**{day.strftime('%d/%m')}**", day_time]
            for c_code in col_codes:
                val = row_vals.get(c_code)
                row_line.append(f"{val:.2f}" if val is not None else "-")
            lines.append("| " + " | ".join(row_line) + " |")

    unit_groups = {}
    for code in col_codes:
        unit = param_meta.get(code, {}).get('unit') or ''
        unit_groups.setdefault(unit, []).append(code)

    chart_colors = ["#2563eb", "#dc2626", "#059669", "#9333ea", "#ea580c", "#0891b2", "#64748b"]
    for unit, codes in unit_groups.items():
        y_keys = [col_labels.get(code, code) for code in codes]
        chart_rows = []
        for row in comparison_rows:
            item = {"Thời điểm": f"{row['day'].strftime('%d/%m')} {row['time']}"}
            has_value = False
            for code in codes:
                val = row["values"].get(code)
                if val is not None:
                    item[col_labels.get(code, code)] = round(val, 2)
                    has_value = True
            if has_value:
                chart_rows.append(item)

        if chart_rows:
            chart_json = {
                "type": "line",
                "title": f"Biểu đồ so sánh 15 ngày - {unit or 'thông số vận hành'}",
                "data": chart_rows,
                "xKey": "Thời điểm",
                "yKeys": y_keys,
                "colors": chart_colors[:len(y_keys)],
                "unit": f" {unit}" if unit else ""
            }
            lines.append("")
            lines.append(f"```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```")

    # Thêm JSON Payload ẩn cho AI Agent đọc trực tiếp
    json_payload = {
        "timestamp": to_dt(time_str).isoformat() if time_str else None,
        "device_code": device_code,
        "device_name": device_ten_clean,
        "operating_mode": operating_mode,
        "analysis_window": f"{window_minutes}m",
        "comparison_window": {
            "start_date": comparison_start_date.isoformat(),
            "end_date": target_date.isoformat(),
            "days": comparison_days,
        },
        "signals": signals_json
    }
    
    lines.append("")
    lines.append(f"<!-- NAMI_THERMO_DATA_START\n{json.dumps(json_payload, ensure_ascii=False, indent=2)}\nNAMI_THERMO_DATA_END -->")

    return "\n".join(lines)
