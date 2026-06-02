"""
Hierarchical statistics service - Get hierarchical statistics for Vĩnh Sơn
"""
# Non-breaking space: giữ Min/Max/Avg trên một dòng khi render Markdown
_NBSP = "\u00a0"

from datetime import datetime, timedelta
from typing import Optional, List, Any, Tuple
import json
from ..config.settings import GS_CONFIG
from ..core.stats_export_client import get_stats_export_client
from ..core.retry import retry_with_backoff
from ..utils.numbers import safe_cell, parse_float_loose


class HierarchicalStatisticsService:
    """Service for hierarchical statistics (Qve, water level)"""

    def __init__(self):
        pass

    def get_hierarchical_statistics(
        self,
        period_type: str,
        period_value: Optional[str] = None,
        reservoir: str = "All",
        parameters: Optional[List[str]] = None,
        compare: bool = False,
        compare_years: int = 1,
        compare_with_period_value: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        _is_subcall: bool = False,
        _accumulators: Optional[dict] = None
    ) -> str:
        """
        Thống kê phân cấp Qve và Mực nước hồ theo năm/tháng/tuần cho Vĩnh Sơn.
        Hỗ trợ date range: nếu có start_date va end_date, trả về thống kê theo ngày.
        """
        # Khởi tạo accumulator ở root call
        if _accumulators is None:
            _accumulators = {"charts": [], "excel_sheets": [], "conclusions": []}
            is_root_call = True
        else:
            is_root_call = False
            _accumulators.setdefault("conclusions", [])

        result_text = self._get_hierarchical_statistics_impl(
            period_type=period_type,
            period_value=period_value,
            reservoir=reservoir,
            parameters=parameters,
            compare=compare,
            compare_years=compare_years,
            compare_with_period_value=compare_with_period_value,
            start_date=start_date,
            end_date=end_date,
            _is_subcall=_is_subcall,
            _accumulators=_accumulators
        )

        if is_root_call:
            charts = _accumulators.get("charts", [])
            excel_sheets = _accumulators.get("excel_sheets", [])
            conclusions = _accumulators.get("conclusions", [])

            # Format phần kết luận
            conclusion_block = ""
            if conclusions:
                conclusion_block = "\n\n### 📌 Kết luận Phân tích So sánh\n\n" + "\n\n".join(conclusions) + "\n\n"

            chart_blocks = []
            for chart_json in charts:
                chart_blocks.append(f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n")
            chart_text = "".join(chart_blocks)

            excel_block = ""
            if excel_sheets:
                filename = "bao-cao-thong-ke-vinh-son.xlsx"
                title = "Báo cáo thống kê Vĩnh Sơn"
                if period_type == "year":
                    y_val = period_value or datetime.now().year
                    filename = f"bao-cao-thong-ke-nam-vinh-son-{y_val}.xlsx"
                    title = f"Báo cáo thống kê năm {y_val} - Vĩnh Sơn"
                elif period_type == "month":
                    m_val = (period_value or f"{datetime.now().month}/{datetime.now().year}").replace("/", "-")
                    filename = f"bao-cao-thong-ke-thang-vinh-son-{m_val}.xlsx"
                    title = f"Báo cáo thống kê tháng {m_val} - Vĩnh Sơn"
                elif period_type == "week":
                    w_val = (period_value or f"{(datetime.now().day - 1) // 7 + 1}/{datetime.now().month}/{datetime.now().year}").replace("/", "-")
                    filename = f"bao-cao-thong-ke-tuan-vinh-son-{w_val}.xlsx"
                    title = f"Báo cáo thống kê tuần {w_val} - Vĩnh Sơn"
                elif start_date and end_date:
                    sd_fn = start_date.replace("/", "-")
                    ed_fn = end_date.replace("/", "-")
                    filename = f"bao-cao-thong-ke-ngay-vinh-son-{sd_fn}-den-{ed_fn}.xlsx"
                    title = f"Báo cáo thống kê từ {start_date} đến {end_date} - Vĩnh Sơn"

                excel_json = {
                    "title": title,
                    "fileName": filename,
                    "prompt": "Bạn có cần xuất file Excel thống kê này không?",
                    "sheets": excel_sheets
                }
                excel_block = f"\n\n```excel\n{json.dumps(excel_json, ensure_ascii=False, indent=2)}\n```\n"

            return result_text + conclusion_block + chart_text + excel_block
        else:
            return result_text

    def _get_hierarchical_statistics_impl(
        self,
        period_type: str,
        period_value: Optional[str] = None,
        reservoir: str = "All",
        parameters: Optional[List[str]] = None,
        compare: bool = False,
        compare_years: int = 1,
        compare_with_period_value: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        _is_subcall: bool = False,
        _accumulators: Optional[dict] = None
    ) -> str:
        print(f"[INFO] VINH SON TOOL: Hierarchical statistics impl - {period_type} {period_value}, reservoir={reservoir}, parameters={parameters}, compare={compare}, compare_years={compare_years}, compare_with_period_value={compare_with_period_value}, start_date={start_date}, end_date={end_date}", flush=True)

        if not parameters:
            parameters = ["qve", "water_level"]

        # Xử lý date range
        if start_date and end_date:
            if reservoir == "All" or reservoir is None:
                return self._get_date_range_statistics_combined(
                    start_date, end_date, parameters, _accumulators
                )
            else:
                return self._get_date_range_statistics(
                    start_date, end_date, reservoir, parameters, _accumulators
                )

        # Xử lý đặc biệt cho reservoir="All"
        if reservoir == "All" or reservoir is None:
            if period_type == "year":
                if compare:
                    results = []
                    for res in ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"]:
                        res_result = self.get_hierarchical_statistics(
                            period_type, period_value, res, parameters, compare, compare_years,
                            compare_with_period_value=compare_with_period_value, start_date=start_date, end_date=end_date,
                            _is_subcall=True, _accumulators=_accumulators
                        )
                        results.append(res_result)
                    return "\n\n".join(results)
                else:
                    return self._get_all_reservoirs_year_stats(period_value, parameters, compare, compare_years, _accumulators)
            elif period_type == "month":
                if compare or compare_with_period_value:
                    results = []
                    for res in ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"]:
                        res_result = self.get_hierarchical_statistics(
                            period_type, period_value, res, parameters, compare, compare_years,
                            compare_with_period_value=compare_with_period_value, start_date=start_date, end_date=end_date,
                            _is_subcall=True, _accumulators=_accumulators
                        )
                        results.append(res_result)
                    return "\n\n".join(results)
                else:
                    return self._get_month_all_reservoirs(period_value, parameters, _accumulators)
            elif period_type == "week":
                results = []
                for res in ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"]:
                    res_result = self.get_hierarchical_statistics(
                        period_type, period_value, res, parameters, compare, compare_years,
                        compare_with_period_value=compare_with_period_value, start_date=start_date, end_date=end_date,
                        _is_subcall=True, _accumulators=_accumulators
                    )
                    results.append(res_result)
                return "\n\n" + "="*80 + "\n\n".join(results)
            else:
                return f"Lỗi: Loại khoảng thời gian không hợp lệ: {period_type}. Sử dụng 'year', 'month', hoặc 'week'."

        # Xử lý cho từng hồ riêng lẻ (reservoir != "All")
        try:
            client, spreadsheet = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets thống kê."

            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title or "Thống kê tháng" in ws.title:
                    stats_ws = ws
                    break
            if not stats_ws and worksheets:
                stats_ws = worksheets[0]
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê trong Google Sheets thống kê."

            def fetch_data():
                return stats_ws.get_all_values()

            all_data = retry_with_backoff(fetch_data, max_retries=3, initial_delay=1)
            if len(all_data) < 8:
                return "Không có dữ liệu trong Google Sheets thống kê"

            data_start_row = 0
            for i, row in enumerate(all_data):
                if len(row) > 0:
                    first_cell = str(row[0]).strip()
                    if '/' in first_cell and any(char.isdigit() for char in first_cell):
                        parts = first_cell.split('/')
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                            data_start_row = i
                            break
            if data_start_row == 0:
                data_start_row = 7 if len(all_data) > 7 else 1

            data_rows = all_data[data_start_row:] if len(all_data) > data_start_row else []

            col_date = 0
            if reservoir == "Vinh Son -A":
                col_qve = 4
                col_water_level = 1
            elif reservoir == "Vinh Son -B":
                col_qve = 5
                col_water_level = 2
            elif reservoir == "Vinh Son -C":
                col_qve = 6
                col_water_level = 3
            else:
                col_qve = 4
                col_water_level = 1

            col_qve_a, col_qve_b, col_qve_c = 4, 5, 6
            col_water_a, col_water_b, col_water_c = 1, 2, 3

            def normalize_date(date_str):
                if not date_str:
                    return None
                try:
                    parts = str(date_str).strip().split('/')
                    if len(parts) == 3:
                        day, month, year_str = parts
                        year = int(year_str)
                        if year < 100:
                            year = 2000 + year if year < 50 else 1900 + year
                        return datetime(year, int(month), int(day))
                    if '-' in str(date_str):
                        return datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
                except (ValueError, AttributeError):
                    pass
                return None

            def extract_value(row, col_idx):
                if col_idx is None or len(row) <= col_idx:
                    return None
                try:
                    val_str = str(row[col_idx]).strip().replace(',', '.')
                    if val_str:
                        return float(val_str)
                except:
                    pass
                return None

            now = datetime.now()
            current_year = now.year
            current_month = now.month
            current_week = (now.day - 1) // 7 + 1

            excel_sheets = _accumulators.get("excel_sheets", []) if _accumulators is not None else []
            charts = _accumulators.get("charts", []) if _accumulators is not None else []
            conclusions = _accumulators.get("conclusions", []) if _accumulators is not None else []

            sheet_title = reservoir.replace("Vinh Son -", "Ho ")
            excel_rows = []

            if period_type == "year":
                year = int(period_value) if period_value else current_year
                if compare:
                    n_compare = min(max(compare_years, 1), 5)
                    years_to_compare = [year]
                    for i in range(1, n_compare + 1):
                        years_to_compare.append(year - i)
                    years_to_compare.sort(reverse=True)
                else:
                    years_to_compare = [year]

                result = f"""### 📊 Thống kê theo Tháng - Thủy điện Vĩnh Sơn
**Hồ:** {reservoir}
**Năm:** {year}"""
                if compare and len(years_to_compare) > 1:
                    if len(years_to_compare) == 2:
                        result += f"\n**So sánh với:** {years_to_compare[1]}"
                    else:
                        result += f"\n**So sánh với {len(years_to_compare) - 1} năm liền kề:** {', '.join(map(str, years_to_compare[1:]))}"
                result += "\n\n---\n\n"

                for param in parameters:
                    col_idx = col_qve if param == "qve" else col_water_level
                    if col_idx is None:
                        continue
                    param_name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                    result += f"\n#### {param_name}\n\n"

                    excel_rows.append([f"THỐNG KÊ {param_name.upper()} - {reservoir.upper()}"])
                    excel_rows.append([])

                    if param == "qve":
                        col_a, col_b, col_c = col_qve_a, col_qve_b, col_qve_c
                    else:
                        col_a, col_b, col_c = col_water_a, col_water_b, col_water_c

                    if compare and len(years_to_compare) > 1:
                        if param == "qve":
                            col_a, col_b, col_c = col_qve_a, col_qve_b, col_qve_c
                        else:
                            col_a, col_b, col_c = col_water_a, col_water_b, col_water_c

                        current_res = reservoir if reservoir else "All"

                        if current_res == "All" or current_res is None:
                            header_cols = ["Tháng"]
                            for res in ["A", "B", "C"]:
                                for yr in years_to_compare:
                                    header_cols.append(f"{res} - {yr} (Min/Max/Avg)")
                            result += f"| {' | '.join(header_cols)} |\n"
                            result += "|" + "|".join([":---:"] * len(header_cols)) + "|\n"
                            cols_to_show = [col_a, col_b, col_c]
                        else:
                            res_mapping = {
                                "Vinh Son -A": ("Hồ A", col_a),
                                "Vinh Son -B": ("Hồ B", col_b),
                                "Vinh Son -C": ("Hồ C", col_c),
                            }
                            res_label, res_col = res_mapping.get(current_res, ("Hồ A", col_a))

                            header_cols = ["Tháng"]
                            for yr in years_to_compare:
                                header_cols.append(f"{res_label}-{yr}")
                            result += f"| {' | '.join(header_cols)} |\n"
                            result += "|" + "|".join([":---:"] * len(header_cols)) + "|\n"
                            cols_to_show = [res_col]
                    else:
                        header_cols = ["Tháng", f"Hồ A - {year}", f"Hồ B - {year}", f"Hồ C - {year}"]
                        result += f"| Tháng | Hồ A - {year} | Hồ B - {year} | Hồ C - {year} |\n"
                        result += "|:---:|:---:|:---:|:---:|\n"
                        cols_to_show = None

                    excel_rows.append(header_cols)

                    chart_data = []

                    for month in range(1, 13):
                        row_data = [f"**Tháng {month}**"]
                        chart_item = {"Thang": f"Tháng {month}"}
                        if compare and len(years_to_compare) > 1:
                            for col_idx_show in cols_to_show:
                                for yr in years_to_compare:
                                    month_values = []
                                    for row in data_rows:
                                        if len(row) > col_idx_show:
                                            date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                            if date and date.year == yr and date.month == month:
                                                val = extract_value(row, col_idx_show)
                                                if val is not None:
                                                    month_values.append(val)
                                    if month_values:
                                        min_val = min(month_values)
                                        max_val = max(month_values)
                                        avg_val = sum(month_values) / len(month_values)
                                        row_data.append(f"{min_val:.2f}{_NBSP}/{_NBSP}{max_val:.2f}{_NBSP}/{_NBSP}{avg_val:.2f}")
                                        chart_item[str(yr)] = round(avg_val, 2)
                                    else:
                                        row_data.append("-")
                                        chart_item[str(yr)] = 0.0
                        else:
                            for col_idx_show in [col_a, col_b, col_c]:
                                month_values = []
                                for row in data_rows:
                                    if len(row) > col_idx_show:
                                        date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                        if date and date.year == year and date.month == month:
                                            val = extract_value(row, col_idx_show)
                                            if val is not None:
                                                month_values.append(val)
                                if month_values:
                                    min_val = min(month_values)
                                    max_val = max(month_values)
                                    avg_val = sum(month_values) / len(month_values)
                                    row_data.append(f"{min_val:.2f}{_NBSP}/{_NBSP}{max_val:.2f}{_NBSP}/{_NBSP}{avg_val:.2f}")
                                else:
                                    row_data.append("-")
                        result += f"| {' | '.join(row_data)} |\n"
                        excel_rows.append([cell.replace("**", "") for cell in row_data])
                        chart_data.append(chart_item)

                    # Thêm hàng trung bình cả năm
                    avg_row = ["**Trung bình**"]
                    year_avgs = {}
                    if compare and len(years_to_compare) > 1:
                        for col_idx_show in cols_to_show:
                            for yr in years_to_compare:
                                year_values = []
                                for m in range(1, 13):
                                    for row in data_rows:
                                        if len(row) > col_idx_show:
                                            date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                            if date and date.year == yr and date.month == m:
                                                val = extract_value(row, col_idx_show)
                                                if val is not None:
                                                    year_values.append(val)
                                if year_values:
                                    avg_val = sum(year_values) / len(year_values)
                                    avg_row.append(f"{avg_val:.2f}")
                                    year_avgs[yr] = avg_val
                                else:
                                    avg_row.append("-")
                    else:
                        for col_idx_show in [col_a, col_b, col_c]:
                            year_values = []
                            for m in range(1, 13):
                                for row in data_rows:
                                    if len(row) > col_idx_show:
                                        date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                        if date and date.year == year and date.month == m:
                                            val = extract_value(row, col_idx_show)
                                            if val is not None:
                                                year_values.append(val)
                            if year_values:
                                avg_val = sum(year_values) / len(year_values)
                                avg_row.append(f"{avg_val:.2f}")
                            else:
                                avg_row.append("-")
                    result += f"| {' | '.join(avg_row)} |\n"
                    excel_rows.append([cell.replace("**", "") for cell in avg_row])
                    excel_rows.append([])

                    # Sinh kết luận tự động so sánh năm
                    if compare and len(years_to_compare) > 1 and year in year_avgs:
                        cur_avg = year_avgs[year]
                        param_conclusions = []
                        for yr in years_to_compare:
                            if yr == year or yr not in year_avgs:
                                continue
                            prev_avg = year_avgs[yr]
                            avg_change = cur_avg - prev_avg
                            avg_pct = (avg_change / prev_avg * 100) if prev_avg > 0 else 0
                            direction = "tăng" if avg_change > 0 else "giảm"
                            param_conclusions.append(f"  - **So với năm {yr}**: {direction} `{abs(avg_change):.2f}` ({avg_pct:+.1f}%) (trung bình `{prev_avg:.2f}`).")
                        
                        if param_conclusions:
                            lbl_map = {"Vinh Son -A": "Hồ A", "Vinh Son -B": "Hồ B", "Vinh Son -C": "Hồ C"}
                            res_label = lbl_map.get(reservoir, reservoir)
                            conclusions.append(f"**{res_label} - {param_name.split(' (')[0]} năm {year} (trung bình `{cur_avg:.2f}`):**\n" + "\n".join(param_conclusions))

                    # Thêm Chart JSON
                    chart_json = {
                        "type": "line" if param == "water_level" else "bar",
                        "title": f"Biểu đồ {param_name.split(' (')[0]} - {reservoir} qua các năm",
                        "data": chart_data,
                        "xKey": "Thang",
                        "yKeys": [str(yr) for yr in years_to_compare],
                        "colors": ["#3b82f6", "#10b981", "#ef4444", "#f59e0b", "#06b6d4"],
                        "unit": " m" if param == "water_level" else " m³/s"
                    }
                    charts.append(chart_json)

                    result += "\n---\n"

                if _accumulators is not None:
                    _merge_sheet(excel_sheets, sheet_title, excel_rows, f"BẢO CÁO THỐNG KÊ CHI TIẾT - {reservoir.upper()}")

                return result.strip()

            elif period_type == "month":
                if period_value and "/" in period_value:
                    m_s, y_s = period_value.split("/")
                    month, year = int(m_s), int(y_s)
                else:
                    month, year = current_month, current_year

                import calendar
                last_day = calendar.monthrange(year, month)[1]

                if compare or compare_with_period_value:
                    if compare_with_period_value and "/" in str(compare_with_period_value):
                        try:
                            _, y2_s = compare_with_period_value.strip().split("/")
                            year2 = int(y2_s)
                            years_to_compare = [year, year2]
                            years_to_compare = sorted(list(set(years_to_compare)), reverse=True)
                        except ValueError:
                            years_to_compare = [year]
                    else:
                        n_compare = min(max(compare_years, 1), 5)
                        years_to_compare = [year]
                        for i in range(1, n_compare + 1):
                            years_to_compare.append(year - i)
                        years_to_compare.sort(reverse=True)
                else:
                    years_to_compare = [year]

                result = f"""### 📊 Thống kê tháng {month}/{year} - Thủy điện Vĩnh Sơn
**Hồ:** {reservoir}
**Tháng:** {month}/{year} (từ ngày 1 đến ngày {last_day})"""
                if compare and len(years_to_compare) > 1:
                    if len(years_to_compare) == 2:
                        result += f"\n**So sánh với:** {years_to_compare[1]}"
                    else:
                        result += f"\n**So sánh với {len(years_to_compare) - 1} năm liền kề:** {', '.join(map(str, years_to_compare[1:]))}"
                result += "\n\n---\n\n"

                for param in parameters:
                    col_idx = col_qve if param == "qve" else col_water_level
                    if col_idx is None:
                        continue
                    param_name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                    result += f"\n#### {param_name}\n\n"

                    excel_rows.append([f"THỐNG KÊ {param_name.upper()} THÁNG {month}/{year} - {reservoir.upper()}"])
                    excel_rows.append([])

                    chart_data = []

                    if compare and len(years_to_compare) > 1:
                        res_label = "Hồ"
                        if reservoir == "Vinh Son -A":
                            res_label = "Hồ A"
                        elif reservoir == "Vinh Son -B":
                            res_label = "Hồ B"
                        elif reservoir == "Vinh Son -C":
                            res_label = "Hồ C"

                        header_cols = ["Ngày"]
                        for yr in years_to_compare:
                            header_cols.append(f"{res_label}-{yr}")
                        result += f"| {' | '.join(header_cols)} |\n"
                        result += "|" + "|".join([":---:"] * len(header_cols)) + "|\n"
                        excel_rows.append(header_cols)

                        for day in range(1, last_day + 1):
                            row_data = [f"**{day}**"]
                            chart_item = {"Ngay": str(day)}
                            for yr in years_to_compare:
                                day_values = []
                                for row in data_rows:
                                    if len(row) > col_idx:
                                        date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                        if date and date.year == yr and date.month == month and date.day == day:
                                            val = extract_value(row, col_idx)
                                            if val is not None:
                                                day_values.append(val)
                                if day_values:
                                    avg_val = sum(day_values) / len(day_values)
                                    row_data.append(f"{avg_val:.2f}")
                                    chart_item[str(yr)] = round(avg_val, 2)
                                else:
                                    row_data.append("-")
                                    chart_item[str(yr)] = 0.0
                            result += f"| {' | '.join(row_data)} |\n"
                            excel_rows.append([cell.replace("**", "") for cell in row_data])
                            chart_data.append(chart_item)

                        # Hàng trung bình tháng
                        avg_row = ["**Trung bình**"]
                        month_avgs = {}
                        for yr in years_to_compare:
                            month_values = []
                            for d in range(1, last_day + 1):
                                for row in data_rows:
                                    if len(row) > col_idx:
                                        date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                        if date and date.year == yr and date.month == month and date.day == d:
                                            val = extract_value(row, col_idx)
                                            if val is not None:
                                                month_values.append(val)
                            if month_values:
                                avg_val = sum(month_values) / len(month_values)
                                avg_row.append(f"{avg_val:.2f}")
                                month_avgs[yr] = avg_val
                            else:
                                avg_row.append("-")
                        result += f"| {' | '.join(avg_row)} |\n"
                        excel_rows.append([cell.replace("**", "") for cell in avg_row])
                        excel_rows.append([])

                        # Sinh kết luận tự động so sánh tháng
                        if compare and len(years_to_compare) > 1 and year in month_avgs:
                            cur_avg = month_avgs[year]
                            param_conclusions = []
                            for yr in years_to_compare:
                                if yr == year or yr not in month_avgs:
                                    continue
                                prev_avg = month_avgs[yr]
                                avg_change = cur_avg - prev_avg
                                avg_pct = (avg_change / prev_avg * 100) if prev_avg > 0 else 0
                                direction = "tăng" if avg_change > 0 else "giảm"
                                param_conclusions.append(f"  - **So với tháng {month}/{yr}**: {direction} `{abs(avg_change):.2f}` ({avg_pct:+.1f}%) (trung bình `{prev_avg:.2f}`).")
                            
                            if param_conclusions:
                                lbl_map = {"Vinh Son -A": "Hồ A", "Vinh Son -B": "Hồ B", "Vinh Son -C": "Hồ C"}
                                res_label = lbl_map.get(reservoir, reservoir)
                                conclusions.append(f"**{res_label} - {param_name.split(' (')[0]} tháng {month}/{year} (trung bình `{cur_avg:.2f}`):**\n" + "\n".join(param_conclusions))

                        # Chart so sánh tháng
                        chart_json = {
                            "type": "line",
                            "title": f"So sánh {param_name.split(' (')[0]} - {reservoir} tháng {month} qua các năm",
                            "data": chart_data,
                            "xKey": "Ngay",
                            "yKeys": [str(yr) for yr in years_to_compare],
                            "colors": ["#3b82f6", "#10b981", "#ef4444", "#f59e0b", "#06b6d4"],
                            "unit": " m" if param == "water_level" else " m³/s"
                        }
                        charts.append(chart_json)
                    else:
                        result += f"| Tháng {month}/{year} (Min/Max/Avg) |\n"
                        result += "|:---:|\n"
                        excel_rows.append([f"Tháng {month}/{year} (Min/Max/Avg)"])

                        vals = []
                        day_vals = []
                        for row in data_rows:
                            if len(row) > col_idx:
                                date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                if date and date.year == year and date.month == month and 1 <= date.day <= last_day:
                                    val = extract_value(row, col_idx)
                                    if val is not None:
                                        vals.append(val)
                                        day_vals.append((date.day, val))
                        if vals:
                            avg_val = sum(vals)/len(vals)
                            min_val = min(vals)
                            max_val = max(vals)
                            result += f"| {min_val:.2f}{_NBSP}/{_NBSP}{max_val:.2f}{_NBSP}/{_NBSP}{avg_val:.2f} |\n"
                            excel_rows.append([f"{min_val:.2f}/{max_val:.2f}/{avg_val:.2f}"])
                        else:
                            result += "| -\n"
                            excel_rows.append(["-"])
                        excel_rows.append([])

                        day_vals.sort()
                        chart_data = [{"Ngay": str(d), "GiaTri": round(v, 2)} for d, v in day_vals]
                        if chart_data:
                            chart_json = {
                                "type": "line",
                                "title": f"Biểu đồ diễn biến {param_name.split(' (')[0]} hàng ngày tháng {month}/{year} - {reservoir}",
                                "data": chart_data,
                                "xKey": "Ngay",
                                "yKeys": ["GiaTri"],
                                "colors": ["#3b82f6"],
                                "unit": " m" if param == "water_level" else " m³/s"
                            }
                            charts.append(chart_json)

                    result += "\n---\n"

                if _accumulators is not None:
                    _merge_sheet(excel_sheets, sheet_title, excel_rows, f"BẢO CÁO THỐNG KÊ CHI TIẾT - {reservoir.upper()}")

                return result.strip()

            elif period_type == "week":
                if period_value and period_value.count("/") == 2:
                    w_s, m_s, y_s = period_value.split("/")
                    week_num, month, year = int(w_s), int(m_s), int(y_s)
                else:
                    week_num, month, year = current_week, current_month, current_year

                week_ranges = {1: (1, 7), 2: (8, 14), 3: (15, 21), 4: (22, 28), 5: (29, 31)}
                sd, ed = week_ranges.get(week_num, (1, 7))

                result = f"""### 📊 Thống kê theo Ngày - Thủy điện Vĩnh Sơn
**Hồ:** {reservoir}
**Tuần {week_num} tháng {month}/{year}** (ngày {sd}-{ed})

---

"""
                for param in parameters:
                    col_idx = col_qve if param == "qve" else col_water_level
                    if col_idx is None:
                        continue
                    param_name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                    unit = "m³/s" if param == "qve" else "m"
                    result += f"\n#### {param_name}\n\n"
                    result += f"| Ngày | Giá trị ({unit}) |\n"
                    result += "|---|---:|\n"

                    excel_rows.append([f"THỐNG KÊ {param_name.upper()} TUẦN {week_num} THÁNG {month}/{year} - {reservoir.upper()}"])
                    excel_rows.append([])
                    excel_rows.append(["Ngày", f"Giá trị ({unit})"])

                    chart_data = []
                    week_values = []

                    for d in range(sd, min(ed + 1, 32)):
                        value_str = "-"
                        val = None
                        for row in data_rows:
                            if len(row) > col_idx:
                                date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                if date and date.year == year and date.month == month and date.day == d:
                                    val = extract_value(row, col_idx)
                                    if val is not None:
                                        value_str = f"{val:.2f}"
                                        week_values.append(val)
                                    break
                        result += f"| **{d}/{month}** | {value_str} |\n"
                        excel_rows.append([f"{d}/{month}", val if val is not None else "-"])
                        chart_data.append({
                            "Ngay": f"{d}/{month}",
                            "GiaTri": val if val is not None else 0.0
                        })

                    avg_val = sum(week_values) / len(week_values) if week_values else None
                    avg_str = f"{avg_val:.2f}" if avg_val is not None else "-"
                    result += f"| **Trung bình** | {avg_str} |\n"
                    excel_rows.append(["Trung bình", avg_val if avg_val is not None else "-"])
                    excel_rows.append([])

                    chart_json = {
                        "type": "bar" if param == "qve" else "line",
                        "title": f"Biểu đồ {param_name.split(' (')[0]} tuần {week_num} tháng {month}/{year} - {reservoir}",
                        "data": chart_data,
                        "xKey": "Ngay",
                        "yKeys": ["GiaTri"],
                        "colors": ["#3b82f6"],
                        "unit": f" {unit}"
                    }
                    charts.append(chart_json)

                    result += "\n---\n"

                if _accumulators is not None:
                    _merge_sheet(excel_sheets, sheet_title, excel_rows, f"BẢO CÁO THỐNG KÊ CHI TIẾT - {reservoir.upper()}")

                return result.strip()

            else:
                return f"Lỗi: Loại khoảng thời gian không hợp lệ: {period_type}. Sử dụng 'year', 'month', hoặc 'week'."

        except Exception as e:
            error_msg = f"Lỗi khi thống kê phân cấp: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg

    def _get_month_comparison_all_reservoirs(
        self,
        period_value: str,
        compare_with_period_value: Optional[str],
        parameters: List[str],
        compare_years: int = 1
    ) -> str:
        try:
            m1_s, y1_s = period_value.strip().split("/")
            month1, year1 = int(m1_s), int(y1_s)
            if compare_years >= 2:
                periods_to_show = [(month1, year1 - i) for i in range(compare_years + 1)]
            elif compare_with_period_value and "/" in str(compare_with_period_value):
                m2_s, y2_s = compare_with_period_value.strip().split("/")
                month2, year2 = int(m2_s), int(y2_s)
                periods_to_show = [(month1, year1), (month2, year2)]
            else:
                periods_to_show = [(month1, year1)]

            client, spreadsheet = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets thống kê."
            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title or "Thống kê tháng" in ws.title:
                    stats_ws = ws
                    break
            if not stats_ws and worksheets:
                stats_ws = worksheets[0]
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê."
            all_data = retry_with_backoff(lambda: stats_ws.get_all_values(), max_retries=3, initial_delay=1)
            if len(all_data) < 8:
                return "Không có dữ liệu trong Google Sheets thống kê"
            data_start_row = 0
            for i, row in enumerate(all_data):
                if len(row) > 0:
                    first_cell = str(row[0]).strip()
                    if '/' in first_cell and any(c.isdigit() for c in first_cell):
                        parts = first_cell.split('/')
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                            data_start_row = i
                            break
            if data_start_row == 0:
                data_start_row = 7 if len(all_data) > 7 else 1
            data_rows = all_data[data_start_row:] if len(all_data) > data_start_row else []
            col_date = 0

            def normalize_date(date_str):
                if not date_str:
                    return None
                try:
                    parts = str(date_str).strip().split('/')
                    if len(parts) == 3:
                        day, mo, yr_str = parts
                        yr = int(yr_str)
                        if yr < 100:
                            yr = 2000 + yr if yr < 50 else 1900 + yr
                        return datetime(yr, int(mo), int(day))
                    if '-' in str(date_str):
                        return datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
                except (ValueError, AttributeError):
                    pass
                return None

            def extract_value(row, col_idx):
                if col_idx is None or len(row) <= col_idx:
                    return None
                try:
                    v = str(row[col_idx]).strip().replace(',', '.')
                    if v:
                        return float(v)
                except Exception:
                    pass
                return None

            reservoirs = [
                ("Vinh Son -A", 4, 1),
                ("Vinh Son -B", 5, 2),
                ("Vinh Son -C", 6, 3),
            ]
            import calendar
            max_day = 31
            for (m, y) in periods_to_show:
                max_day = max(max_day, calendar.monthrange(y, m)[1])
            parts_out = []

            for res_name, col_qve, col_water in reservoirs:
                period_labels = ", ".join([f"Tháng {m}/{y}" for (m, y) in periods_to_show])
                res_label = res_name.replace("Vinh Son -", "Hồ ")
                block = f"### 📊 So sánh theo Ngày - Thủy điện Vĩnh Sơn\n**Hồ:** {res_name}\n**So sánh:** {period_labels} (từ ngày 1 đến ngày {max_day})\n\n---\n\n"
                for param in parameters or ["qve", "water_level"]:
                    col_idx = col_qve if param == "qve" else col_water
                    param_name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                    block += f"\n#### {param_name} - {res_label}\n\n"
                    header_cols = [f"{res_label} - Tháng {m}/{y}" for (m, y) in periods_to_show]
                    header_row = "| Ngày | " + " | ".join(header_cols) + " |"
                    sep_row = "|:---:|" + "|".join([":---:"] * len(periods_to_show)) + "|"
                    block += header_row + "\n"
                    block += sep_row + "\n"
                    for d in range(1, max_day + 1):
                        cells = [f"**{d}**"]
                        for (m, y) in periods_to_show:
                            vals = []
                            for row in data_rows:
                                if len(row) <= col_idx:
                                    continue
                                date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                if not date or date.year != y or date.month != m or date.day != d:
                                    continue
                                v = extract_value(row, col_idx)
                                if v is not None:
                                    vals.append(v)
                            cells.append(f"{sum(vals)/len(vals):.2f}" if vals else "-")
                        block += "| " + " | ".join(cells) + " |\n"

                    avg_cells = ["**Trung bình**"]
                    for (m, y) in periods_to_show:
                        all_vals = []
                        for d in range(1, max_day + 1):
                            for row in data_rows:
                                if len(row) <= col_idx:
                                    continue
                                date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                if not date or date.year != y or date.month != m or date.day != d:
                                    continue
                                v = extract_value(row, col_idx)
                                if v is not None:
                                    all_vals.append(v)
                        avg_cells.append(f"{sum(all_vals)/len(all_vals):.2f}" if all_vals else "-")
                    block += "| " + " | ".join(avg_cells) + " |\n"
                    block += "\n---\n"
                block += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Vĩnh Sơn"
                parts_out.append(block.strip())

            return (("="*80) + "\n\n").join(parts_out)
        except Exception as e:
            return f"Lỗi: {e}"

    def _get_all_reservoirs_year_stats(
        self,
        period_value: Optional[str],
        parameters: List[str],
        compare: bool,
        compare_years: int,
        _accumulators: Optional[dict] = None
    ) -> str:
        """Thống kê năm cho tất cả 3 hồ (1 bảng với các cột cho 3 hồ)"""
        try:
            client, spreadsheet = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets thống kê."

            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title or "Thống kê tháng" in ws.title:
                    stats_ws = ws
                    break
            if not stats_ws and worksheets:
                stats_ws = worksheets[0]
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê trong Google Sheets thống kê."

            def fetch_data():
                return stats_ws.get_all_values()

            all_data = retry_with_backoff(fetch_data, max_retries=3, initial_delay=1)
            if len(all_data) < 8:
                return "Không có dữ liệu trong Google Sheets thống kê"

            data_start_row = 0
            for i, row in enumerate(all_data):
                if len(row) > 0:
                    first_cell = str(row[0]).strip()
                    if '/' in first_cell and any(char.isdigit() for char in first_cell):
                        parts = first_cell.split('/')
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                            data_start_row = i
                            break
            if data_start_row == 0:
                data_start_row = 7 if len(all_data) > 7 else 1

            data_rows = all_data[data_start_row:] if len(all_data) > data_start_row else []

            col_date = 0
            col_qve_a, col_qve_b, col_qve_c = 4, 5, 6
            col_water_a, col_water_b, col_water_c = 1, 2, 3

            def normalize_date(date_str):
                if not date_str:
                    return None
                try:
                    parts = str(date_str).strip().split('/')
                    if len(parts) == 3:
                        day, month, year_str = parts
                        year = int(year_str)
                        if year < 100:
                            year = 2000 + year if year < 50 else 1900 + year
                        return datetime(year, int(month), int(day))
                    if '-' in str(date_str):
                        return datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
                except (ValueError, AttributeError):
                    pass
                return None

            def extract_value(row, col_idx):
                if col_idx is None or len(row) <= col_idx:
                    return None
                try:
                    val_str = str(row[col_idx]).strip().replace(',', '.')
                    if val_str:
                        return float(val_str)
                except:
                    pass
                return None

            now = datetime.now()
            current_year = now.year
            year = int(period_value) if period_value else current_year

            result = f"""### 📊 Thống kê theo Tháng - Thủy điện Vĩnh Sơn
**Tất cả 3 hồ:** A, B, C
**Năm:** {year}"""
            result += "\n\n---\n\n"

            excel_sheets = _accumulators.get("excel_sheets", []) if _accumulators is not None else []
            charts = _accumulators.get("charts", []) if _accumulators is not None else []

            excel_rows = []

            for param in parameters:
                if param == "qve":
                    param_name = "Lưu lượng về Qve (m³/s)"
                    col_a, col_b, col_c = col_qve_a, col_qve_b, col_qve_c
                elif param == "water_level":
                    param_name = "Mực nước hồ (m)"
                    col_a, col_b, col_c = col_water_a, col_water_b, col_water_c
                else:
                    continue

                result += f"\n#### {param_name}\n\n"

                excel_rows.append([f"THỐNG KÊ NĂM {year} - {param_name.upper()} - TẤT CẢ CÁC HỒ"])
                excel_rows.append([])

                header_row = ["Tháng", f"Hồ A - {year}", f"Hồ B - {year}", f"Hồ C - {year}"]
                result += f"| Tháng | Hồ A - {year} | Hồ B - {year} | Hồ C - {year} |\n"
                result += "|:---:|:---:|:---:|:---:|\n"
                excel_rows.append(header_row)

                chart_data = []

                for month in range(1, 13):
                    row_data = [f"**Tháng {month}**"]
                    excel_row = [f"Tháng {month}"]
                    chart_item = {"Thang": f"Tháng {month}"}

                    for res_label, col_idx in [("Hồ A", col_a), ("Hồ B", col_b), ("Hồ C", col_c)]:
                        month_values = []
                        for row in data_rows:
                            if len(row) > col_idx:
                                date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                if date and date.year == year and date.month == month:
                                    val = extract_value(row, col_idx)
                                    if val is not None:
                                        month_values.append(val)
                        if month_values:
                            min_val = min(month_values)
                            max_val = max(month_values)
                            avg_val = sum(month_values) / len(month_values)
                            row_data.append(f"{min_val:.2f}{_NBSP}/{_NBSP}{max_val:.2f}{_NBSP}/{_NBSP}{avg_val:.2f}")
                            excel_row.append(f"{min_val:.2f}/{max_val:.2f}/{avg_val:.2f}")
                            chart_item[res_label] = round(avg_val, 2)
                        else:
                            row_data.append("-")
                            excel_row.append("-")
                            chart_item[res_label] = 0.0
                    result += f"| {' | '.join(row_data)} |\n"
                    excel_rows.append(excel_row)
                    chart_data.append(chart_item)

                excel_rows.append([])
                chart_json = {
                    "type": "line" if param == "water_level" else "bar",
                    "title": f"Biểu đồ {param_name.split(' (')[0]} các hồ năm {year}",
                    "data": chart_data,
                    "xKey": "Thang",
                    "yKeys": ["Hồ A", "Hồ B", "Hồ C"],
                    "colors": ["#3b82f6", "#10b981", "#ef4444"],
                    "unit": " m" if param == "water_level" else " m³/s"
                }
                charts.append(chart_json)

                result += "\n---\n"

            if _accumulators is not None:
                _merge_sheet(excel_sheets, "Vinh Son", excel_rows, f"BẢO CÁO THỐNG KÊ CHI TIẾT - TỔNG HỢP")

            return result.strip()

        except Exception as e:
            return f"Lỗi thống kê: {e}"

    def _get_month_all_reservoirs(
        self,
        period_value: str,
        parameters: List[str],
        _accumulators: Optional[dict] = None
    ) -> str:
        """Thống kê tháng cho tất cả 3 hồ (1 bảng gộp - Hồ A, B, C trong 3 hàng)"""
        try:
            m_s, y_s = period_value.strip().split("/")
            month, year = int(m_s), int(y_s)

            import calendar
            last_day = calendar.monthrange(year, month)[1]

            client, spreadsheet = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets thống kê."

            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title or "Thống kê tháng" in ws.title:
                    stats_ws = ws
                    break
            if not stats_ws and worksheets:
                stats_ws = worksheets[0]
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê trong Google Sheets thống kê."

            def fetch_data():
                return stats_ws.get_all_values()

            all_data = retry_with_backoff(fetch_data, max_retries=3, initial_delay=1)
            if len(all_data) < 8:
                return "Không có dữ liệu trong Google Sheets thống kê"

            data_start_row = 0
            for i, row in enumerate(all_data):
                if len(row) > 0:
                    first_cell = str(row[0]).strip()
                    if '/' in first_cell and any(char.isdigit() for char in first_cell):
                        parts = first_cell.split('/')
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                            data_start_row = i
                            break
            if data_start_row == 0:
                data_start_row = 7 if len(all_data) > 7 else 1

            data_rows = all_data[data_start_row:] if len(all_data) > data_start_row else []

            col_date = 0
            col_qve_a, col_qve_b, col_qve_c = 4, 5, 6
            col_water_a, col_water_b, col_water_c = 1, 2, 3

            def normalize_date(date_str):
                if not date_str:
                    return None
                try:
                    parts = str(date_str).strip().split('/')
                    if len(parts) == 3:
                        day, month_str, year_str = parts
                        yr = int(year_str)
                        if yr < 100:
                            yr = 2000 + yr if yr < 50 else 1900 + yr
                        return datetime(yr, int(month_str), int(day))
                    if '-' in str(date_str):
                        return datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
                except (ValueError, AttributeError):
                    pass
                return None

            def extract_value(row, col_idx):
                if col_idx is None or len(row) <= col_idx:
                    return None
                try:
                    val_str = str(row[col_idx]).strip().replace(',', '.')
                    if val_str:
                        return float(val_str)
                except:
                    pass
                return None

            result = f"""### 📊 Thống kê tháng {month}/{year} - Thủy điện Vĩnh Sơn
**Hồ:** Tất cả (A, B, C)
**Tháng:** {month}/{year} (từ ngày 1 đến ngày {last_day})

---

"""
            excel_sheets = _accumulators.get("excel_sheets", []) if _accumulators is not None else []
            charts = _accumulators.get("charts", []) if _accumulators is not None else []

            excel_rows = []

            for param in parameters:
                if param == "qve":
                    param_name = "Lưu lượng về Qve (m³/s)"
                    col_a, col_b, col_c = col_qve_a, col_qve_b, col_qve_c
                elif param == "water_level":
                    param_name = "Mực nước hồ (m)"
                    col_a, col_b, col_c = col_water_a, col_water_b, col_water_c
                else:
                    continue

                result += f"\n#### {param_name}\n\n"
                excel_rows.append([f"THỐNG KÊ THÁNG {month}/{year} - {param_name.upper()} - TẤT CẢ CÁC HỒ"])
                excel_rows.append([])
                excel_rows.append(["Hồ", f"Tháng {month}/{year} (Min/Max/Avg)"])

                result += f"| Hồ | {month}/{year} (Min/Max/Avg) |\n"
                result += "|:---:|:---:|\n"

                for res_name, col_idx in [("Hồ A", col_a), ("Hồ B", col_b), ("Hồ C", col_c)]:
                    month_values = []
                    for row in data_rows:
                        if len(row) > col_idx:
                            date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                            if date and date.year == year and date.month == month and 1 <= date.day <= last_day:
                                val = extract_value(row, col_idx)
                                if val is not None:
                                    month_values.append(val)
                    if month_values:
                        min_val = min(month_values)
                        max_val = max(month_values)
                        avg_val = sum(month_values) / len(month_values)
                        result += f"| **{res_name}** | {min_val:.2f}{_NBSP}/{_NBSP}{max_val:.2f}{_NBSP}/{_NBSP}{avg_val:.2f} |\n"
                        excel_rows.append([res_name, f"{min_val:.2f}/{max_val:.2f}/{avg_val:.2f}"])
                    else:
                        result += f"| **{res_name}** | - |\n"
                        excel_rows.append([res_name, "-"])
                excel_rows.append([])

                chart_data = []
                for day in range(1, last_day + 1):
                    chart_item = {"Ngay": str(day)}
                    for res_name, col_idx in [("Hồ A", col_a), ("Hồ B", col_b), ("Hồ C", col_c)]:
                        day_values = []
                        for row in data_rows:
                            if len(row) > col_idx:
                                date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                if date and date.year == year and date.month == month and date.day == day:
                                    val = extract_value(row, col_idx)
                                    if val is not None:
                                        day_values.append(val)
                        if day_values:
                            chart_item[res_name] = round(sum(day_values)/len(day_values), 2)
                        else:
                            chart_item[res_name] = 0.0
                    chart_data.append(chart_item)

                chart_json = {
                    "type": "line",
                    "title": f"Biểu đồ diễn biến {param_name.split(' (')[0]} tháng {month}/{year}",
                    "data": chart_data,
                    "xKey": "Ngay",
                    "yKeys": ["Hồ A", "Hồ B", "Hồ C"],
                    "colors": ["#3b82f6", "#10b981", "#ef4444"],
                    "unit": " m" if param == "water_level" else " m³/s"
                }
                charts.append(chart_json)

                result += "\n---\n"

            if _accumulators is not None:
                _merge_sheet(excel_sheets, "Vinh Son", excel_rows, f"BẢO CÁO THỐNG KÊ CHI TIẾT - TỔNG HỢP")

            return result.strip()

        except Exception as e:
            return f"Lỗi thống kê: {e}"

    def _get_date_range_statistics(
        self,
        start_date: str,
        end_date: str,
        reservoir: str,
        parameters: List[str],
        _accumulators: Optional[dict] = None
    ) -> str:
        try:
            client, spreadsheet = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets thống kê."

            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title or "Thống kê tháng" in ws.title:
                    stats_ws = ws
                    break
            if not stats_ws and worksheets:
                stats_ws = worksheets[0]
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê trong Google Sheets thống kê."

            def fetch_data():
                return stats_ws.get_all_values()

            all_data = retry_with_backoff(fetch_data, max_retries=3, initial_delay=1)
            if len(all_data) < 8:
                return "Không có dữ liệu trong Google Sheets thống kê"

            data_start_row = 0
            for i, row in enumerate(all_data):
                if len(row) > 0:
                    first_cell = str(row[0]).strip()
                    if '/' in first_cell and any(char.isdigit() for char in first_cell):
                        parts = first_cell.split('/')
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                            data_start_row = i
                            break
            if data_start_row == 0:
                data_start_row = 7 if len(all_data) > 7 else 1

            data_rows = all_data[data_start_row:] if len(all_data) > data_start_row else []

            col_date = 0
            if reservoir == "Vinh Son -A":
                col_qve = 4
                col_water_level = 1
            elif reservoir == "Vinh Son -B":
                col_qve = 5
                col_water_level = 2
            elif reservoir == "Vinh Son -C":
                col_qve = 6
                col_water_level = 3
            else:
                col_qve = 4
                col_water_level = 1

            def parse_date_str(date_str: str) -> Optional[datetime]:
                try:
                    parts = date_str.strip().split("/")
                    if len(parts) == 3:
                        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                        return datetime(y, m, d)
                except (ValueError, IndexError):
                    pass
                return None

            def normalize_date(date_str):
                if not date_str:
                    return None
                try:
                    parts = str(date_str).strip().split('/')
                    if len(parts) == 3:
                        day, month, year_str = parts
                        year = int(year_str)
                        if year < 100:
                            year = 2000 + year if year < 50 else 1900 + year
                        return datetime(year, int(month), int(day))
                    if '-' in str(date_str):
                        return datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
                except (ValueError, AttributeError):
                    pass
                return None

            def extract_value(row, col_idx):
                if col_idx is None or len(row) <= col_idx:
                    return None
                try:
                    val_str = str(row[col_idx]).strip().replace(',', '.')
                    if val_str:
                        return float(val_str)
                except:
                    pass
                return None

            start_dt = parse_date_str(start_date)
            end_dt = parse_date_str(end_date)

            if not start_dt or not end_dt:
                return f"### Lỗi\n\nKhông thể parse ngày. Sử dụng format DD/MM/YYYY (ví dụ: 1/1/2026)"

            if start_dt > end_dt:
                return f"### Lỗi\n\nNgày bắt đầu ({start_date}) phải nhỏ hơn hoặc bằng ngày kết thúc ({end_date})"

            out = f"""
### 📊 Thống kê theo Ngày - Thủy điện Vĩnh Sơn
**Hồ:** {reservoir}
**Khoảng thời gian:** Từ {start_date} đến {end_date}
"""
            out += "\n---\n"

            excel_sheets = _accumulators.get("excel_sheets", []) if _accumulators is not None else []
            charts = _accumulators.get("charts", []) if _accumulators is not None else []

            excel_rows = []

            for param in parameters:
                col_idx = col_qve if param == "qve" else col_water_level
                if col_idx is None:
                    continue
                param_name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                unit = "m³/s" if param == "qve" else "m"
                out += f"\n#### {param_name}\n\n"
                out += f"| Ngày | Giá trị ({unit}) |\n"
                out += "|---|---:|\n"

                excel_rows.append([f"THỐNG KÊ {param_name.upper()} - {reservoir.upper()}"])
                excel_rows.append([f"Từ {start_date} đến {end_date}"])
                excel_rows.append([])
                excel_rows.append(["Ngày", f"Giá trị ({unit})"])

                values_in_range: List[float] = []
                chart_data = []
                current_dt = start_dt
                while current_dt <= end_dt:
                    day_str = f"**{current_dt.day}/{current_dt.month}/{current_dt.year}**"
                    excel_day_str = f"{current_dt.day}/{current_dt.month}/{current_dt.year}"
                    value_str = "-"
                    val = None
                    for r in data_rows:
                        if len(r) > col_idx:
                            dt = normalize_date(r[col_date] if col_date is not None and len(r) > col_date else None)
                            if dt and dt.year == current_dt.year and dt.month == current_dt.month and dt.day == current_dt.day:
                                val = extract_value(r, col_idx)
                                if val is not None:
                                    value_str = f"{val:.2f}"
                                    values_in_range.append(val)
                                break

                    out += f"| {day_str} | {value_str} |\n"
                    excel_rows.append([excel_day_str, val if val is not None else "-"])
                    chart_data.append({
                        "Ngay": f"{current_dt.day}/{current_dt.month}",
                        "GiaTri": val if val is not None else 0.0
                    })
                    current_dt += timedelta(days=1)

                avg_val = sum(values_in_range) / len(values_in_range) if values_in_range else None
                avg_str = f"{avg_val:.2f}" if avg_val is not None else "-"
                out += f"| **Trung bình** | {avg_str} |\n"
                excel_rows.append(["Trung bình", avg_val if avg_val is not None else "-"])
                excel_rows.append([])

                if chart_data:
                    chart_json = {
                        "type": "bar" if param == "qve" else "line",
                        "title": f"Biểu đồ biến động {param_name.split(' (')[0]} - {reservoir}",
                        "data": chart_data,
                        "xKey": "Ngay",
                        "yKeys": ["GiaTri"],
                        "colors": ["#3b82f6"],
                        "unit": f" {unit}"
                    }
                    charts.append(chart_json)

                out += "\n---\n"

            if _accumulators is not None:
                sheet_title = reservoir.replace("Vinh Son -", "Ho ")
                _merge_sheet(excel_sheets, sheet_title, excel_rows, f"BẢO CÁO THỐNG KÊ CHI TIẾT - {reservoir.upper()}")

            return out.strip()

        except Exception as e:
            return f"Lỗi: {e}"

    def _get_date_range_statistics_combined(
        self,
        start_date: str,
        end_date: str,
        parameters: List[str],
        _accumulators: Optional[dict] = None
    ) -> str:
        try:
            client, spreadsheet = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet:
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets thống kê."

            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title or "Thống kê tháng" in ws.title:
                    stats_ws = ws
                    break
            if not stats_ws and worksheets:
                stats_ws = worksheets[0]
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê trong Google Sheets thống kê."

            def fetch_data():
                return stats_ws.get_all_values()

            all_data = retry_with_backoff(fetch_data, max_retries=3, initial_delay=1)
            if len(all_data) < 8:
                return "Không có dữ liệu trong Google Sheets thống kê"

            data_start_row = 0
            for i, row in enumerate(all_data):
                if len(row) > 0:
                    first_cell = str(row[0]).strip()
                    if '/' in first_cell and any(char.isdigit() for char in first_cell):
                        parts = first_cell.split('/')
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                            data_start_row = i
                            break
            if data_start_row == 0:
                data_start_row = 7 if len(all_data) > 7 else 1

            data_rows = all_data[data_start_row:] if len(all_data) > data_start_row else []

            col_date = 0
            col_qve_a, col_qve_b, col_qve_c = 4, 5, 6
            col_water_a, col_water_b, col_water_c = 1, 2, 3

            def parse_date_str(date_str: str) -> Optional[datetime]:
                try:
                    parts = date_str.strip().split("/")
                    if len(parts) == 3:
                        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                        return datetime(y, m, d)
                except (ValueError, IndexError):
                    pass
                return None

            def normalize_date(date_str):
                if not date_str:
                    return None
                try:
                    parts = str(date_str).strip().split('/')
                    if len(parts) == 3:
                        day, month, year_str = parts
                        year = int(year_str)
                        if year < 100:
                            year = 2000 + year if year < 50 else 1900 + year
                        return datetime(year, int(month), int(day))
                    if '-' in str(date_str):
                        return datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
                except (ValueError, AttributeError):
                    pass
                return None

            def extract_value(row, col_idx):
                if col_idx is None or len(row) <= col_idx:
                    return None
                try:
                    val_str = str(row[col_idx]).strip().replace(',', '.')
                    if val_str:
                        return float(val_str)
                except:
                    pass
                return None

            start_dt = parse_date_str(start_date)
            end_dt = parse_date_str(end_date)

            if not start_dt or not end_dt:
                return f"### Lỗi\n\nKhông thể parse ngày. Sử dụng format DD/MM/YYYY (ví dụ: 1/1/2026)"

            if start_dt > end_dt:
                return f"### Lỗi\n\nNgày bắt đầu ({start_date}) phải nhỏ hơn hoặc bằng ngày kết thúc ({end_date})"

            out = f"""
### 📊 Thống kê theo Ngày - Thủy điện Vĩnh Sơn
**Tất cả 3 hồ:** A, B, C (gộp chung 1 bảng)
**Khoảng thời gian:** Từ {start_date} đến {end_date}
"""
            out += "\n---\n"

            excel_sheets = _accumulators.get("excel_sheets", []) if _accumulators is not None else []
            charts = _accumulators.get("charts", []) if _accumulators is not None else []

            excel_rows = []

            for param in parameters:
                if param == "qve":
                    param_name = "Lưu lượng về Qve (m³/s)"
                    col_a, col_b, col_c = col_qve_a, col_qve_b, col_qve_c
                elif param == "water_level":
                    param_name = "Mực nước hồ (m)"
                    col_a, col_b, col_c = col_water_a, col_water_b, col_water_c
                else:
                    continue

                out += f"\n#### {param_name}\n\n"
                out += "| Ngày | Hồ A | Hồ B | Hồ C |\n"
                out += "|:------:|------:|------:|------:|\n"

                excel_rows.append([f"THỐNG KÊ CHI TIẾT TỔNG HỢP - {param_name.upper()}"])
                excel_rows.append([f"Từ {start_date} đến {end_date}"])
                excel_rows.append([])
                excel_rows.append(["Ngày", "Hồ A", "Hồ B", "Hồ C"])

                vals_a: List[float] = []
                vals_b: List[float] = []
                vals_c: List[float] = []
                chart_data = []

                current_dt = start_dt
                while current_dt <= end_dt:
                    day_str = f"**{current_dt.day}/{current_dt.month}/{current_dt.year}**"
                    excel_day_str = f"{current_dt.day}/{current_dt.month}/{current_dt.year}"

                    def day_val(col_idx, acc: List[float]) -> Tuple[str, Optional[float]]:
                        for r in data_rows:
                            if len(r) > col_idx:
                                dt = normalize_date(r[col_date] if col_date is not None and len(r) > col_date else None)
                                if dt and dt.year == current_dt.year and dt.month == current_dt.month and dt.day == current_dt.day:
                                    v = extract_value(r, col_idx)
                                    if v is not None:
                                        acc.append(v)
                                        return f"{v:.2f}", v
                        return "-", None

                    va_str, va_num = day_val(col_a, vals_a)
                    vb_str, vb_num = day_val(col_b, vals_b)
                    vc_str, vc_num = day_val(col_c, vals_c)

                    out += f"| {day_str} | {va_str} | {vb_str} | {vc_str} |\n"
                    excel_rows.append([excel_day_str, va_num if va_num is not None else "-", vb_num if vb_num is not None else "-", vc_num if vc_num is not None else "-"])
                    chart_data.append({
                        "Ngay": f"{current_dt.day}/{current_dt.month}",
                        "Hồ A": va_num if va_num is not None else 0.0,
                        "Hồ B": vb_num if vb_num is not None else 0.0,
                        "Hồ C": vc_num if vc_num is not None else 0.0
                    })
                    current_dt += timedelta(days=1)

                avg_a = sum(vals_a) / len(vals_a) if vals_a else None
                avg_b = sum(vals_b) / len(vals_b) if vals_b else None
                avg_c = sum(vals_c) / len(vals_c) if vals_c else None

                avg_a_str = f"{avg_a:.2f}" if avg_a is not None else "-"
                avg_b_str = f"{avg_b:.2f}" if avg_b is not None else "-"
                avg_c_str = f"{avg_c:.2f}" if avg_c is not None else "-"

                out += f"| **Trung bình** | {avg_a_str} | {avg_b_str} | {avg_c_str} |\n"
                excel_rows.append(["Trung bình", avg_a if avg_a is not None else "-", avg_b if avg_b is not None else "-", avg_c if avg_c is not None else "-"])
                excel_rows.append([])

                if chart_data:
                    chart_json = {
                        "type": "line",
                        "title": f"Biểu đồ diễn biến {param_name} các hồ",
                        "data": chart_data,
                        "xKey": "Ngay",
                        "yKeys": ["Hồ A", "Hồ B", "Hồ C"],
                        "colors": ["#3b82f6", "#10b981", "#ef4444"],
                        "unit": " m" if param == "water_level" else " m³/s"
                    }
                    charts.append(chart_json)

                out += "\n---\n"

            if _accumulators is not None:
                _merge_sheet(excel_sheets, "Vinh Son", excel_rows, f"BẢO CÁO THỐNG KÊ CHI TIẾT - TỔNG HỢP")

            return out.strip()

        except Exception as e:
            return f"Lỗi: {e}"


def _merge_sheet(excel_sheets: list, name: str, rows: list, title: str):
    """
    Trợ giúp để gộp các dòng vào worksheet có tên chỉ định.
    Nếu worksheet chưa tồn tại, tạo mới với title hàng đầu.
    """
    for sheet in excel_sheets:
        if sheet["name"] == name:
            sheet["rows"].extend(rows)
            return
    excel_sheets.append({
        "name": name,
        "rows": [
            [title],
            [],
        ] + rows
    })
