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
                from ai_tools.water_tools.weather_service import (
                    get_rainfall_forecast,
                    get_reservoir_useful_capacity,
                    get_reservoir_max_useful_capacity,
                    get_initial_levels_and_volumes,
                    get_daily_rainfall_history,
                    get_monthly_rainfall
                )

                # Lấy dự báo lượng mưa 7 ngày cho Sông Hinh
                rainfall_forecast = get_rainfall_forecast(lat=12.92684, lon=108.946392)

                # Lấy mực nước & dung tích đầu kỳ
                init_data = get_initial_levels_and_volumes('songhinh', target_year, target_month)
                H_dau, V_dau = init_data.get('songhinh', (204.85, 220.0))

                # Tính lượng mưa tháng trước để xác định độ ẩm đất và hệ số hiệu chỉnh lưu lượng về (soil moisture scaling)
                compare_year = target_year - 1 if target_month == 1 else target_year
                compare_year_analog = closest_year - 1 if target_month == 1 else closest_year
                
                R_cur = get_monthly_rainfall('songhinh', compare_year, compare_month)
                R_ana = get_monthly_rainfall('songhinh', compare_year_analog, compare_month)
                
                ratio = R_cur / R_ana if R_ana > 0.0 else 1.0
                wetness_factor = 1.0 + (ratio - 1.0) * 0.2
                wetness_factor = max(0.8, min(1.3, wetness_factor))

                result += f"""#### 📅 Dự báo chi tiết từng ngày - Sông Hinh
**Dựa trên dữ liệu tháng:** {target_month}/{closest_year}

> [!NOTE]
> **Hiệu chỉnh độ ẩm lưu vực (Soil Moisture Scaling):**
> * Lượng mưa lũy kế tháng trước ({compare_month:02d}/{compare_year}): **{R_cur:.1f} mm** (thực tế đo được)
> * Lượng mưa lũy kế tháng trước năm tương đồng ({compare_month:02d}/{compare_year_analog}): **{R_ana:.1f} mm**
> * Hệ số hiệu chỉnh lưu lượng về (Qve): **{wetness_factor:.2f}** (lưu lượng về lịch sử được nhân với hệ số này trước khi hiệu chỉnh theo dự báo mưa)

"""

                # Lấy dữ liệu chi tiết từng ngày của năm được chọn (tháng dự báo)
                qve_by_day, commercial_by_day = get_daily_data_for_month(
                    manager, closest_year, target_month
                )

                # Chuyển đổi sang dict để tra cứu
                qve_dict = dict(qve_by_day)
                commercial_dict = dict(commercial_by_day)
                
                # Lấy lượng mưa hàng ngày lịch sử của năm tương đồng
                analog_daily_rain = get_daily_rainfall_history('songhinh', closest_year, target_month)

                # Lấy số ngày trong tháng dự báo
                import calendar
                last_day_forecast = calendar.monthrange(target_year, target_month)[1]

                # Tạo bảng dữ liệu từng ngày (chỉ hiển thị ngày có dữ liệu)
                result += f"| Ngày | Qve (m3/s) | Lượng mưa lịch sử ({closest_year}) (mm) | Dự báo lượng mưa (mm) | Sản lượng (kWh) |\n"
                result += "|------:|-----------:|---------------------------:|----------------------:|---------------:|\n"

                total_commercial = 0.0
                qve_values = []
                forecast_chart_data = []

                for day in range(1, last_day_forecast + 1):
                    qve_val = qve_dict.get(day, "-")
                    commercial_val = commercial_dict.get(day, "-")

                    # Bỏ qua dòng nếu cả hai đều không có dữ liệu
                    if qve_val == "-" and commercial_val == "-":
                        continue

                    # Dự báo mưa cho ngày này
                    date_str = f"{target_year}-{target_month:02d}-{day:02d}"
                    rain_val = rainfall_forecast.get(date_str, 0.0)
                    rain_display = f"{rain_val:.1f}" if date_str in rainfall_forecast else "-"

                    # Lấy lượng mưa lịch sử của ngày này ở năm tương đồng
                    hist_rain_val = analog_daily_rain.get(day, 0.0)
                    hist_rain_display = f"{hist_rain_val:.1f}"

                    # Hiệu chỉnh Qve dựa trên hệ số độ ẩm đất và lượng mưa dự báo
                    if isinstance(qve_val, (int, float)):
                        qve_val = qve_val * wetness_factor
                        factor = 1.0
                        if rain_val >= 35.0:
                            factor = 2.0
                        elif rain_val >= 15.0:
                            factor = 1.5
                        elif rain_val >= 5.0:
                            factor = 1.2
                        qve_val = qve_val * factor
                        qve_values.append(qve_val)

                    # Hiển thị ngày đầy đủ
                    day_display = f"{day}/{target_month}/{target_year}"

                    qve_str = f"{qve_val:.2f}" if isinstance(qve_val, (int, float)) else "-"
                    commercial_str = (
                        f"{commercial_val:,.0f}"
                        if isinstance(commercial_val, (int, float))
                        else "-"
                    )

                    if isinstance(commercial_val, (int, float)):
                        total_commercial += commercial_val

                    result += f"| {day_display} | {qve_str} | {hist_rain_display} | {rain_display} | {commercial_str} |\n"

                    forecast_chart_data.append({
                        "Ngay": f"{day}/{target_month}",
                        "Qve": round(qve_val, 2) if isinstance(qve_val, (int, float)) else 0.0,
                        "SanLuong": round(commercial_val, 0) if isinstance(commercial_val, (int, float)) else 0.0
                    })

                # Thêm hàng tổng/trung bình
                STH = 2.74
                Total_Time = 86400
                avg_qve = sum(qve_values) / len(qve_values) if qve_values else 0.0
                total_Qcm = (total_commercial * STH) / (Total_Time * last_day_forecast)
                total_V = ((total_Qcm - avg_qve) * Total_Time * last_day_forecast) / 1000000
                
                # Tính toán dung tích cuối kỳ
                V_cuoi = V_dau - total_V
                V_max = get_reservoir_max_useful_capacity('songhinh')

                result += (
                    f"| **Trung bình/Tổng** | **{avg_qve:.2f}** | **-** | **-** | "
                    f"**{total_commercial:,.0f}** |\n"
                )


                # Tạo thông báo cảnh báo vận hành
                if V_cuoi > V_max:
                    alert_str = f"""> [!WARNING]
> **Cảnh báo nguy cơ xả lũ:** Dung tích hữu ích cuối tháng dự kiến đạt **{V_cuoi:.2f} triệu m3**, vượt quá dung tích hữu ích tối đa (**{V_max:.2f} triệu m3**). Nhà máy có nguy cơ phải xả tràn. Đề xuất tăng sản lượng phát điện để hạ bớt mực nước hồ.
"""
                elif V_cuoi < 0.0:
                    alert_str = f"""> [!CAUTION]
> **Cảnh báo thiếu hụt nước:** Dung tích hữu ích cuối tháng dự kiến âm (**{V_cuoi:.2f} triệu m3**). Lượng nước về và dung tích đầu kỳ không đủ đáp ứng sản lượng phát điện dự báo. Yêu cầu giảm sản lượng phát điện để giữ mực nước hồ an toàn.
"""
                else:
                    alert_str = f"""> [!NOTE]
> **Trạng thái hồ chứa an toàn:** Dung tích hữu ích cuối kỳ dự kiến đạt **{V_cuoi:.2f} triệu m3** (nằm trong giới hạn vận hành an toàn từ 0.0 đến **{V_max:.2f} triệu m3**).
"""

            # Kết luận dự báo (sau bảng)
            result += f"""---

#### 🔮 Kết luận dự báo

**Tháng so sánh:** {compare_month}/{closest_year}
**Mực nước & dung tích hữu ích đầu kỳ:** H_đầu = **{H_dau:.2f} m**, V_đầu = **{V_dau:.2f} triệu m3**
**Qve dự báo trung bình:** **{avg_qve:.2f} m3/s**
**Qcm dự báo trung bình:** **{total_Qcm:.2f} m3/s** *(Suất tiêu hao: {STH} m3/kWh)*
**Thể tích tiêu thụ dự báo (phát điện - nước về):** **{total_V:.2f} triệu m3**
**Dung tích hữu ích cuối kỳ dự kiến:** **{V_cuoi:.2f} triệu m3**

{alert_str}

**Sản lượng dự báo:** {total_commercial:,.0f} kWh
**(Tổng sản lượng từ bảng chi tiết)**
"""

            # Tự động vẽ đồ thị
            if forecast_chart_data:
                qve_chart_json = {
                    "type": "line",
                    "title": f"Biểu đồ dự báo Qve hàng ngày tháng {target_month}/{target_year}",
                    "data": forecast_chart_data,
                    "xKey": "Ngay",
                    "yKeys": ["Qve"],
                    "colors": ["#10b981"],
                    "unit": " m3/s"
                }
                output_chart_json = {
                    "type": "bar",
                    "title": f"Biểu đồ dự báo Sản lượng hàng ngày tháng {target_month}/{target_year}",
                    "data": forecast_chart_data,
                    "xKey": "Ngay",
                    "yKeys": ["SanLuong"],
                    "colors": ["#3b82f6"],
                    "unit": " kWh"
                }
                import json
                result += f"\n\n```chart\n{json.dumps(qve_chart_json, ensure_ascii=False, indent=2)}\n```\n"
                result += f"\n\n```chart\n{json.dumps(output_chart_json, ensure_ascii=False, indent=2)}\n```\n"

            result += """---

**Lưu ý:**
**Để có dự báo chính xác hơn, cần xem xét nhiều yếu tố như: lượng mưa dự báo thực tế, mực nước hồ hiện tại, kế hoạch vận hành.**
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

| Năm | Qve trung bình cả năm (m3/s) |
|:---:|---:|
"""

            for yr, qv in sorted(qve_data, key=lambda x: -x[0]):
                marker = " ← Gần nhất với trung bình" if yr == closest_year else ""
                result += f"| {yr} | {qv:.2f}{marker} |\n"

            # Tự động vẽ đồ thị Qve trung bình các năm liền kề
            year_chart_data = []
            for yr, qv in sorted(qve_data, key=lambda x: x[0]):
                year_chart_data.append({
                    "Nam": str(yr),
                    "Qve_TB": round(qv, 2)
                })

            year_chart_json = {
                "type": "bar",
                "title": "Biểu đồ so sánh Qve trung bình các năm liền kề",
                "data": year_chart_data,
                "xKey": "Nam",
                "yKeys": ["Qve_TB"],
                "colors": ["#3b82f6"],
                "unit": " m3/s"
            }
            import json
            result += f"\n\n```chart\n{json.dumps(year_chart_json, ensure_ascii=False, indent=2)}\n```\n"

            result += f"""
**Trung bình Qve cả năm:** {avg_qve:.2f} m3/s
**Năm được chọn để dự báo:** {closest_year} (Qve = {forecast_qve:.2f} m3/s)

---

#### 🔮 Dự báo cho năm {target_year}

**Qve dự báo:** {forecast_qve:.2f} m3/s
*(Dựa trên Qve năm {closest_year})*

---

**Lưu ý:**
**Để có dự báo chính xác hơn, cần xem xét nhiều yếu tố như: lượng mưa dự báo, mực nước hồ, kế hoạch vận hành.**


"""
            return result.strip()

        except Exception as e:
            return f"### Lỗi dự báo\n\n{str(e)}"