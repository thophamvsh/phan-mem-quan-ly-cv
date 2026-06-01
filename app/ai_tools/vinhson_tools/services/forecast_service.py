"""
Forecast service - Dự báo Qve và Sản lượng cho tháng/năm tới cho Vĩnh Sơn.
Áp dụng phương pháp từ Sông Hinh với 3 hồ A, B, C.
Lấy dữ liệu Qve từ spreadsheet_id (sheet vận hành).
"""

from __future__ import annotations

from datetime import date
from typing import Optional, List, Tuple, Dict
import calendar
import json

from ..config.settings import GS_CONFIG
from ..config.columns import COL_DATE, COL_OUTPUT_DAY
from ..core.stats_export_client import get_stats_export_client
from ..core.retry import retry_with_backoff
from ..utils.dates import normalize_date
from ..utils.numbers import parse_number, parse_number_for_qve


# Sheet Thống kê (0-based) - Vĩnh Sơn
# Cột Qve cho 3 hồ: E(4)=Hồ A, F(5)=Hồ B, G(6)=Hồ C
COL_DATE_STATS = 0
COL_QVE_A, COL_QVE_B, COL_QVE_C = 4, 5, 6


def _cell(row: list, i: int) -> str:
    return row[i] if i < len(row) else ""


def _date_from_stats_row(row: list) -> Optional[date]:
    for col in (0, COL_DATE_STATS):
        if col >= len(row):
            continue
        raw = str(_cell(row, col)).strip()
        if not raw:
            continue
        d = normalize_date(raw)
        if d:
            return d
    return None


def pick_stats_worksheet(spreadsheet, prefer_sheet_name=None):
    """Tìm worksheet trong spreadsheet."""
    worksheets = spreadsheet.worksheets()
    if prefer_sheet_name:
        for ws in worksheets:
            if prefer_sheet_name in ws.title:
                return ws
    return worksheets[0] if worksheets else None


def find_data_start_row(all_data: List[List[str]]) -> int:
    """Tìm dòng bắt đầu dữ liệu thực (bỏ qua header)."""
    for i, row in enumerate(all_data[:50]):
        if not row:
            continue
        for date_col in (COL_DATE_STATS, COL_DATE):
            cell_str = str(row[date_col]).strip() if date_col < len(row) else ""
            if '/' in cell_str and any(c.isdigit() for c in cell_str):
                parts = cell_str.split('/')
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    return i
    return 7 if len(all_data) > 7 else 1


def get_month_data(rows: List[list], year: int, month: int, col_qve: int) -> Optional[float]:
    """Lấy dữ liệu Qve trung bình tháng từ sheet Thống kê."""
    vals: List[float] = []
    for r in rows:
        dt = _date_from_stats_row(r)
        if dt and dt.year == year and dt.month == month:
            val_str = _cell(r, col_qve)
            v = parse_number_for_qve(val_str)
            if v is not None:
                vals.append(v)
    if vals:
        return sum(vals) / len(vals)
    return None


def get_month_data_all_reservoirs(rows: List[list], year: int, month: int) -> Dict[str, float]:
    """Lấy dữ liệu Qve cho tất cả 3 hồ A, B, C."""
    result = {}
    for res_label, col_qve in [("Hồ A", COL_QVE_A), ("Hồ B", COL_QVE_B), ("Hồ C", COL_QVE_C)]:
        qve = get_month_data(rows, year, month, col_qve)
        if qve is not None:
            result[res_label] = qve
    return result


def get_year_data_all_reservoirs(rows: List[list], year: int) -> Dict[str, float]:
    result = {}
    for res_label, col_qve in [("Hồ A", COL_QVE_A), ("Hồ B", COL_QVE_B), ("Hồ C", COL_QVE_C)]:
        vals: List[float] = []
        for row in rows:
            dt = _date_from_stats_row(row)
            if dt and dt.year == year:
                value = parse_number_for_qve(_cell(row, col_qve))
                if value is not None:
                    vals.append(value)
        if vals:
            result[res_label] = sum(vals) / len(vals)
    return result


def get_output_month(year: int, month: int) -> Optional[float]:
    """Lấy sản lượng điện thương phẩm tháng từ sheet Sản lượng."""
    try:
        _, spreadsheet = get_stats_export_client(GS_CONFIG.spreadsheet_id)
        if not spreadsheet:
            return None

        worksheets = spreadsheet.worksheets()
        op_ws = None
        for ws in worksheets:
            if "Sản lượng" in ws.title:
                op_ws = ws
                break
        op_ws = op_ws or (worksheets[0] if worksheets else None)
        if not op_ws:
            return None

        all_data = op_ws.get_all_values()
        data_start_row = find_data_start_row(all_data)
        data_rows = all_data[data_start_row:] if data_start_row < len(all_data) else []

        total_output = 0.0
        for row in data_rows:
            if len(row) <= COL_DATE:
                continue
            raw = str(row[COL_DATE]).strip()
            dt = normalize_date(raw)
            if dt and dt.year == year and dt.month == month:
                if len(row) > COL_OUTPUT_DAY:
                    val = parse_number(_cell(row, COL_OUTPUT_DAY))
                    if val is not None:
                        total_output += val

        if total_output > 0:
            return total_output
    except Exception as e:
        print(f"[WARN] Lỗi lấy sản lượng: {e}")
    return None


def get_output_year(year: int) -> Optional[float]:
    try:
        _, spreadsheet = get_stats_export_client(GS_CONFIG.spreadsheet_id)
        if not spreadsheet:
            return None

        worksheets = spreadsheet.worksheets()
        op_ws = None
        for ws in worksheets:
            if "Sản lượng" in ws.title:
                op_ws = ws
                break
        op_ws = op_ws or (worksheets[0] if worksheets else None)
        if not op_ws:
            return None

        all_data = op_ws.get_all_values()
        data_start_row = find_data_start_row(all_data)
        data_rows = all_data[data_start_row:] if data_start_row < len(all_data) else []

        total_output = 0.0
        for row in data_rows:
            if len(row) <= COL_DATE:
                continue
            dt = normalize_date(str(row[COL_DATE]).strip())
            if dt and dt.year == year and len(row) > COL_OUTPUT_DAY:
                value = parse_number(_cell(row, COL_OUTPUT_DAY))
                if value is not None:
                    total_output += value

        if total_output > 0:
            return total_output
    except Exception as e:
        print(f"[WARN] Lỗi lấy sản lượng năm: {e}")
    return None


def get_daily_data_for_month_vinhson(year: int, month: int) -> Tuple[Dict[int, Dict[str, float]], Dict[int, float]]:
    """Lấy dữ liệu Qve cho từng hồ A, B, C và Sản lượng ngày.
    - Qve: từ stats_export_spreadsheet_id (sheet TV VS) - cột E, F, G (ngày ở cột A)
    - Sản lượng: từ spreadsheet_id (sheet Sản lượng) - cột M (ngày ở cột B)

    Trả về: (dict of {day: {res_label: qve}}, dict of {day: commercial_output})
    """
    # Lấy Qve từ stats_export_spreadsheet_id (sheet TV VS)
    _, spreadsheet_qve = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)

    qve_by_day: Dict[int, Dict[str, float]] = {}

    if spreadsheet_qve:
        worksheets = spreadsheet_qve.worksheets()
        # Tìm sheet TV VS (thường có tên chứa "TV" hoặc "VS" hoặc là sheet đầu tiên)
        stats_ws = None
        for ws in worksheets:
            title = ws.title.upper()
            if "TV" in title or "THỐNG KÊ" in title or "VS" in title or "202" in title:
                stats_ws = ws
                break
        stats_ws = stats_ws or (worksheets[0] if worksheets else None)
        if stats_ws:
            all_data = stats_ws.get_all_values()
            data_start = find_data_start_row(all_data)
            data_rows = all_data[data_start:] if data_start < len(all_data) else []

            for row in data_rows:
                # Sheet TV VS: ngày ở cột A (index 0)
                if len(row) <= 0:
                    continue
                cell_str = _cell(row, 0)
                dt = normalize_date(cell_str)
                if not dt or dt.year != year or dt.month != month:
                    continue

                day = dt.day

                if day not in qve_by_day:
                    qve_by_day[day] = {}

                # Lấy Qve của từng hồ A, B, C từ cột E, F, G (index 4, 5, 6)
                for res_label, col_qve in [("Hồ A", COL_QVE_A), ("Hồ B", COL_QVE_B), ("Hồ C", COL_QVE_C)]:
                    if len(row) > col_qve:
                        val = parse_number_for_qve(_cell(row, col_qve))
                        if val is not None:
                            qve_by_day[day][res_label] = val

    # Lấy Sản lượng từ spreadsheet_id (sheet Sản lượng)
    _, spreadsheet_output = get_stats_export_client(GS_CONFIG.spreadsheet_id)
    commercial_by_day: Dict[int, float] = {}

    if spreadsheet_output:
        worksheets = spreadsheet_output.worksheets()
        op_ws = None
        for ws in worksheets:
            if "Sản lượng" in ws.title:
                op_ws = ws
                break
        op_ws = op_ws or (worksheets[0] if worksheets else None)
        if op_ws:
            all_data = op_ws.get_all_values()
            data_start = find_data_start_row(all_data)
            data_rows = all_data[data_start:] if data_start < len(all_data) else []

            for row in data_rows:
                # Sheet Sản lượng: ngày ở cột B (COL_DATE = 1)
                if len(row) <= COL_DATE:
                    continue
                cell_str = _cell(row, COL_DATE)
                dt = normalize_date(cell_str)
    """Lấy dữ liệu Qve cho từng hồ A, B, C và Sản lượng ngày.
    - Qve: từ stats_export_spreadsheet_id (sheet TV VS) - cột E, F, G (ngày ở cột A)
    - Sản lượng: từ spreadsheet_id (sheet Sản lượng) - cột M (ngày ở cột B)

    Trả về: (dict of {day: {res_label: qve}}, dict of {day: commercial_output})
    """
    # Lấy Qve từ stats_export_spreadsheet_id (sheet TV VS)
    _, spreadsheet_qve = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)

    qve_by_day: Dict[int, Dict[str, float]] = {}

    if spreadsheet_qve:
        worksheets = spreadsheet_qve.worksheets()
        # Tìm sheet TV VS (thường có tên chứa "TV" hoặc "VS" hoặc là sheet đầu tiên)
        stats_ws = None
        for ws in worksheets:
            title = ws.title.upper()
            if "TV" in title or "THỐNG KÊ" in title or "VS" in title or "202" in title:
                stats_ws = ws
                break
        stats_ws = stats_ws or (worksheets[0] if worksheets else None)
        if stats_ws:
            all_data = stats_ws.get_all_values()
            data_start = find_data_start_row(all_data)
            data_rows = all_data[data_start:] if data_start < len(all_data) else []

            for row in data_rows:
                # Sheet TV VS: ngày ở cột A (index 0)
                if len(row) <= 0:
                    continue
                cell_str = _cell(row, 0)
                dt = normalize_date(cell_str)
                if not dt or dt.year != year or dt.month != month:
                    continue

                day = dt.day

                if day not in qve_by_day:
                    qve_by_day[day] = {}

                # Lấy Qve của từng hồ A, B, C từ cột E, F, G (index 4, 5, 6)
                for res_label, col_qve in [("Hồ A", COL_QVE_A), ("Hồ B", COL_QVE_B), ("Hồ C", COL_QVE_C)]:
                    if len(row) > col_qve:
                        val = parse_number_for_qve(_cell(row, col_qve))
                        if val is not None:
                            qve_by_day[day][res_label] = val

    # Lấy Sản lượng từ spreadsheet_id (sheet Sản lượng)
    _, spreadsheet_output = get_stats_export_client(GS_CONFIG.spreadsheet_id)
    commercial_by_day: Dict[int, float] = {}

    if spreadsheet_output:
        worksheets = spreadsheet_output.worksheets()
        op_ws = None
        for ws in worksheets:
            if "Sản lượng" in ws.title:
                op_ws = ws
                break
        op_ws = op_ws or (worksheets[0] if worksheets else None)
        if op_ws:
            all_data = op_ws.get_all_values()
            data_start = find_data_start_row(all_data)
            data_rows = all_data[data_start:] if data_start < len(all_data) else []

            for row in data_rows:
                # Sheet Sản lượng: ngày ở cột B (COL_DATE = 1)
                if len(row) <= COL_DATE:
                    continue
                cell_str = _cell(row, COL_DATE)
                dt = normalize_date(cell_str)
                if not dt or dt.year != year or dt.month != month:
                    continue

                day = dt.day

                # Lấy Sản lượng đầu cực ngày (cột M)
                if len(row) > COL_OUTPUT_DAY:
                    val = parse_number(_cell(row, COL_OUTPUT_DAY))
                    if val is not None:
                        commercial_by_day[day] = commercial_by_day.get(day, 0.0) + val

    return qve_by_day, commercial_by_day


class ForecastService:
    """Service dự báo Qve và Sản lượng cho Vĩnh Sơn với 3 hồ A, B, C."""

    def __init__(self):
        pass

    def forecast_month(self, target_month: int, target_year: int, reservoir: str = "All") -> str:
        """Dự báo Qve và Sản lượng cho tháng - hiển thị 3 cột cho hồ A, B, C.

        Args:
            target_month: Tháng dự báo
            target_year: Năm dự báo
            reservoir: Tham số giữ lại để tương thích (hiện tại luôn dự báo cho cả 3 hồ)
        """
        try:
            # Xác định tháng trước để so sánh (tháng M-1)
            if target_month == 1:
                compare_month = 12
            else:
                compare_month = target_month - 1

            # Lấy Qve từ stats_export_spreadsheet_id (sheet TV VS)
            _, spreadsheet_stats = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet_stats:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối với sheet TV VS."

            stats_ws = pick_stats_worksheet(spreadsheet_stats)
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet TV VS."

            all_data = retry_with_backoff(stats_ws.get_all_values, max_retries=3, initial_delay=1)
            if not all_data or len(all_data) < 2:
                return "Không có dữ liệu."

            data_start = find_data_start_row(all_data)
            rows = all_data[data_start:] if data_start < len(all_data) else []

            years_to_check = [target_year - 1, target_year - 2, target_year - 3]
            res_labels = ["Hồ A", "Hồ B", "Hồ C"]

            # Lấy Qve của từng hồ cho các năm liền kề
            qve_data_by_year: Dict[int, Dict[str, float]] = {}
            for yr in years_to_check:
                year_qve_values = get_month_data_all_reservoirs(rows, yr, compare_month)
                if year_qve_values:
                    qve_data_by_year[yr] = year_qve_values

            if not qve_data_by_year:
                return f"### Không đủ dữ liệu\n\nKhông có dữ liệu Qve tháng {compare_month} của các năm liền kề để dự báo."

            # Lấy Qve tháng trước của năm hiện tại
            current_qve_by_res = get_month_data_all_reservoirs(rows, target_year, compare_month)
            # Tính tổng Qve của 3 hồ cho từng năm làm cơ sở so sánh tương đồng
            qve_data: List[Tuple[int, float]] = []
            for yr, year_qve_values in qve_data_by_year.items():
                sum_qve_for_year = sum(year_qve_values.values())
                qve_data.append((yr, sum_qve_for_year))

            current_month_qve = sum(current_qve_by_res.values()) if current_qve_by_res else None

            # Tính trung bình tổng Qve của các năm qua
            avg_qve = sum([q for _, q in qve_data]) / len(qve_data)

            # Tính trung bình Qve của từng hồ qua các năm để hiển thị
            avg_qve_by_res: Dict[str, float] = {}
            for res_label in res_labels:
                vals = [year_qve.get(res_label, 0) for year_qve in qve_data_by_year.values() if res_label in year_qve]
                if vals:
                    avg_qve_by_res[res_label] = sum(vals) / len(vals)

            # Chọn năm tương đồng nhất
            if current_month_qve is not None:
                closest_year = min(qve_data, key=lambda x: abs(x[1] - current_month_qve))[0]
                compare_value = current_month_qve
                compare_label = f"Tổng Qve tháng {compare_month}/{target_year}"
            else:
                closest_year = min(qve_data, key=lambda x: abs(x[1] - avg_qve))[0]
                compare_value = avg_qve
                compare_label = "Tổng Qve trung bình"

            # ===== LẤY DỮ LIỆU TỪNG NGÀY VÀ TÍCH HỢP THỜI TIẾT =====
            from ai_tools.water_tools.weather_service import (
                get_rainfall_forecast,
                get_reservoir_useful_capacity,
                get_reservoir_max_useful_capacity,
                get_initial_levels_and_volumes,
                get_daily_rainfall_history,
                get_monthly_rainfall
            )

            # Lấy dự báo thời tiết cho Vĩnh Sơn
            rainfall_forecast = get_rainfall_forecast(lat=14.365095, lon=108.694488)

            # Lấy mực nước & dung tích đầu kỳ
            init_data = get_initial_levels_and_volumes('vinhson', target_year, target_month)
            H_dau_A, V_dau_A = init_data.get('vinhson_a', (770.0, 1.0))
            H_dau_B, V_dau_B = init_data.get('vinhson_b', (820.0, 5.0))
            H_dau_C, V_dau_C = init_data.get('vinhson_c', (976.0, 2.5))

            # Tính lượng mưa tháng trước để xác định độ ẩm đất và hệ số hiệu chỉnh lưu lượng về (soil moisture scaling)
            compare_year = target_year - 1 if target_month == 1 else target_year
            compare_year_analog = closest_year - 1 if target_month == 1 else closest_year
            
            R_cur = get_monthly_rainfall('vinhson', compare_year, compare_month)
            R_ana = get_monthly_rainfall('vinhson', compare_year_analog, compare_month)
            
            ratio = R_cur / R_ana if R_ana > 0.0 else 1.0
            wetness_factor = 1.0 + (ratio - 1.0) * 0.2
            wetness_factor = max(0.8, min(1.3, wetness_factor))

            qve_by_day, commercial_by_day = get_daily_data_for_month_vinhson(closest_year, target_month)
            analog_daily_rain = get_daily_rainfall_history('vinhson', closest_year, target_month)

            # Tính toán giá trị từ dữ liệu hàng ngày
            total_commercial = 0.0
            qve_values_a, qve_values_b, qve_values_c = [], [], []
            forecast_chart_data = []
            forecast_excel_rows = [[
                "Ngay",
                "Qve Ho A (m3/s)",
                "Qve Ho B (m3/s)",
                "Qve Ho C (m3/s)",
                f"Luong mua lich su {closest_year} (mm)",
                "Du bao luong mua (mm)",
                "San luong dau cuc (kWh)",
            ]]

            import calendar
            last_day_forecast = calendar.monthrange(target_year, target_month)[1]

            # Tạo bảng dữ liệu từng ngày
            table_rows = ""
            for day in range(1, last_day_forecast + 1):
                day_qve_dict = qve_by_day.get(day, {})
                commercial_val = commercial_by_day.get(day, "-")

                qve_a = day_qve_dict.get("Hồ A", "-")
                qve_b = day_qve_dict.get("Hồ B", "-")
                qve_c = day_qve_dict.get("Hồ C", "-")

                if qve_a == "-" and qve_b == "-" and qve_c == "-" and commercial_val == "-":
                    continue

                # Dự báo lượng mưa
                date_str = f"{target_year}-{target_month:02d}-{day:02d}"
                rain_val = rainfall_forecast.get(date_str, 0.0)
                rain_display = f"{rain_val:.1f}" if date_str in rainfall_forecast else "-"

                # Lấy lượng mưa lịch sử của ngày này ở năm tương đồng
                hist_rain_val = analog_daily_rain.get(day, 0.0)
                hist_rain_display = f"{hist_rain_val:.1f}"

                # Hiệu chỉnh Qve dựa trên hệ số độ ẩm đất và lượng mưa dự báo
                factor = 1.0
                if rain_val >= 35.0:
                    factor = 2.0
                elif rain_val >= 15.0:
                    factor = 1.5
                elif rain_val >= 5.0:
                    factor = 1.2

                if isinstance(qve_a, (int, float)):
                    qve_a = qve_a * wetness_factor * factor
                    qve_values_a.append(qve_a)
                if isinstance(qve_b, (int, float)):
                    qve_b = qve_b * wetness_factor * factor
                    qve_values_b.append(qve_b)
                if isinstance(qve_c, (int, float)):
                    qve_c = qve_c * wetness_factor * factor
                    qve_values_c.append(qve_c)

                if isinstance(commercial_val, (int, float)):
                    total_commercial += commercial_val

                day_display = f"{day}/{target_month}/{target_year}"
                qve_a_str = f"{qve_a:.2f}" if isinstance(qve_a, (int, float)) else "-"
                qve_b_str = f"{qve_b:.2f}" if isinstance(qve_b, (int, float)) else "-"
                qve_c_str = f"{qve_c:.2f}" if isinstance(qve_c, (int, float)) else "-"
                commercial_str = f"{commercial_val:,.0f}" if isinstance(commercial_val, (int, float)) else "-"

                table_rows += f"| {day_display} | {qve_a_str} | {qve_b_str} | {qve_c_str} | {hist_rain_display} | {rain_display} | {commercial_str} |\n"
                forecast_excel_rows.append([
                    day_display,
                    round(qve_a, 2) if isinstance(qve_a, (int, float)) else None,
                    round(qve_b, 2) if isinstance(qve_b, (int, float)) else None,
                    round(qve_c, 2) if isinstance(qve_c, (int, float)) else None,
                    round(hist_rain_val, 1),
                    round(rain_val, 1) if date_str in rainfall_forecast else None,
                    round(commercial_val, 0) if isinstance(commercial_val, (int, float)) else None,
                ])

                forecast_chart_data.append({
                    "Ngay": f"{day}/{target_month}",
                    "QveHoA": round(qve_a, 2) if isinstance(qve_a, (int, float)) else 0.0,
                    "QveHoB": round(qve_b, 2) if isinstance(qve_b, (int, float)) else 0.0,
                    "QveHoC": round(qve_c, 2) if isinstance(qve_c, (int, float)) else 0.0,
                    "SanLuong": round(commercial_val, 0) if isinstance(commercial_val, (int, float)) else 0.0,
                })

            # Tính trung bình từng hồ từ dữ liệu hàng ngày
            avg_a = sum(qve_values_a) / len(qve_values_a) if qve_values_a else 0.0
            avg_b = sum(qve_values_b) / len(qve_values_b) if qve_values_b else 0.0
            avg_c = sum(qve_values_c) / len(qve_values_c) if qve_values_c else 0.0

            # Tính toán cân bằng nước cho Vĩnh Sơn
            STH = 0.69
            Total_Time = 86400
            total_V_phat = (total_commercial * STH) / 1000000 # triệu m3
            
            # Thể tích nước về cho từng hồ
            total_V_ve_a = (sum(qve_values_a) * Total_Time) / 1000000 if qve_values_a else 0.0
            total_V_ve_b = (sum(qve_values_b) * Total_Time) / 1000000 if qve_values_b else 0.0
            total_V_ve_c = (sum(qve_values_c) * Total_Time) / 1000000 if qve_values_c else 0.0

            # Tính toán cuối kỳ
            V_cuoi_A = V_dau_A + total_V_ve_a - total_V_phat
            V_cuoi_B = V_dau_B + total_V_ve_b
            V_cuoi_C = V_dau_C + total_V_ve_c

            V_max_A = get_reservoir_max_useful_capacity('vinhson_a')
            V_max_B = get_reservoir_max_useful_capacity('vinhson_b')
            V_max_C = get_reservoir_max_useful_capacity('vinhson_c')

            # Cảnh báo
            V_trong_A = max(V_max_A - V_dau_A, 0.0)
            V_trong_B = max(V_max_B - V_dau_B, 0.0)
            V_trong_C = max(V_max_C - V_dau_C, 0.0)
            V_nguon_A = max(V_dau_A + total_V_ve_a, 0.0)
            V_nguon_B = max(V_dau_B + total_V_ve_b, 0.0)
            V_nguon_C = max(V_dau_C + total_V_ve_c, 0.0)
            V_nguon_he_thong = V_nguon_A + V_nguon_B + V_nguon_C
            V_thieu_A = max(total_V_phat - V_nguon_A, 0.0)
            V_du_A = max(V_nguon_A - total_V_phat, 0.0)
            V_dieu_tiet_B = min(V_thieu_A, V_nguon_B)
            V_con_thieu_sau_B = max(V_thieu_A - V_dieu_tiet_B, 0.0)
            V_dieu_tiet_C = min(V_con_thieu_sau_B, V_nguon_C)
            V_con_thieu_he_thong = max(V_thieu_A - V_dieu_tiet_B - V_dieu_tiet_C, 0.0)
            du_nuoc_ho_a = V_thieu_A <= 0.0
            du_nuoc_he_thong = V_nguon_he_thong >= total_V_phat
            if du_nuoc_ho_a:
                dieu_tiet_recommendation = (
                    f"Hồ A đủ nước cho sản lượng dự báo, không cần bổ sung bắt buộc từ hồ B/C. "
                    f"Có thể điều tiết B/C theo yêu cầu duy trì MNH vận hành và tránh đầy hồ."
                )
            elif du_nuoc_he_thong:
                dieu_tiet_recommendation = (
                    f"Hồ A thiếu khoảng **{V_thieu_A:.2f} triệu m3** so với nhu cầu phát điện. "
                    f"Ưu tiên điều tiết từ hồ B khoảng **{V_dieu_tiet_B:.2f} triệu m3**, "
                    f"sau đó từ hồ C khoảng **{V_dieu_tiet_C:.2f} triệu m3** về hồ A để đảm bảo sản lượng dự báo."
                )
            else:
                dieu_tiet_recommendation = (
                    f"Tổng nguồn nước ước tính toàn hệ thống vẫn thiếu khoảng **{V_con_thieu_he_thong:.2f} triệu m3** "
                    f"sau khi huy động hồ B/C. Cần giảm sản lượng kế hoạch hoặc cập nhật lại dự báo nước về."
                )

            water_balance_excel_rows = [
                [
                    "Ho",
                    "MNH hien tai (m)",
                    "Dung tich hien co (trieu m3)",
                    "Dung tich con trong (trieu m3)",
                    "Nuoc ve du bao (trieu m3)",
                    "Dung tich cuoi ky (trieu m3)",
                ],
                ["Ho A", round(H_dau_A, 2), round(V_dau_A, 2), round(V_trong_A, 2), round(total_V_ve_a, 2), round(V_cuoi_A, 2)],
                ["Ho B", round(H_dau_B, 2), round(V_dau_B, 2), round(V_trong_B, 2), round(total_V_ve_b, 2), round(V_cuoi_B, 2)],
                ["Ho C", round(H_dau_C, 2), round(V_dau_C, 2), round(V_trong_C, 2), round(total_V_ve_c, 2), round(V_cuoi_C, 2)],
                [],
                ["Tong nuoc can phat dien (trieu m3)", round(total_V_phat, 2)],
                ["Nguon nuoc rieng ho A (trieu m3)", round(V_nguon_A, 2)],
                ["Ho A du/thieu sau phat (trieu m3)", round(V_du_A - V_thieu_A, 2)],
                ["Dieu tiet uoc tinh tu ho B ve A (trieu m3)", round(V_dieu_tiet_B, 2)],
                ["Dieu tiet uoc tinh tu ho C ve A (trieu m3)", round(V_dieu_tiet_C, 2)],
                ["Con thieu sau dieu tiet (trieu m3)", round(V_con_thieu_he_thong, 2)],
            ]

            alert_lines = []
            has_warning = False
            has_caution = False

            # Hồ A
            if V_cuoi_A > V_max_A:
                alert_lines.append(f"* **Hồ A:** Dự kiến đầy hồ (**{V_cuoi_A:.2f} triệu m3** / **{V_max_A:.2f} triệu m3**). Nguy cơ xả tràn.")
                has_warning = True
            elif V_cuoi_A < 0.0:
                alert_lines.append(f"* **Hồ A:** Nguy cơ thiếu nước nghiêm trọng (**{V_cuoi_A:.2f} triệu m3** < 0.0). Lượng nước đầu kỳ và nước về không đủ phát điện.")
                has_caution = True
            else:
                alert_lines.append(f"* **Hồ A:** Vận hành an toàn (dự kiến cuối kỳ đạt **{V_cuoi_A:.2f} triệu m3** / **{V_max_A:.2f} triệu m3**).")

            # Hồ B
            if V_cuoi_B > V_max_B:
                alert_lines.append(f"* **Hồ B:** Dự kiến đầy hồ (**{V_cuoi_B:.2f} triệu m3** / **{V_max_B:.2f} triệu m3**). Nguy cơ xả tràn.")
                has_warning = True
            else:
                alert_lines.append(f"* **Hồ B:** Vận hành an toàn (dự kiến cuối kỳ đạt **{V_cuoi_B:.2f} triệu m3** / **{V_max_B:.2f} triệu m3**).")

            # Hồ C
            if V_cuoi_C > V_max_C:
                alert_lines.append(f"* **Hồ C:** Dự kiến đầy hồ (**{V_cuoi_C:.2f} triệu m3** / **{V_max_C:.2f} triệu m3**). Nguy cơ xả tràn.")
                has_warning = True
            else:
                alert_lines.append(f"* **Hồ C:** Vận hành an toàn (dự kiến cuối kỳ đạt **{V_cuoi_C:.2f} triệu m3** / **{V_max_C:.2f} triệu m3**).")

            alert_block = "\n".join(alert_lines)
            if has_caution:
                alert_str = f"""> [!CAUTION]
> **Cảnh báo vận hành hồ chứa Vĩnh Sơn:**
{alert_block}
"""
            elif has_warning:
                alert_str = f"""> [!WARNING]
> **Cảnh báo vận hành hồ chứa Vĩnh Sơn:**
{alert_block}
"""
            else:
                alert_str = f"""> [!NOTE]
> **Cảnh báo vận hành hồ chứa Vĩnh Sơn:**
{alert_block}
"""

            # Tính toán lưu lượng máy chạy máy Qcm trung bình
            total_Qcm = (total_commercial * STH) / (Total_Time * last_day_forecast)

            # ===== BUILD RESULT =====
            result = f"""### 📊 Dự báo Qve và Sản lượng - Vĩnh Sơn (A, B, C)
**Tháng dự báo:** {target_month}/{target_year}

> [!NOTE]
> **Hiệu chỉnh độ ẩm lưu vực (Soil Moisture Scaling):**
> * Lượng mưa lũy kế tháng trước ({compare_month:02d}/{compare_year}): **{R_cur:.1f} mm** (thực tế đo được)
> * Lượng mưa lũy kế tháng trước năm tương đồng ({compare_month:02d}/{compare_year_analog}): **{R_ana:.1f} mm**
> * Hệ số hiệu chỉnh lưu lượng về (Qve): **{wetness_factor:.2f}** (lưu lượng về lịch sử được nhân với hệ số này trước khi hiệu chỉnh theo dự báo mưa)

---

#### 📋 Phương pháp dự báo

Dựa trên phân tích **tháng {compare_month}** của các năm liền kề:

| Năm | {' | '.join(res_labels)} | Tổng Qve (m3/s) |
|:---:|---:|---:|---:|---:|---:|
"""
            # Kết hợp dữ liệu Qve
            for yr in sorted(qve_data_by_year.keys(), key=lambda x: -x):
                year_qve_values = qve_data_by_year[yr]
                row_data = [str(yr)]
                for res_label in res_labels:
                    qv = year_qve_values.get(res_label, "-")
                    if isinstance(qv, (int, float)):
                        row_data.append(f"{qv:.2f}")
                    else:
                        row_data.append("-")
                # Thêm cột tổng Qve của năm
                sum_yr = sum(year_qve_values.values())
                marker = " ←" if yr == closest_year else ""
                row_data.append(f"{sum_yr:.2f}{marker}")
                result += "| " + ' | '.join(row_data) + " |\n"

            result += f"""
**Giá trị so sánh:** {compare_label} = {compare_value:.2f} m3/s

---
**Qve Hồ A trung bình:** {avg_a:.2f} m3/s
**Qve Hồ B trung bình:** {avg_b:.2f} m3/s
**Qve Hồ C trung bình:** {avg_c:.2f} m3/s
**Qcm trung bình dự báo:** {total_Qcm:.2f} m3/s *(Suất tiêu hao: {STH} m3/kWh)*
**Sản lượng đầu cực dự báo:** {total_commercial:,.0f} kWh
*(Tổng sản lượng đầu cực ngày từ bảng chi tiết)*

---

#### 📅 Dự báo chi tiết từng ngày - {target_month}/{closest_year}
*Dựa trên dữ liệu tháng {target_month}/{closest_year}*

"""
            # Tạo bảng dữ liệu từng ngày
            result += f"| Ngày | Qve Hồ A (m3/s) | Qve Hồ B (m3/s) | Qve Hồ C (m3/s) | Lượng mưa lịch sử ({closest_year}) (mm) | Dự báo lượng mưa (mm) | Sản lượng đầu cực (kWh) |\n"
            result += "|:---:|---:|---:|---:|---:|---:|---:|\n"
            result += table_rows
            forecast_excel_rows.append([
                "Trung binh/Tong",
                round(avg_a, 2),
                round(avg_b, 2),
                round(avg_c, 2),
                None,
                None,
                round(total_commercial, 0),
            ])
            result += f"| **Trung bình/Tổng** | **{avg_a:.2f}** | **{avg_b:.2f}** | **{avg_c:.2f}** | **-** | **-** | **{total_commercial:,.0f}** |\n"

            # Phần kết luận và cảnh báo vận hành
            result += f"""
---

#### 🔮 Kết luận & Cân bằng nước dự báo

**Mực nước & dung tích đầu kỳ:**
*   **Hồ A:** H_đầu = **{H_dau_A:.2f} m**, V_đầu = **{V_dau_A:.2f} triệu m3**
*   **Hồ B:** H_đầu = **{H_dau_B:.2f} m**, V_đầu = **{V_dau_B:.2f} triệu m3**
*   **Hồ C:** H_đầu = **{H_dau_C:.2f} m**, V_đầu = **{V_dau_C:.2f} triệu m3**

**Tổng nước phát điện tiêu thụ:** **{total_V_phat:.2f} triệu m3**

#### Đánh giá MNH hiện tại, dung tích và điều tiết bậc thang

| Hồ | MNH hiện tại (m) | Dung tích hiện có (triệu m3) | Dung tích còn trống (triệu m3) | Nước về dự báo (triệu m3) | Dung tích cuối kỳ (triệu m3) |
|:---:|---:|---:|---:|---:|---:|
| A | {H_dau_A:.2f} | {V_dau_A:.2f} | {V_trong_A:.2f} | {total_V_ve_a:.2f} | {V_cuoi_A:.2f} |
| B | {H_dau_B:.2f} | {V_dau_B:.2f} | {V_trong_B:.2f} | {total_V_ve_b:.2f} | {V_cuoi_B:.2f} |
| C | {H_dau_C:.2f} | {V_dau_C:.2f} | {V_trong_C:.2f} | {total_V_ve_c:.2f} | {V_cuoi_C:.2f} |

**Nguồn nước riêng hồ A:** **{V_nguon_A:.2f} triệu m3** so với nhu cầu phát điện **{total_V_phat:.2f} triệu m3**.
**Trạng thái hồ A:** {"Đủ nước phát theo sản lượng dự báo" if du_nuoc_ho_a else f"Thiếu khoảng {V_thieu_A:.2f} triệu m3 nếu không điều tiết bổ sung từ B/C"}.
**Nguồn nước toàn hệ thống A+B+C:** **{V_nguon_he_thong:.2f} triệu m3** - {"đủ" if du_nuoc_he_thong else "chưa đủ"} cho sản lượng dự báo.
**Phương án điều tiết:** {dieu_tiet_recommendation}

{alert_str}
"""

            if forecast_chart_data:
                forecast_chart_json = {
                    "type": "composed",
                    "title": f"Biểu đồ dự báo Qve hàng ngày Vĩnh Sơn tháng {target_month}/{target_year}",
                    "data": forecast_chart_data,
                    "xKey": "Ngay",
                    "barKeys": ["SanLuong"],
                    "lineKeys": ["QveHoA", "QveHoB", "QveHoC"],
                    "barColors": ["#6366f1"],
                    "lineColors": ["#10b981", "#3b82f6", "#f59e0b"],
                    "barUnit": " kWh",
                    "lineUnit": " m3/s",
                }
                output_chart_json = {
                    "type": "bar",
                    "title": f"Biểu đồ dự báo Sản lượng đầu cực hàng ngày Vĩnh Sơn tháng {target_month}/{target_year}",
                    "data": forecast_chart_data,
                    "xKey": "Ngay",
                    "yKeys": ["SanLuong"],
                    "colors": ["#6366f1"],
                    "unit": " kWh",
                }
                excel_report_json = {
                    "title": f"Bao cao du bao Vinh Son thang {target_month:02d}/{target_year}",
                    "fileName": f"bao-cao-du-bao-vinh-son-{target_month:02d}-{target_year}.xlsx",
                    "prompt": "Bạn có cần xuất file Excel để báo cáo không?",
                    "sheets": [
                        {
                            "name": "Du bao ngay",
                            "rows": forecast_excel_rows,
                        },
                        {
                            "name": "Can bang nuoc",
                            "rows": water_balance_excel_rows,
                        }
                    ],
                }
                result += f"\n\n```chart\n{json.dumps(forecast_chart_json, ensure_ascii=False, indent=2)}\n```\n"
                result += f"\n\n```excel\n{json.dumps(excel_report_json, ensure_ascii=False, indent=2)}\n```\n"

            result += """---

**Lưu ý:**
**Để có dự báo chính xác hơn, cần xem xét nhiều yếu tố như: lượng mưa dự báo thực tế, mực nước hồ hiện tại, kế hoạch vận hành.**
"""
            return result.strip()

        except Exception as e:
            return f"### Lỗi dự báo\n\n{str(e)}"

    def forecast_year(self, target_year: int, reservoir: str = "All") -> str:
        """Dự báo Qve và Sản lượng cho cả năm cho bậc thang Vĩnh Sơn."""
        try:
            _, spreadsheet_stats = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet_stats:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối với sheet TV VS."

            stats_ws = pick_stats_worksheet(spreadsheet_stats)
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet TV VS."

            all_data = retry_with_backoff(stats_ws.get_all_values, max_retries=3, initial_delay=1)
            if not all_data or len(all_data) < 2:
                return "Không có dữ liệu."

            data_start = find_data_start_row(all_data)
            rows = all_data[data_start:] if data_start < len(all_data) else []
            years_to_check = [target_year - 1, target_year - 2, target_year - 3, target_year - 4]
            res_labels = ["Hồ A", "Hồ B", "Hồ C"]

            qve_data_by_year: Dict[int, Dict[str, float]] = {}
            for yr in years_to_check:
                year_qve_values = get_year_data_all_reservoirs(rows, yr)
                if year_qve_values:
                    qve_data_by_year[yr] = year_qve_values

            if not qve_data_by_year:
                return "### Không đủ dữ liệu\n\nKhông có dữ liệu Qve của các năm liền kề để dự báo."

            # Tính tổng Qve 3 hồ cho từng năm
            qve_data: List[Tuple[int, float]] = []
            for yr, year_qve_values in qve_data_by_year.items():
                qve_data.append((yr, sum(year_qve_values.values())))

            # Tính trung bình tổng Qve các năm
            avg_qve = sum(q for _, q in qve_data) / len(qve_data)
            closest_year = min(qve_data, key=lambda x: abs(x[1] - avg_qve))[0]
            forecast_qve_by_res = qve_data_by_year.get(closest_year, {})
            forecast_output = get_output_year(closest_year)

            # Tính trung bình từng hồ qua các năm
            avg_qve_by_res: Dict[str, float] = {}
            for res_label in res_labels:
                vals = [
                    year_qve[res_label]
                    for year_qve in qve_data_by_year.values()
                    if res_label in year_qve
                ]
                if vals:
                    avg_qve_by_res[res_label] = sum(vals) / len(vals)

            result = f"""### 📊 Dự báo Qve và Sản lượng - Vĩnh Sơn (A, B, C)
**Năm dự báo:** {target_year}

---

#### 📋 Phương pháp dự báo

Dựa trên phân tích các năm liền kề:

| Năm | {' | '.join(res_labels)} | Tổng cả năm (m3/s) | Sản lượng đầu cực (kWh) |
|:---:|---:|---:|---:|---:|---:|
"""

            year_chart_data = []
            for yr in sorted(qve_data_by_year.keys(), key=lambda x: -x):
                year_qve_values = qve_data_by_year[yr]
                row_data = [str(yr)]
                for res_label in res_labels:
                    qv = year_qve_values.get(res_label, "-")
                    if isinstance(qv, (int, float)):
                        row_data.append(f"{qv:.2f}")
                    else:
                        row_data.append("-")
                sum_yr = sum(year_qve_values.values())
                output_yr = get_output_year(yr)
                marker = " ←" if yr == closest_year else ""
                row_data.append(f"{sum_yr:.2f}{marker}")
                row_data.append(f"{output_yr:,.0f}" if output_yr else "-")
                result += "| " + ' | '.join(row_data) + " |\n"
                year_chart_data.append({
                    "Nam": str(yr),
                    "QveHoA": round(year_qve_values.get(res_labels[0], 0), 2),
                    "QveHoB": round(year_qve_values.get(res_labels[1], 0), 2),
                    "QveHoC": round(year_qve_values.get(res_labels[2], 0), 2),
                    "SanLuong": round(output_yr or 0, 0),
                })

            avg_a_yr = avg_qve_by_res.get('Hồ A', 0.0)
            avg_b_yr = avg_qve_by_res.get('Hồ B', 0.0)
            avg_c_yr = avg_qve_by_res.get('Hồ C', 0.0)
            fc_a_yr = forecast_qve_by_res.get('Hồ A', 0.0)
            fc_b_yr = forecast_qve_by_res.get('Hồ B', 0.0)
            fc_c_yr = forecast_qve_by_res.get('Hồ C', 0.0)
            result += f"""
**Trung bình Qve cả năm:**
- Hồ A: {avg_a_yr:.2f} m3/s
- Hồ B: {avg_b_yr:.2f} m3/s
- Hồ C: {avg_c_yr:.2f} m3/s
- **Tổng trung bình:** {avg_qve:.2f} m3/s

**Năm được chọn để dự báo:** {closest_year}

---

#### 🔮 Dự báo cho năm {target_year}

**Qve dự báo:**
- Hồ A: {fc_a_yr:.2f} m3/s
- Hồ B: {fc_b_yr:.2f} m3/s
- Hồ C: {fc_c_yr:.2f} m3/s

**Sản lượng đầu cực dự báo:** {forecast_output or 0:,.0f} kWh
*(Dựa trên sản lượng năm {closest_year})*

---

**Lưu ý:**
**Để có dự báo chính xác hơn, cần xem xét nhiều yếu tố như: lượng mưa dự báo, mực nước hồ, kế hoạch vận hành.**
"""
            if year_chart_data:
                qve_year_chart_json = {
                    "type": "line",
                    "title": f"Biểu đồ dự báo Qve Vĩnh Sơn năm {target_year}",
                    "data": year_chart_data,
                    "xKey": "Nam",
                    "yKeys": ["QveHoA", "QveHoB", "QveHoC"],
                    "colors": ["#10b981", "#3b82f6", "#f59e0b"],
                    "unit": " m3/s",
                }
                output_year_chart_json = {
                    "type": "bar",
                    "title": f"Biểu đồ dự báo Sản lượng Vĩnh Sơn năm {target_year}",
                    "data": year_chart_data,
                    "xKey": "Nam",
                    "yKeys": ["SanLuong"],
                    "colors": ["#6366f1"],
                    "unit": " kWh",
                }
                result += f"\n\n```chart\n{json.dumps(qve_year_chart_json, ensure_ascii=False, indent=2)}\n```\n"
                result += f"\n\n```chart\n{json.dumps(output_year_chart_json, ensure_ascii=False, indent=2)}\n```\n"

            return result.strip()

        except Exception as e:
            return f"### Lỗi dự báo\n\n{str(e)}"
