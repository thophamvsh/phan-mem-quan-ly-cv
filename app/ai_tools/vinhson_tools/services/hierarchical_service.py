"""
Hierarchical statistics service - Get hierarchical statistics for Vĩnh Sơn
"""
# Non-breaking space: giữ Min/Max/Avg trên một dòng khi render Markdown
_NBSP = "\u00a0"

from datetime import datetime, timedelta
from typing import Optional, List, Any
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
        end_date: Optional[str] = None
    ) -> str:
        """
        Thống kê phân cấp Qve và Mực nước hồ theo năm/tháng/tuần cho Vĩnh Sơn.
        Hỗ trợ date range: nếu có start_date và end_date, trả về thống kê theo ngày.

        Chỉ hiển thị đúng tham số trong parameters:
        - Hỏi Qve → parameters=["qve"] → chỉ bảng Qve
        - Hỏi MNH/mực nước → parameters=["water_level"] → chỉ bảng MNH
        """
        print(f"[INFO] VINH SON TOOL: Hierarchical statistics - {period_type} {period_value}, reservoir={reservoir}, parameters={parameters}, compare={compare}, compare_years={compare_years}, compare_with_period_value={compare_with_period_value}, start_date={start_date}, end_date={end_date}", flush=True)

        # Chỉ hiển thị đúng tham số được hỏi (Qve hoặc MNH). Mặc định cả hai nếu không truyền.
        if not parameters:
            parameters = ["qve", "water_level"]

        # Xử lý date range: nếu có start_date và end_date
        if start_date and end_date:
            if reservoir == "All" or reservoir is None:
                # Với reservoir="All", gộp chung 1 bảng với cột Hồ A, Hồ B, Hồ C
                return self._get_date_range_statistics_combined(
                    start_date, end_date, parameters
                )
            else:
                # Với hồ cụ thể
                return self._get_date_range_statistics(
                    start_date, end_date, reservoir, parameters
                )

        # Xử lý đặc biệt cho reservoir="All"
        if reservoir == "All" or reservoir is None:
            if period_type == "year":
                # Hỏi năm: chỉ trả 1 khối (3 bảng Hồ A, B, C), không tách thành 2/4, 3/4, 4/4
                if compare:
                    results = []
                    for res in ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"]:
                        res_result = self.get_hierarchical_statistics(
                            period_type, period_value, res, parameters, compare, compare_years,
                            compare_with_period_value=None, start_date=start_date, end_date=end_date
                        )
                        results.append(res_result)
                    # Gộp 3 bảng trong 1 khối, dùng \n\n để UI không tách thành nhiều phần (2/4, 3/4, 4/4)
                    return "\n\n".join(results)
                else:
                    return self._get_all_reservoirs_year_stats(period_value, parameters, compare, compare_years)
            elif period_type == "month":
                # Thống kê tháng cho tất cả 3 hồ
                if compare and compare_years >= 2:
                    # So sánh tháng với nhiều năm -> hiển thị 3 bảng riêng cho từng hồ (giống year)
                    results = []
                    for res in ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"]:
                        res_result = self.get_hierarchical_statistics(
                            period_type, period_value, res, parameters, compare, compare_years,
                            compare_with_period_value=None, start_date=start_date, end_date=end_date
                        )
                        results.append(res_result)
                    # Gộp 3 bảng trong 1 khối
                    return "\n\n".join(results)
                else:
                    return self._get_month_all_reservoirs(period_value, parameters)
            elif period_type == "week":
                # Với "week": gọi đệ quy cho từng hồ riêng lẻ
                results = []
                for res in ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"]:
                    res_result = self.get_hierarchical_statistics(
                        period_type, period_value, res, parameters, compare, compare_years,
                        compare_with_period_value=None, start_date=start_date, end_date=end_date
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

            # Tìm dòng bắt đầu dữ liệu
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

            # Column mapping cho từng hồ
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

            # Column mapping cho tất cả các hồ (dùng khi so sánh nhiều năm với reservoir="All")
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

            if period_type == "year":
                year = int(period_value) if period_value else current_year
                if compare:
                    n_compare = min(max(compare_years, 1), 5)  # 2 → 3 cột, 3 → 4 cột
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

                    if param == "qve":
                        col_a, col_b, col_c = col_qve_a, col_qve_b, col_qve_c
                    else:
                        col_a, col_b, col_c = col_water_a, col_water_b, col_water_c

                    if compare and len(years_to_compare) > 1:
                        # Xác định column index cho từng hồ dựa trên param
                        if param == "qve":
                            col_a, col_b, col_c = col_qve_a, col_qve_b, col_qve_c
                        else:
                            col_a, col_b, col_c = col_water_a, col_water_b, col_water_c

                        # Xác định hồ nào cần hiển thị dựa trên reservoir
                        # Nếu reservoir cụ thể (A, B, C) -> chỉ hiển thị hồ đó
                        # Nếu reservoir="All" -> hiển thị cả 3 hồ
                        current_res = reservoir if reservoir else "All"

                        if current_res == "All" or current_res is None:
                            # Hiển thị cả 3 hồ A, B, C
                            header_cols = ["Tháng"]
                            for res in ["A", "B", "C"]:
                                for yr in years_to_compare:
                                    header_cols.append(f"{res} - {yr} (Min/Max/Avg)")
                            result += f"| {' | '.join(header_cols)} |\n"
                            result += "|" + "|".join([":---:"] * len(header_cols)) + "|\n"

                            # Dữ liệu cho 3 hồ
                            cols_to_show = [col_a, col_b, col_c]
                        else:
                            # Chỉ hiển thị hồ được chọn
                            # Map reservoir name -> (label, column index)
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

                            # Chỉ 1 hồ
                            cols_to_show = [res_col]
                    else:
                        result += f"| Tháng | Hồ A - {year} | Hồ B - {year} | Hồ C - {year} |\n"
                        result += "|:---:|:---:|:---:|:---:|\n"
                        cols_to_show = None

                    for month in range(1, 13):
                        row_data = [f"**Tháng {month}**"]
                        if compare and len(years_to_compare) > 1:
                            for col_idx in cols_to_show:
                                for yr in years_to_compare:
                                    month_values = []
                                    for row in data_rows:
                                        if len(row) > col_idx:
                                            date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                            if date and date.year == yr and date.month == month:
                                                val = extract_value(row, col_idx)
                                                if val is not None:
                                                    month_values.append(val)
                                    if month_values:
                                        min_val = min(month_values)
                                        max_val = max(month_values)
                                        avg_val = sum(month_values) / len(month_values)
                                        row_data.append(f"{min_val:.2f}{_NBSP}/{_NBSP}{max_val:.2f}{_NBSP}/{_NBSP}{avg_val:.2f}")
                                    else:
                                        row_data.append("-")
                        else:
                            for col_idx in [col_a, col_b, col_c]:
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
                                else:
                                    row_data.append("-")
                        result += f"| {' | '.join(row_data)} |\n"

                    # Thêm hàng trung bình cả năm
                    avg_row = ["**Trung bình**"]
                    if compare and len(years_to_compare) > 1:
                        for col_idx in cols_to_show:
                            for yr in years_to_compare:
                                year_values = []
                                for m in range(1, 13):
                                    for row in data_rows:
                                        if len(row) > col_idx:
                                            date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                            if date and date.year == yr and date.month == m:
                                                val = extract_value(row, col_idx)
                                                if val is not None:
                                                    year_values.append(val)
                                if year_values:
                                    avg_val = sum(year_values) / len(year_values)
                                    avg_row.append(f"{avg_val:.2f}")
                                else:
                                    avg_row.append("-")
                    else:
                        for col_idx in [col_a, col_b, col_c]:
                            year_values = []
                            for m in range(1, 13):
                                for row in data_rows:
                                    if len(row) > col_idx:
                                        date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                        if date and date.year == year and date.month == m:
                                            val = extract_value(row, col_idx)
                                            if val is not None:
                                                year_values.append(val)
                            if year_values:
                                avg_val = sum(year_values) / len(year_values)
                                avg_row.append(f"{avg_val:.2f}")
                            else:
                                avg_row.append("-")
                    result += f"| {' | '.join(avg_row)} |\n"
                    result += "\n---\n"

                # result += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Vĩnh Sơn"
                return result.strip()

            elif period_type == "month":
                # Thống kê cả tháng (từ ngày 1 đến ngày cuối tháng)
                if period_value and "/" in period_value:
                    m_s, y_s = period_value.split("/")
                    month, year = int(m_s), int(y_s)
                else:
                    month, year = current_month, current_year

                import calendar
                last_day = calendar.monthrange(year, month)[1]

                # Xác định các năm cần so sánh
                if compare and compare_years >= 2:
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

                    if compare and len(years_to_compare) > 1:
                        # Xác định tên hồ để hiển thị trong tiêu đề
                        res_label = "Hồ"
                        if reservoir == "Vinh Son -A":
                            res_label = "Hồ A"
                        elif reservoir == "Vinh Son -B":
                            res_label = "Hồ B"
                        elif reservoir == "Vinh Son -C":
                            res_label = "Hồ C"

                        # Hiển thị từng ngày với các năm so sánh (chỉ 1 giá trị trung bình)
                        header_cols = ["Ngày"]
                        for yr in years_to_compare:
                            header_cols.append(f"{res_label}-{yr}")
                        result += f"| {' | '.join(header_cols)} |\n"
                        result += "|" + "|".join([":---:"] * len(header_cols)) + "|\n"

                        for day in range(1, last_day + 1):
                            row_data = [f"**{day}**"]
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
                                else:
                                    row_data.append("-")
                            result += f"| {' | '.join(row_data)} |\n"

                        # Thêm hàng trung bình tháng
                        avg_row = ["**Trung bình**"]
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
                            else:
                                avg_row.append("-")
                        result += f"| {' | '.join(avg_row)} |\n"
                    else:
                        # Không so sánh - hiển thị tổng hợp cả tháng
                        result += f"| Tháng {month}/{year} (Min/Max/Avg) |\n"
                        result += "|:---:|\n"

                        vals = []
                        for row in data_rows:
                            if len(row) > col_idx:
                                date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                if date and date.year == year and date.month == month and 1 <= date.day <= last_day:
                                    val = extract_value(row, col_idx)
                                    if val is not None:
                                        vals.append(val)
                        if vals:
                            result += f"| {min(vals):.2f}{_NBSP}/{_NBSP}{max(vals):.2f}{_NBSP}/{_NBSP}{sum(vals)/len(vals):.2f} |\n"
                        else:
                            result += "| -\n"
                    result += "\n---\n"

                # result += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Vĩnh Sơn"
                return result.strip()

            elif period_type == "week":
                # Thống kê theo ngày trong tuần (1 hồ)
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
                    # Hiển thị đúng đơn vị cho từng tham số
                    unit = "m³/s" if param == "qve" else "m"
                    result += f"\n#### {param_name}\n\n"
                    result += f"| Ngày | Giá trị ({unit}) |\n"
                    result += "|---|---:|\n"

                    for d in range(sd, min(ed + 1, 32)):
                        value_str = "-"
                        for row in data_rows:
                            if len(row) > col_idx:
                                date = normalize_date(row[col_date] if col_date is not None and len(row) > col_date else None)
                                if date and date.year == year and date.month == month and date.day == d:
                                    val = extract_value(row, col_idx)
                                    if val is not None:
                                        value_str = f"{val:.2f}"
                                    break
                        result += f"| **{d}/{month}** | {value_str} |\n"
                    result += "\n---\n"

                result += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Vĩnh Sơn"
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
        """So sánh tháng: 2 tháng hoặc 3 năm cùng kỳ. Trả về 3 bảng (mỗi hồ 1 bảng)."""
        try:
            m1_s, y1_s = period_value.strip().split("/")
            month1, year1 = int(m1_s), int(y1_s)
            # N năm cùng kỳ (compare_years=2 → 3 cột, compare_years=3 → 4 cột): year1, year1-1, ..., year1-N
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
                # Tên hồ hiển thị (A, B, C)
                res_label = res_name.replace("Vinh Son -", "Hồ ")
                block = f"### 📊 So sánh theo Ngày - Thủy điện Vĩnh Sơn\n**Hồ:** {res_name}\n**So sánh:** {period_labels} (từ ngày 1 đến ngày {max_day})\n\n---\n\n"
                for param in parameters or ["qve", "water_level"]:
                    col_idx = col_qve if param == "qve" else col_water
                    param_name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                    # Thêm tên hồ vào tiêu đề bảng
                    block += f"\n#### {param_name} - {res_label}\n\n"
                    # Header với tên hồ
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

                    # Thêm hàng trung bình
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
            error_msg = f"Lỗi khi so sánh tháng: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg

    def _get_all_reservoirs_year_stats(
        self,
        period_value: Optional[str],
        parameters: List[str],
        compare: bool,
        compare_years: int
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

                # Header với tên hồ
                result += f"| Tháng | Hồ A - {year} | Hồ B - {year} | Hồ C - {year} |\n"
                result += "|:---:|:---:|:---:|:---:|\n"

                for month in range(1, 13):
                    row_data = [f"**Tháng {month}**"]
                    for col_idx in [col_a, col_b, col_c]:
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
                        else:
                            row_data.append("-")
                    result += f"| {' | '.join(row_data)} |\n"
                result += "\n---\n"

            # result += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Vĩnh Sơn"
            return result.strip()

        except Exception as e:
            error_msg = f"Lỗi khi thống kê phân cấp: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg

    def _get_month_all_reservoirs(
        self,
        period_value: str,
        parameters: List[str]
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
                # Header: 1 hàng tiêu đề + 3 hàng dữ liệu (Hồ A, B, C)
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
                    else:
                        result += f"| **{res_name}** | - |\n"
                result += "\n---\n"

            # result += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Vĩnh Sơn"
            return result.strip()

        except Exception as e:
            error_msg = f"Lỗi khi thống kê tháng cho tất cả hồ: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg

    def _get_date_range_statistics(
        self,
        start_date: str,
        end_date: str,
        reservoir: str,
        parameters: List[str]
    ) -> str:
        """
        Thống kê theo ngày cho khoảng thời gian từ start_date đến end_date cho một hồ cụ thể
        """
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

            # Tìm dòng bắt đầu dữ liệu
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

            # Column mapping cho từng hồ
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
                """Parse date string in format DD/MM/YYYY"""
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

            for param in parameters:
                col_idx = col_qve if param == "qve" else col_water_level
                if col_idx is None:
                    continue
                param_name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                # Hiển thị đúng đơn vị cho từng tham số
                unit = "m³/s" if param == "qve" else "m"
                out += f"\n#### {param_name}\n\n"
                out += f"| Ngày | Giá trị ({unit}) |\n"
                out += "|---|---:|\n"

                values_in_range: List[float] = []
                current_dt = start_dt
                while current_dt <= end_dt:
                    day_str = f"**{current_dt.day}/{current_dt.month}/{current_dt.year}**"

                    value_str = "-"
                    for r in data_rows:
                        if len(r) > col_idx:
                            dt = normalize_date(r[col_date] if col_date is not None and len(r) > col_date else None)
                            if dt and dt.year == current_dt.year and dt.month == current_dt.month and dt.day == current_dt.day:
                                v = extract_value(r, col_idx)
                                if v is not None:
                                    value_str = f"{v:.2f}"
                                    values_in_range.append(v)
                                break

                    out += f"| {day_str} | {value_str} |\n"
                    current_dt += timedelta(days=1)

                avg_str = f"{sum(values_in_range) / len(values_in_range):.2f}" if values_in_range else "-"
                out += f"| **Trung bình** | {avg_str} |\n"
                out += "\n---\n"

            # out += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Vĩnh Sơn"
            return out.strip()

        except Exception as e:
            error_msg = f"Lỗi khi thống kê phân cấp: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg

    def _get_date_range_statistics_combined(
        self,
        start_date: str,
        end_date: str,
        parameters: List[str]
    ) -> str:
        """
        Thống kê theo ngày cho khoảng thời gian từ start_date đến end_date,
        gộp chung 3 hồ A, B, C vào 1 bảng (cột Hồ A | Hồ B | Hồ C).
        Chỉ xuất bảng tương ứng parameters: ["qve"] → chỉ Qve; ["water_level"] → chỉ MNH.
        """
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

                vals_a: List[float] = []
                vals_b: List[float] = []
                vals_c: List[float] = []

                current_dt = start_dt
                while current_dt <= end_dt:
                    day_str = f"**{current_dt.day}/{current_dt.month}/{current_dt.year}**"

                    def day_val(col_idx, acc: List[float]):
                        for r in data_rows:
                            if len(r) > col_idx:
                                dt = normalize_date(r[col_date] if col_date is not None and len(r) > col_date else None)
                                if dt and dt.year == current_dt.year and dt.month == current_dt.month and dt.day == current_dt.day:
                                    v = extract_value(r, col_idx)
                                    if v is not None:
                                        acc.append(v)
                                        return f"{v:.2f}"
                        return "-"

                    va = day_val(col_a, vals_a)
                    vb = day_val(col_b, vals_b)
                    vc = day_val(col_c, vals_c)
                    out += f"| {day_str} | {va} | {vb} | {vc} |\n"
                    current_dt += timedelta(days=1)

                avg_a = f"{sum(vals_a) / len(vals_a):.2f}" if vals_a else "-"
                avg_b = f"{sum(vals_b) / len(vals_b):.2f}" if vals_b else "-"
                avg_c = f"{sum(vals_c) / len(vals_c):.2f}" if vals_c else "-"
                out += f"| **Trung bình** | {avg_a} | {avg_b} | {avg_c} |\n"
                out += "\n---\n"

            # out += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Vĩnh Sơn"
            return out.strip()

        except Exception as e:
            error_msg = f"Lỗi khi thống kê phân cấp: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg
