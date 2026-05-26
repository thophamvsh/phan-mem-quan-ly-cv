"""
Forecast service - Dự báo Qve và Sản lượng cho tháng/năm tới cho Sông Hinh.
"""

from __future__ import annotations

from datetime import date
from typing import Optional, List, Tuple

from ..config.settings import GS_CONFIG
from ..config.columns import OP_COLS
from ..core.sheets_client import get_sheets_client_manager
from ..utils.dates import normalize_date
from ..utils.numbers import parse_number, parse_kwh_integer


# Sheet Thống kê (0-based) - Sông Hinh
COL_DATE_STATS_SH = 0
COL_QVE_SH = 5  # Cột F - Lưu lượng về 2026


def _get_manager():
    return get_sheets_client_manager()


def _cell(row: list, i: int) -> str:
    return row[i] if i < len(row) else ""


def _date_from_stats_row(row: list) -> Optional[date]:
    for col in (0, COL_DATE_STATS_SH):
        if col >= len(row):
            continue
        raw = str(_cell(row, col)).strip()
        if not raw:
            continue
        d = normalize_date(raw)
        if d:
            return d
    return None


def find_data_start_row(all_data: List[List[str]]) -> int:
    # Check column A (index 0) for date pattern in Sông Hinh production sheet
    print(f"[DEBUG] find_data_start_row SH: checking {len(all_data)} rows")
    for i, row in enumerate(all_data[:50]):
        if not row or len(row) < 2:
            continue

        # Check column A for date (index 0)
        cell_str = str(row[0]).strip() if len(row) > 0 else ""
        if "/" in cell_str and any(c.isdigit() for c in cell_str):
            parts = cell_str.split("/")
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                print(
                    f"[DEBUG] find_data_start_row SH: found date at row {i}, col 0: '{cell_str}'"
                )
                return i

        if i < 15:
            # Log first few rows to debug
            print(
                f"[DEBUG] find_data_start_row SH: row {i}: {[str(c)[:20] for c in row[:6]]}"
            )

    return 7 if len(all_data) > 7 else 1


def get_month_data(
    rows: List[list], year: int, month: int, col_qve: int
) -> Optional[float]:
    vals: List[float] = []
    for r in rows:
        dt = _date_from_stats_row(r)
        if dt and dt.year == year and dt.month == month:
            val_str = _cell(r, col_qve)
            v = parse_number(val_str)
            if v is not None:
                vals.append(v)

    if vals:
        return sum(vals) / len(vals)
    return None


def get_output_month(manager, year: int, month: int) -> Optional[float]:
    """Lấy sản lượng điện thương phẩm tháng từ Google Sheets sản lượng Sông Hinh.
    Lấy ngày cuối cùng của tháng (dòng cuối cùng trong tháng)."""
    try:
        # Dùng spreadsheet_id (sheet Sản lượng) cho Sông Hinh
        # ID: 1P_yKjS0FkAwWPjwgvEB0NosVu9ic-lAF0aseZh1o2EM
        spreadsheet = manager.get_write_spreadsheet(GS_CONFIG.spreadsheet_id)
        if not spreadsheet:
            print(f"[DEBUG] get_output_month SH: no spreadsheet")
            return None

        worksheets = spreadsheet.worksheets()
        print(f"[DEBUG] get_output_month SH: worksheets = {[ws.title for ws in worksheets]}")

        op_ws = None
        for ws in worksheets:
            if "Sản lượng" in ws.title:
                op_ws = ws
                print(f"[DEBUG] get_output_month SH: found sheet 'Sản lượng'")
                break

        op_ws = op_ws or (worksheets[0] if worksheets else None)
        if not op_ws:
            print(f"[DEBUG] get_output_month SH: no worksheet found")
            return None

        all_data = op_ws.get_all_values()
        print(f"[DEBUG] get_output_month SH: rows = {len(all_data)}, looking for {month}/{year}")

        # Column indices for Sông Hinh production sheet (1P_yKjS0FkAwWPjwgvEB0NosVu9ic-lAF0aseZh1o2EM)
        # Cột A (index 0): Ngày
        # Cột N (index 13): Sản lượng điện thương phẩm tháng

        print(
            f"[DEBUG] get_output_month SH: COL_DATE={OP_COLS.COL_DATE}, "
            f"COL_OUTPUT_MONTH={OP_COLS.COL_COMMERCIAL_MONTH}"
        )

        # Tìm dòng bắt đầu dữ liệu thực (bỏ qua header, quy ước, v.v.)
        data_start_row = find_data_start_row(all_data)
        data_rows = all_data[data_start_row:] if data_start_row < len(all_data) else []

        # Tìm tất cả các dòng trong tháng, lấy dòng cuối cùng (ngày cuối tháng)
        last_row_for_month = None
        last_date = None

        # Tìm dòng dữ liệu - check column A for date
        for row in data_rows:
            if len(row) <= OP_COLS.COL_DATE:
                continue

            # Check column A for date (index 0)
            cell_str = (
                str(row[OP_COLS.COL_DATE]).strip()
                if len(row) > OP_COLS.COL_DATE
                else ""
            )
            dt = normalize_date(cell_str)
            if dt and dt.year == year and dt.month == month:
                # Lấy dòng có ngày lớn nhất (ngày cuối tháng)
                if last_date is None or dt.day > last_date.day:
                    last_date = dt
                    last_row_for_month = row

        if last_row_for_month:
            print(
                f"[DEBUG] get_output_month SH: found row for {month}/{year} "
                f"(last day {last_date.day})"
            )
            print(f"[DEBUG] get_output_month SH: row = {last_row_for_month[:20]}")

            # Cột sản lượng thương phẩm tháng
            if len(last_row_for_month) > OP_COLS.COL_COMMERCIAL_MONTH:
                val = parse_number(last_row_for_month[OP_COLS.COL_COMMERCIAL_MONTH])
                print(
                    f"[DEBUG] get_output_month SH: "
                    f"COL_OUTPUT_MONTH={OP_COLS.COL_COMMERCIAL_DAY}, "
                    f"value = '{last_row_for_month[OP_COLS.COL_COMMERCIAL_MONTH]}', "
                    f"parsed = {val}"
                )
                if val:
                    return val

    except Exception as e:
        print(f"[WARN] Lỗi lấy sản lượng: {e}")

    return None


def get_daily_data_for_month(
    manager, year: int, month: int
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """Lấy dữ liệu Qve và Sản lượng thương phẩm ngày từ sheet Thống kê và sheet Sản lượng.
    Trả về: (list of (day, qve), list of (day, commercial_output))
    """
    import calendar

    # Lấy số ngày trong tháng
    last_day = calendar.monthrange(year, month)[1]

    # Lấy Qve từ sheet Thống kê
    spreadsheet_stats = manager.get_write_spreadsheet(
        GS_CONFIG.stats_export_spreadsheet_id_songhinh
    )
    qve_by_day = []
    if spreadsheet_stats:
        worksheets = spreadsheet_stats.worksheets()
        stats_ws = None
        for ws in worksheets:
            if "Thống kê" in ws.title:
                stats_ws = ws
                break

        stats_ws = stats_ws or (worksheets[0] if worksheets else None)
        if stats_ws:
            all_data = stats_ws.get_all_values()
            data_start = find_data_start_row(all_data)
            data_rows = all_data[data_start:] if data_start < len(all_data) else []

            for row in data_rows:
                dt = _date_from_stats_row(row)
                if dt and dt.year == year and dt.month == month:
                    val_str = _cell(row, COL_QVE_SH)
                    v = parse_number(val_str)
                    if v is not None:
                        qve_by_day.append((dt.day, v))

    # Lấy Sản lượng thương phẩm ngày từ sheet Sản lượng
    spreadsheet_prod = manager.get_write_spreadsheet(GS_CONFIG.spreadsheet_id)
    commercial_by_day = []
    if spreadsheet_prod:
        worksheets = spreadsheet_prod.worksheets()
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
                # Cột A (index 0) là Ngày
                if len(row) <= OP_COLS.COL_DATE:
                    continue

                cell_str = _cell(row, OP_COLS.COL_DATE)
                dt = normalize_date(cell_str)
                if dt and dt.year == year and dt.month == month:
                    # Cột N (COL_COMMERCIAL_DAY) là Sản lượng thương phẩm ngày
                    if len(row) > OP_COLS.COL_COMMERCIAL_DAY:
                        val_str = _cell(row, OP_COLS.COL_COMMERCIAL_DAY)
                        v = parse_kwh_integer(val_str)
                        if v is not None:
                            commercial_by_day.append((dt.day, v))

    return qve_by_day, commercial_by_day


class ForecastServiceSH:
    """Service dự báo Qve và Sản lượng cho Sông Hinh."""

    def __init__(self):
        pass

    def forecast_month(self, target_month: int, target_year: int) -> str:
        try:
            # Xác định tháng trước để so sánh (tháng M-1)
            if target_month == 1:
                compare_month = 12
            else:
                compare_month = target_month - 1

            # Lấy dữ liệu từ Google Sheets
            manager = _get_manager()
            spreadsheet = manager.get_write_spreadsheet(
                GS_CONFIG.stats_export_spreadsheet_id_songhinh
            )
            if not spreadsheet:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối."

            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title:
                    stats_ws = ws
                    break

            stats_ws = stats_ws or (worksheets[0] if worksheets else None)
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê."

            all_data = manager.get_all_values_cached(stats_ws, cache_key="forecast_stats")
            if not all_data or len(all_data) < 2:
                return "Không có dữ liệu."

            data_start = find_data_start_row(all_data)
            rows = all_data[data_start:] if data_start < len(all_data) else []

            # Lấy Qve tháng trước của các năm liền kề
            years_to_check = [target_year - 1, target_year - 2, target_year - 3]
            col_qve = 5

            qve_data: List[Tuple[int, float]] = []
            for yr in years_to_check:
                qve = get_month_data(rows, yr, compare_month, col_qve)
                if qve is not None:
                    qve_data.append((yr, qve))

            if not qve_data:
                return (
                    f"### Không đủ dữ liệu\n\n"
                    f"Không có dữ liệu Qve tháng {compare_month} của các năm liền kề để dự báo."
                )

            # Lấy Qve tháng trước của năm hiện tại (để so sánh và chọn năm gần nhất)
            current_month_qve = get_month_data(rows, target_year, compare_month, col_qve)

            # Lấy Sản lượng của các năm liền kề
            output_data: List[Tuple[int, float]] = []
            for yr in years_to_check:
                output_val = get_output_month(manager, yr, compare_month)
                if output_val is not None:
                    output_data.append((yr, output_val))

            avg_qve = sum([q for _, q in qve_data]) / len(qve_data)

            # Chọn năm gần với giá trị hiện tại nhất (nếu có), hoặc gần trung bình
            if current_month_qve is not None:
                closest_year = min(
                    qve_data,
                    key=lambda x: abs(x[1] - current_month_qve),
                )[0]
                compare_value = current_month_qve
                compare_label = f"Qve tháng {compare_month}/{target_year}"
            else:
                closest_year = min(qve_data, key=lambda x: abs(x[1] - avg_qve))[0]
                compare_value = avg_qve
                compare_label = "trung bình"

            forecast_qve = None
            forecast_output = None
            for yr, qv in qve_data:
                if yr == closest_year:
                    forecast_qve = qv
                    # Tìm sản lượng tương ứng
                    for oyr, oval in output_data:
                        if oyr == yr:
                            forecast_output = oval
                            break
                    break

            result = f"""### 📊 Dự báo Qve và Sản lượng - Sông Hinh
**Tháng dự báo:** {target_month}/{target_year}

"""

            if forecast_output:
                result += f"""#### 📅 Dự báo chi tiết từng ngày - Sông Hinh
**Dựa trên dữ liệu tháng:** {target_month}/{closest_year}

"""

                # Lấy dữ liệu chi tiết từng ngày của năm được chọn (tháng dự báo)
                # Ví dụ: dự báo tháng 3/2026, năm chọn 2024 → lấy tháng 3/2024
                qve_by_day, commercial_by_day = get_daily_data_for_month(
                    manager, closest_year, target_month
                )

                # Chuyển đổi sang dict để tra cứu
                qve_dict = dict(qve_by_day)
                commercial_dict = dict(commercial_by_day)

                # Lấy số ngày trong tháng dự báo
                import calendar

                last_day_forecast = calendar.monthrange(target_year, target_month)[1]

                # Tạo bảng dữ liệu từng ngày (chỉ hiển thị ngày có dữ liệu)
                result += f"| Ngày | Qve (m³/s) | Sản lượng (kWh) |\n"
                result += "|------:|-----------:|---------------:|\n"

                total_commercial = 0.0
                qve_values = []

                for day in range(1, last_day_forecast + 1):
                    qve_val = qve_dict.get(day, "-")
                    commercial_val = commercial_dict.get(day, "-")

                    # Bỏ qua dòng nếu cả hai đều không có dữ liệu
                    if qve_val == "-" and commercial_val == "-":
                        continue

                    # Hiển thị ngày đầy đủ: ngày/tháng/năm dự báo
                    day_display = f"{day}/{target_month}/{target_year}"

                    qve_str = (
                        f"{qve_val:.2f}" if isinstance(qve_val, (int, float)) else "-"
                    )
                    commercial_str = (
                        f"{commercial_val:,.0f}"
                        if isinstance(commercial_val, (int, float))
                        else "-"
                    )

                    if isinstance(qve_val, (int, float)):
                        qve_values.append(qve_val)
                    if isinstance(commercial_val, (int, float)):
                        total_commercial += commercial_val

                    result += f"| {day_display} | {qve_str} | {commercial_str} |\n"

                # Thêm hàng tổng/trung bình
                STH = 2.58
                Total_Time = 86400
                total_Qcm = (total_commercial * STH)/(Total_Time*last_day_forecast)
                total_V = ((total_Qcm - avg_qve)*Total_Time*last_day_forecast)/1000000
                avg_qve = sum(qve_values) / len(qve_values) if qve_values else 0
                result += (
                    f"| **Trung bình/Tổng** | **{avg_qve:.2f}** | "
                    f"**{total_commercial:,.0f}** |\n"
                )

            # Kết luận dự báo (sau bảng)
            result += f"""---

#### 🔮 Kết luận dự báo

**Tháng so sánh:** {compare_month}/{closest_year}
**Qve dự báo:** {avg_qve:.2f} m³/s
**Qcm dự báo:** {total_Qcm:.2f} m³/s
**Thể tích tiêu thụ dự báo:** {total_V:.2f} triệu m³

"""

            if forecast_output:
                result += f"""**Sản lượng dự báo:** {total_commercial:,.0f} kWh
**(Tổng sản lượng từ bảng chi tiết)**
"""

            result += """---

**Lưu ý:**
**Để có dự báo chính xác hơn, cần xem xét nhiều yếu tố như: lượng mưa dự báo, mực nước hồ, kế hoạch vận hành.**


"""
            return result.strip()

        except Exception as e:
            return f"### Lỗi dự báo\n\n{str(e)}"

    def forecast_year(self, target_year: int) -> str:
        try:
            # Lấy dữ liệu từ Google Sheets
            manager = _get_manager()
            spreadsheet = manager.get_write_spreadsheet(
                GS_CONFIG.stats_export_spreadsheet_id_songhinh
            )
            if not spreadsheet:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối."

            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title:
                    stats_ws = ws
                    break

            stats_ws = stats_ws or (worksheets[0] if worksheets else None)
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê."

            all_data = manager.get_all_values_cached(
                stats_ws, cache_key="forecast_stats_year"
            )
            if not all_data or len(all_data) < 2:
                return "Không có dữ liệu."

            data_start = find_data_start_row(all_data)
            rows = all_data[data_start:] if data_start < len(all_data) else []

            col_qve = 5
            years_to_check = [
                target_year - 1,
                target_year - 2,
                target_year - 3,
                target_year - 4,
            ]

            qve_data: List[Tuple[int, float]] = []
            for yr in years_to_check:
                year_vals: List[float] = []
                for r in rows:
                    dt = _date_from_stats_row(r)
                    if dt and dt.year == yr:
                        val_str = _cell(r, col_qve)
                        v = parse_number(val_str)
                        if v is not None:
                            year_vals.append(v)

                if year_vals:
                    qve_data.append((yr, sum(year_vals) / len(year_vals)))

            if not qve_data:
                return (
                    "### Không đủ dữ liệu\n\n"
                    "Không có dữ liệu Qve của các năm liền kề để dự báo."
                )

            avg_qve = sum([q for _, q in qve_data]) / len(qve_data)
            closest_year = min(qve_data, key=lambda x: abs(x[1] - avg_qve))[0]

            forecast_qve = None
            for yr, qv in qve_data:
                if yr == closest_year:
                    forecast_qve = qv
                    break

            result = f"""### 📊 Dự báo Qve và Sản lượng - Sông Hinh
**Năm dự báo:** {target_year}

---

#### 📋 Phương pháp dự báo

Dựa trên phân tích các năm liền kề:

| Năm | Qve trung bình cả năm (m³/s) |
|:---:|---:|
"""

            for yr, qv in sorted(qve_data, key=lambda x: -x[0]):
                marker = " ← Gần nhất với trung bình" if yr == closest_year else ""
                result += f"| {yr} | {qv:.2f}{marker} |\n"

            result += f"""
**Trung bình Qve cả năm:** {avg_qve:.2f} m³/s
**Năm được chọn để dự báo:** {closest_year} (Qve = {forecast_qve:.2f} m³/s)

---

#### 🔮 Dự báo cho năm {target_year}

**Qve dự báo:** {forecast_qve:.2f} m³/s
*(Dựa trên Qve năm {closest_year})*

---

**Lưu ý:**
**Để có dự báo chính xác hơn, cần xem xét nhiều yếu tố như: lượng mưa dự báo, mực nước hồ, kế hoạch vận hành.**


"""
            return result.strip()

        except Exception as e:
            return f"### Lỗi dự báo\n\n{str(e)}"