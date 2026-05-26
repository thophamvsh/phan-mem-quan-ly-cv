"""
Forecast service - Dự báo Qve và Sản lượng cho tháng/năm tới cho Vĩnh Sơn.
Áp dụng phương pháp từ Sông Hinh với 3 hồ A, B, C.
Lấy dữ liệu Qve từ spreadsheet_id (sheet vận hành).
"""

from __future__ import annotations

from datetime import date
from typing import Optional, List, Tuple, Dict
import calendar

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
        if not row or len(row) <= COL_DATE:
            continue
        cell_str = str(row[COL_DATE]).strip() if COL_DATE < len(row) else ""
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
                if not dt or dt.year != year or dt.month != month:
                    continue

                day = dt.day

                # Lấy Sản lượng đầu cực ngày (cột M)
                if len(row) > COL_OUTPUT_DAY:
                    val = parse_number(_cell(row, COL_OUTPUT_DAY))
                    if val is not None:
                        commercial_by_day[day] = val

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

            # Tính trung bình Qve của 3 hồ cho từng năm
            qve_data: List[Tuple[int, float]] = []
            for yr, year_qve_values in qve_data_by_year.items():
                avg_qve_for_year = sum(year_qve_values.values()) / len(year_qve_values)
                qve_data.append((yr, avg_qve_for_year))

            current_month_qve = sum(current_qve_by_res.values()) / len(current_qve_by_res) if current_qve_by_res else None

            # Tính trung bình Qve của từng hồ qua các năm
            avg_qve_by_res: Dict[str, float] = {}
            for res_label in res_labels:
                vals = [year_qve.get(res_label, 0) for year_qve in qve_data_by_year.values() if res_label in year_qve]
                if vals:
                    avg_qve_by_res[res_label] = sum(vals) / len(vals)

            avg_qve = sum([q for _, q in qve_data]) / len(qve_data)

            # Chọn năm gần nhất
            if current_month_qve is not None:
                closest_year = min(qve_data, key=lambda x: abs(x[1] - current_month_qve))[0]
                compare_value = current_month_qve
                compare_label = f"Qve tháng {compare_month}/{target_year}"
            else:
                closest_year = min(qve_data, key=lambda x: abs(x[1] - avg_qve))[0]
                compare_value = avg_qve
                compare_label = "trung bình"

            # ===== LẤY DỮ LIỆU TỪNG NGÀY =====
            # Lấy dữ liệu chi tiết từng ngày để lấy giá trị trung bình
            qve_by_day, commercial_by_day = get_daily_data_for_month_vinhson(closest_year, target_month)

            # Tính toán giá trị từ dữ liệu hàng ngày
            total_commercial = 0.0
            qve_values_a, qve_values_b, qve_values_c = [], [], []

            last_day_forecast = calendar.monthrange(target_year, target_month)[1]

            for day in range(1, last_day_forecast + 1):
                day_qve_dict = qve_by_day.get(day, {})
                commercial_val = commercial_by_day.get(day, "-")

                qve_a = day_qve_dict.get("Hồ A", "-")
                qve_b = day_qve_dict.get("Hồ B", "-")
                qve_c = day_qve_dict.get("Hồ C", "-")

                # Bỏ qua dòng nếu tất cả đều không có dữ liệu
                if qve_a == "-" and qve_b == "-" and qve_c == "-" and commercial_val == "-":
                    continue

                # Thu thập giá trị để tính trung bình
                if isinstance(qve_a, (int, float)):
                    qve_values_a.append(qve_a)
                if isinstance(qve_b, (int, float)):
                    qve_values_b.append(qve_b)
                if isinstance(qve_c, (int, float)):
                    qve_values_c.append(qve_c)
                if isinstance(commercial_val, (int, float)):
                    total_commercial += commercial_val

            # Tính trung bình từng hồ từ dữ liệu hàng ngày
            avg_a = sum(qve_values_a) / len(qve_values_a) if qve_values_a else 0
            avg_b = sum(qve_values_b) / len(qve_values_b) if qve_values_b else 0
            avg_c = sum(qve_values_c) / len(qve_values_c) if qve_values_c else 0

            # ===== BUILD RESULT =====
            result = f"""### 📊 Dự báo Qve và Sản lượng - Vĩnh Sơn (A, B, C)
**Tháng dự báo:** {target_month}/{target_year}

---

#### 📋 Phương pháp dự báo

Dựa trên phân tích **tháng {compare_month}** của các năm liền kề:

| Năm | {" | ".join(res_labels)} |
|:---:|---:|---:|---:|---:|
"""
            # Kết hợp dữ liệu Qve
            for yr in sorted(qve_data_by_year.keys(), key=lambda x: -x):
                year_qve_values = qve_data_by_year[yr]
                row_data = [str(yr)]
                for res_label in res_labels:
                    qv = year_qve_values.get(res_label, "-")
                    if isinstance(qv, (int, float)):
                        marker = " ←" if yr == closest_year else ""
                        row_data.append(f"{qv:.2f}{marker}")
                    else:
                        row_data.append("-")
                result += "| " + " | ".join(row_data) + " |\n"

            result += f"""
**Giá trị so sánh:** {compare_label} = {compare_value:.2f} m³/s

---
**Qve Hồ A:** {avg_a:.2f} m³/s
**Qve Hồ B:** {avg_b:.2f} m³/s
**Qve Hồ C:** {avg_c:.2f} m³/s
**Sản lượng dự báo:** {total_commercial:,.0f} kWh
*(Tổng sản lượng từ bảng chi tiết từng ngày)*

---

#### 📅 Dự báo chi tiết từng ngày - {target_month}/{closest_year}
*Dựa trên dữ liệu tháng {target_month}/{closest_year}*

"""
            # Tạo bảng dữ liệu từng ngày
            result += f"| Ngày | Qve Hồ A (m³/s) | Qve Hồ B (m³/s) | Qve Hồ C (m³/s) | Sản lượng (kWh) |\n"
            result += "|:---:|---:|---:|---:|---:|\n"

            for day in range(1, last_day_forecast + 1):
                day_qve_dict = qve_by_day.get(day, {})
                commercial_val = commercial_by_day.get(day, "-")

                qve_a = day_qve_dict.get("Hồ A", "-")
                qve_b = day_qve_dict.get("Hồ B", "-")
                qve_c = day_qve_dict.get("Hồ C", "-")

                qve_a_str = f"{qve_a:.2f}" if isinstance(qve_a, (int, float)) else "-"
                qve_b_str = f"{qve_b:.2f}" if isinstance(qve_b, (int, float)) else "-"
                qve_c_str = f"{qve_c:.2f}" if isinstance(qve_c, (int, float)) else "-"
                commercial_str = f"{commercial_val:,.0f}" if isinstance(commercial_val, (int, float)) else "-"

                if qve_a == "-" and qve_b == "-" and qve_c == "-" and commercial_val == "-":
                    continue

                day_display = f"{day}/{target_month}/{target_year}"
                result += f"| {day_display} | {qve_a_str} | {qve_b_str} | {qve_c_str} | {commercial_str} |\n"

            # Thêm hàng trung bình
            result += f"| **Trung bình** | **{avg_a:.2f}** | **{avg_b:.2f}** | **{avg_c:.2f}** | **{total_commercial:,.0f}** |\n"""

            result += """---

**Lưu ý:**
**Để có dự báo chính xác hơn, cần xem xét nhiều yếu tố như: lượng mưa dự báo, mực nước hồ, kế hoạch vận hành.**

"""
            return result.strip()

        except Exception as e:
            return f"### Lỗi dự báo\n\n{str(e)}"

#     def forecast_year(self, target_year: int, reservoir: str = "All") -> str:
#         """Dự báo Qve cho cả năm - hiển thị 3 cột cho hồ A, B, C.

#         Args:
#             target_year: Năm dự báo
#             reservoir: Tham số giữ lại để tương thích (hiện tại luôn dự báo cho cả 3 hồ)
#         """
#         try:
#             _, spreadsheet_stats = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
#             if not spreadsheet_stats:
#                 return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối."

#             stats_ws = pick_stats_worksheet(spreadsheet_stats)
#             if not stats_ws:
#                 return "### Lỗi\n\nKhông tìm thấy worksheet TV VS."

#             all_data = retry_with_backoff(stats_ws.get_all_values, max_retries=3, initial_delay=1)
#             if not all_data or len(all_data) < 2:
#                 return "Không có dữ liệu."

#             data_start = find_data_start_row(all_data)
#             rows = all_data[data_start:] if data_start < len(all_data) else []

#             years_to_check = [target_year - 1, target_year - 2, target_year - 3, target_year - 4]
#             res_labels = ["Hồ A", "Hồ B", "Hồ C"]
#             qve_cols = [COL_QVE_A, COL_QVE_B, COL_QVE_C]

#             # Lấy Qve cả năm của từng hồ
#             qve_data_by_year: Dict[int, Dict[str, float]] = {}
#             for yr in years_to_check:
#                 year_qve_values = {}
#                 for res_label, col_qve in zip(res_labels, qve_cols):
#                     year_vals: List[float] = []
#                     for r in rows:
#                         dt = _date_from_stats_row(r)
#                         if dt and dt.year == yr:
#                             val_str = _cell(r, col_qve)
#                             v = parse_number_for_qve(val_str)
#                             if v is not None:
#                                 year_vals.append(v)
#                     if year_vals:
#                         year_qve_values[res_label] = sum(year_vals) / len(year_vals)
#                 if year_qve_values:
#                     qve_data_by_year[yr] = year_qve_values

#             if not qve_data_by_year:
#                 return "### Không đủ dữ liệu\n\nKhông có dữ liệu Qve của các năm liền kề để dự báo."

#             # Tính trung bình Qve của 3 hồ cho từng năm
#             qve_data: List[Tuple[int, float]] = []
#             for yr, year_qve_values in qve_data_by_year.items():
#                 avg_qve_for_year = sum(year_qve_values.values()) / len(year_qve_values)
#                 qve_data.append((yr, avg_qve_for_year))

#             avg_qve = sum([q for _, q in qve_data]) / len(qve_data)
#             closest_year = min(qve_data, key=lambda x: abs(x[1] - avg_qve))[0]

#             # Lấy forecast Qve của từng hồ
#             forecast_qve_by_res = qve_data_by_year.get(closest_year, {})

#             # Tính trung bình Qve của từng hồ qua các năm
#             avg_qve_by_res: Dict[str, float] = {}
#             for res_label in res_labels:
#                 vals = [year_qve.get(res_label, 0) for year_qve in qve_data_by_year.values() if res_label in year_qve]
#                 if vals:
#                     avg_qve_by_res[res_label] = sum(vals) / len(vals)

#             result = f"""### 📊 Dự báo Qve - Vĩnh Sơn (A, B, C)
# **Năm dự báo:** {target_year}

# ---

# #### 📋 Phương pháp dự báo

# Dựa trên phân tích các năm liền kề:

# | Năm | {" | ".join(res_labels)} | TB cả năm (m³/s) |
# |:---:|---:|---:|---:|---:|
# """
#             for yr in sorted(qve_data_by_year.keys(), key=lambda x: -x):
#                 year_qve_values = qve_data_by_year[yr]
#                 row_data = [str(yr)]
#                 for res_label in res_labels:
#                     qv = year_qve_values.get(res_label, "-")
#                     if isinstance(qv, (int, float)):
#                         marker = " ←" if yr == closest_year else ""
#                         row_data.append(f"{qv:.2f}{marker}")
#                     else:
#                         row_data.append("-")
#                 # Thêm trung bình cả năm
#                 avg_yr = sum(year_qve_values.values()) / len(year_qve_values)
#                 row_data.append(f"{avg_yr:.2f}")
#                 result += "| " + " | ".join(row_data) + " |\n"

#             result += f"""
# **Trung bình Qve cả năm:**
# - Hồ A: {avg_qve_by_res.get('Hồ A', 0):.2f} m³/s
# - Hồ B: {avg_qve_by_res.get('Hồ B', 0):.2f} m³/s
# - Hồ C: {avg_qve_by_res.get('Hồ C', 0):.2f} m³/s
# - **Trung bình chung:** {avg_qve:.2f} m³/s

# **Năm được chọn để dự báo:** {closest_year}

# ---

# #### 🔮 Dự báo cho năm {target_year}

# **Qve dự báo:**
# - Hồ A: {forecast_qve_by_res.get('Hồ A', 0):.2f} m³/s
# - Hồ B: {forecast_qve_by_res.get('Hồ B', 0):.2f} m³/s
# - Hồ C: {forecast_qve_by_res.get('Hồ C', 0):.2f} m³/s

# ---

# **Lưu ý:**
# - Đây là dự báo đơn giản dựa trên Qve trung bình của năm liền kề.

# **Nguồn dữ liệu:** Google Sheets thống kê (Vĩnh Sơn)
# """
#             return result.strip()

#         except Exception as e:
#             return f"### Lỗi dự báo\n\n{str(e)}"
