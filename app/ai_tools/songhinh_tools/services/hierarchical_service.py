"""
Hierarchical statistics service - Get hierarchical statistics for Sông Hinh
"""
# Non-breaking space: giữ Min/Max/Avg trên một dòng khi render Markdown
_NBSP = "\u00a0"

from datetime import datetime, timedelta
from typing import Optional, List, Any, Tuple
from ..config.settings import GS_CONFIG
from ..core.sheets_client import get_sheets_client_manager
from ..utils.numbers import safe_cell, parse_float_loose, normalize_mnh_value


class HierarchicalStatisticsService:
    """Service for hierarchical statistics (Qve, water level)"""

    def __init__(self):
        self.manager = get_sheets_client_manager()

    def get_hierarchical_statistics(
        self,
        period_type: str,
        period_value: Optional[str] = None,
        parameters: Optional[List[str]] = None,
        compare: bool = False,
        compare_years: int = 1,
        compare_with_period_value: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Thống kê phân cấp Qve và Mực nước hồ theo năm/tháng/tuần cho Sông Hinh
        Hỗ trợ date range: nếu có start_date và end_date, trả về thống kê theo ngày cho khoảng thời gian đó
        """
        print(f"[INFO] SONG HINH TOOL: Hierarchical statistics - {period_type} {period_value}, parameters={parameters}, compare={compare}, compare_years={compare_years}, compare_with_period_value={compare_with_period_value}, start_date={start_date}, end_date={end_date}", flush=True)

        if not parameters:
            parameters = ["qve", "water_level"]

        spreadsheet = self.manager.get_write_spreadsheet(GS_CONFIG.stats_export_spreadsheet_id_songhinh)
        if not spreadsheet:
            return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets thống kê."

        # pick worksheet
        try:
            worksheets = spreadsheet.worksheets()
            stats_ws = None
            for ws in worksheets:
                if "Thống kê" in ws.title:
                    stats_ws = ws
                    break
            stats_ws = stats_ws or (worksheets[0] if worksheets else None)
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy worksheet thống kê trong Google Sheets thống kê."
        except Exception as e:
            return f"### Lỗi\n\nKhông thể kết nối Google Sheets thống kê: {str(e)}"

        all_data = self.manager.get_all_values_cached(stats_ws, cache_key="stats_all_values")
        if len(all_data) < 8:
            return "Không có dữ liệu trong Google Sheets thống kê"

        # find data start row
        data_start = 0
        for i, row in enumerate(all_data):
            first_cell = str(row[0]).strip() if row else ""
            if "/" in first_cell and any(ch.isdigit() for ch in first_cell):
                parts = first_cell.split("/")
                if len(parts) >= 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                    data_start = i
                    break
        if data_start == 0:
            data_start = 7 if len(all_data) > 7 else 1

        rows = all_data[data_start:]

        # Cột trong sheet thống kê Sông Hinh (0-based): A=0, B=1, C=2, D=3, E=4, F=5, G=6
        # Chỉ lấy A,B,C,D,E,F. KHÔNG lấy cột G (Qv 2025) khi thống kê so sánh Qve.
        col_date = 0      # A: Tháng/ngày/năm
        col_water = 1     # B: Mực nước TL (Htl m)
        col_qve = 5       # F: Lưu lượng về trung bình ngày 2026 (Qv 2026 m3/s) - CHỈ dùng cột này cho Qve. Cột G (index 6) Qv 2025 không lấy.

        def parse_stats_date(s: Any) -> Optional[datetime]:
            if not s:
                return None
            text = str(s).strip()
            if not text:
                return None
            # DD/MM/YY or DD/MM/YYYY
            if "/" in text:
                parts = text.split("/")
                if len(parts) == 3:
                    try:
                        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                        if y < 100:
                            y = 2000 + y if y < 50 else 1900 + y
                        return datetime(y, m, d)
                    except Exception:
                        return None
            if "-" in text:
                try:
                    return datetime.strptime(text, "%Y-%m-%d")
                except Exception:
                    return None
            return None

        def extract_col_value(row: List[str], col: int, param_name: Optional[str] = None) -> Optional[float]:
            raw = safe_cell(row, col)
            # Cột F Qve Sông Hinh: định dạng châu Âu (dấu phẩy = thập phân). 43,820 = 43.82; 9,931 = 9.931. Chuẩn hóa trước khi parse để tránh 9,931 → 9931.
            if param_name == "qve" and raw:
                raw = str(raw).strip().replace(",", ".")
            v = parse_float_loose(raw)
            if param_name == "water_level" and v is not None:
                v = normalize_mnh_value(v)
            return v

        now = datetime.now()
        current_year, current_month = now.year, now.month
        current_week = (now.day - 1) // 7 + 1

        # Xử lý date range: nếu có start_date và end_date, trả về thống kê theo ngày
        if start_date and end_date:
            return self._get_date_range_statistics(start_date, end_date, parameters, rows, col_date, col_qve, col_water, parse_stats_date, extract_col_value)

        if period_type == "year":
            year = int(period_value) if period_value else current_year
            if compare:
                n_compare = min(max(int(compare_years), 1), 5)  # 2 → 3 cột, 3 → 4 cột
                years = [year] + [year - i for i in range(1, n_compare + 1)]
                years.sort(reverse=True)
            else:
                years = [year]

            out = f"""
### 📊 Thống kê theo Tháng - Thủy điện Sông Hinh
**Năm:** {year}
"""
            if compare and len(years) > 1:
                out += f"**So sánh với {len(years)-1} năm liền kề:** {', '.join(map(str, years[1:]))}\n"
            out += "\n---\n"

            for param in parameters:
                col = col_qve if param == "qve" else col_water
                name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                out += f"\n#### {name}\n\n"

                header = ["Tháng"] + [f"{y} (Min/Max/Avg)" for y in years]
                out += f"| {' | '.join(header)} |\n"
                out += "|" + "|".join([":---:"] * len(header)) + "|\n"

                for m in range(1, 13):
                    row_cells = [f"**Tháng {m}**"]
                    for y in years:
                        vals: List[float] = []
                        for r in rows:
                            dt = parse_stats_date(safe_cell(r, col_date))
                            if dt and dt.year == y and dt.month == m:
                                v = extract_col_value(r, col, param)
                                if v is not None:
                                    vals.append(v)
                        if vals:
                            # Cột F (Qv 2026 m3/s) đã là m³/s, không chia 1000
                            if param == "qve":
                                min_val = min(vals)
                                max_val = max(vals)
                                avg_val = sum(vals) / len(vals)
                                row_cells.append(f"{min_val:.2f}{_NBSP}/{_NBSP}{max_val:.2f}{_NBSP}/{_NBSP}{avg_val:.2f}")
                            else:
                                row_cells.append(f"{min(vals):.2f}{_NBSP}/{_NBSP}{max(vals):.2f}{_NBSP}/{_NBSP}{sum(vals)/len(vals):.2f}")
                        else:
                            row_cells.append("-")
                    out += f"| {' | '.join(row_cells)} |\n"

                # Tự động vẽ đồ thị cho từng tham số theo năm
                chart_data = []
                for m in range(1, 13):
                    item = {"Thang": f"Tháng {m}"}
                    for y in years:
                        vals = []
                        for r in rows:
                            dt = parse_stats_date(safe_cell(r, col_date))
                            if dt and dt.year == y and dt.month == m:
                                v = extract_col_value(r, col, param)
                                if v is not None:
                                    vals.append(v)
                        item[str(y)] = round(sum(vals) / len(vals), 2) if vals else 0.0
                    chart_data.append(item)

                chart_json = {
                    "type": "line" if param == "water_level" else "bar",
                    "title": f"Biểu đồ {name.split(' (')[0]} trung bình tháng",
                    "data": chart_data,
                    "xKey": "Thang",
                    "yKeys": [str(y) for y in years],
                    "colors": ["#10b981", "#3b82f6", "#ef4444", "#f59e0b", "#06b6d4"],
                    "unit": " m" if param == "water_level" else " m³/s"
                }
                import json
                out += f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n"

                out += "\n---\n"

            out += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Sông Hinh"
            return out.strip()

        if period_type == "month":
            if period_value and "/" in period_value:
                m_s, y_s = period_value.split("/")
                month, year = int(m_s), int(y_s)
            else:
                month, year = current_month, current_year

            compare_month = None
            compare_year = year
            # N năm cùng kỳ (compare_years=2 → 3 cột, compare_years=3 → 4 cột): month/year, month/(year-1), ..., month/(year-N)
            periods_to_show: List[Tuple[int, int]] = []
            if compare_years >= 2:
                periods_to_show = [(month, year - i) for i in range(compare_years + 1)]
            elif compare_with_period_value and "/" in str(compare_with_period_value):
                try:
                    m2_s, y2_s = compare_with_period_value.strip().split("/")
                    compare_month, compare_year = int(m2_s), int(y2_s)
                    periods_to_show = [(month, year), (compare_month, compare_year)]
                except (ValueError, AttributeError):
                    pass
            elif compare:
                if month > 1:
                    compare_month = month - 1
                else:
                    compare_month = 12
                    compare_year = year - 1
                periods_to_show = [(month, year), (compare_month, compare_year)]

            # So sánh 2 hoặc 3 tháng: trả theo ngày (1–31). Không so sánh: trả theo tuần như cũ.
            if periods_to_show:
                import calendar
                max_day = 31
                for (m, y) in periods_to_show:
                    max_day = max(max_day, calendar.monthrange(y, m)[1])
                period_labels = ", ".join([f"Tháng {m}/{y}" for (m, y) in periods_to_show])
                out = f"""
### 📊 So sánh theo Ngày - Thủy điện Sông Hinh
**So sánh:** {period_labels} (từ ngày 1 đến ngày {max_day})
"""
                out += "\n---\n"
                for param in parameters:
                    col = col_qve if param == "qve" else col_water
                    name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                    out += f"\n#### {name}\n\n"
                    header_cols = [f"Tháng {m}/{y}" for (m, y) in periods_to_show]
                    out += "| Ngày | " + " | ".join(header_cols) + " |\n"
                    out += "|:---:|" + "|".join([":---:"] * len(periods_to_show)) + "|\n"
                    for d in range(1, max_day + 1):
                        cells = [f"**{d}**"]
                        for (m, y) in periods_to_show:
                            vals: List[float] = []
                            for r in rows:
                                dt = parse_stats_date(safe_cell(r, col_date))
                                if not dt or dt.year != y or dt.month != m or dt.day != d:
                                    continue
                                v = extract_col_value(r, col, param)
                                if v is not None:
                                    vals.append(v)
                            # Cột F đã là m³/s, không chia 1000
                            if param == "qve":
                                c = f"{sum(vals)/len(vals):.2f}" if vals else "-"
                            else:
                                c = f"{sum(vals)/len(vals):.2f}" if vals else "-"
                            cells.append(c)
                        out += "| " + " | ".join(cells) + " |\n"

                    # Thêm hàng trung bình cả tháng
                    avg_cells = ["**Trung bình**"]
                    for (m, y) in periods_to_show:
                        month_vals: List[float] = []
                        for d in range(1, max_day + 1):
                            for r in rows:
                                dt = parse_stats_date(safe_cell(r, col_date))
                                if not dt or dt.year != y or dt.month != m or dt.day != d:
                                    continue
                                v = extract_col_value(r, col, param)
                                if v is not None:
                                    month_vals.append(v)
                        if month_vals:
                            avg_cells.append(f"{sum(month_vals)/len(month_vals):.2f}")
                        else:
                            avg_cells.append("-")
                    out += "| " + " | ".join(avg_cells) + " |\n"

                    # Tự động vẽ đồ thị so sánh theo ngày
                    chart_data = []
                    for d in range(1, max_day + 1):
                        item = {"Ngay": str(d)}
                        for (m, y) in periods_to_show:
                            vals = []
                            for r in rows:
                                dt = parse_stats_date(safe_cell(r, col_date))
                                if dt and dt.year == y and dt.month == m and dt.day == d:
                                    v = extract_col_value(r, col, param)
                                    if v is not None:
                                        vals.append(v)
                            item[f"T{m}/{y}"] = round(sum(vals)/len(vals), 2) if vals else 0.0
                        chart_data.append(item)

                    chart_json = {
                        "type": "line",
                        "title": f"Biểu đồ so sánh {name.split(' (')[0]} hàng ngày",
                        "data": chart_data,
                        "xKey": "Ngay",
                        "yKeys": [f"T{m}/{y}" for (m, y) in periods_to_show],
                        "colors": ["#10b981", "#3b82f6", "#ef4444", "#f59e0b"],
                        "unit": " m" if param == "water_level" else " m³/s"
                    }
                    import json
                    out += f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n"

                    out += "\n---\n"
            else:
                # Thống kê cả tháng (từ ngày 1 đến ngày cuối tháng), không theo tuần
                import calendar
                last_day = calendar.monthrange(year, month)[1]
                out = f"""
### 📊 Thống kê tháng {month}/{year} - Thủy điện Sông Hinh
**Tháng:** {month}/{year} (từ ngày 1 đến ngày {last_day})
"""
                out += "\n---\n"
                for param in parameters:
                    col = col_qve if param == "qve" else col_water
                    name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                    out += f"\n#### {name}\n\n"
                    out += f"| Tháng {month}/{year} (Min/Max/Avg) |\n"
                    out += "|:---:|\n"
                    vals: List[float] = []
                    for r in rows:
                        dt = parse_stats_date(safe_cell(r, col_date))
                        if dt and dt.year == year and dt.month == month and 1 <= dt.day <= last_day:
                            v = extract_col_value(r, col, param)
                            if v is not None:
                                vals.append(v)
                    if vals:
                        if param == "qve":
                            min_val, max_val = min(vals), max(vals)
                            avg_val = sum(vals) / len(vals)
                            out += f"| {min_val:.2f}{_NBSP}/{_NBSP}{max_val:.2f}{_NBSP}/{_NBSP}{avg_val:.2f} |\n"
                        else:
                            out += f"| {min(vals):.2f}{_NBSP}/{_NBSP}{max(vals):.2f}{_NBSP}/{_NBSP}{sum(vals)/len(vals):.2f} |\n"
                        
                        # Tự động vẽ đồ thị hàng ngày trong tháng
                        day_vals = []
                        for r in rows:
                            dt = parse_stats_date(safe_cell(r, col_date))
                            if dt and dt.year == year and dt.month == month and 1 <= dt.day <= last_day:
                                v = extract_col_value(r, col, param)
                                if v is not None:
                                    day_vals.append((dt.day, v))
                        day_vals.sort()
                        chart_data = [{"Ngay": str(d), "GiaTri": round(val, 2)} for d, val in day_vals]
                        if chart_data:
                            chart_json = {
                                "type": "line",
                                "title": f"Biểu đồ {name.split(' (')[0]} hàng ngày tháng {month}/{year}",
                                "data": chart_data,
                                "xKey": "Ngay",
                                "yKeys": ["GiaTri"],
                                "colors": ["#3b82f6"],
                                "unit": " m" if param == "water_level" else " m³/s"
                            }
                            import json
                            out += f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n"
                    else:
                        out += "| -\n"
                    out += "\n---\n"

            out += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Sông Hinh"
            return out.strip()

        if period_type == "week":
            if period_value and period_value.count("/") == 2:
                w_s, m_s, y_s = period_value.split("/")
                week_num, month, year = int(w_s), int(m_s), int(y_s)
            else:
                week_num, month, year = current_week, current_month, current_year

            week_ranges = {1: (1, 7), 2: (8, 14), 3: (15, 21), 4: (22, 28), 5: (29, 31)}
            sd, ed = week_ranges.get(week_num, (1, 7))

            compare_week_num = None
            compare_month = month
            compare_year = year
            if compare:
                if week_num > 1:
                    compare_week_num = week_num - 1
                else:
                    compare_week_num = 5
                    if month > 1:
                        compare_month = month - 1
                    else:
                        compare_month = 12
                        compare_year = year - 1

            out = f"""
### 📊 Thống kê theo Ngày - Thủy điện Sông Hinh
**Tuần {week_num} tháng {month}/{year}** (ngày {sd}-{ed})
"""
            if compare and compare_week_num:
                cs, ce = week_ranges.get(compare_week_num, (1, 7))
                out += f"**So sánh với:** Tuần {compare_week_num} tháng {compare_month}/{compare_year} (ngày {cs}-{ce})\n"
            out += "\n---\n"

            for param in parameters:
                col = col_qve if param == "qve" else col_water
                name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
                out += f"\n#### {name}\n\n"

                if compare and compare_week_num:
                    out += f"| Ngày | {year} | {compare_year} |\n"
                    out += "|---|---:|---:|\n"
                else:
                    out += f"| Ngày | {year} |\n"
                    out += "|---|---:|\n"

                for d in range(sd, min(ed + 1, 32)):
                    def day_val(y: int, m: int, dd: int) -> str:
                        for r in rows:
                            dt = parse_stats_date(safe_cell(r, col_date))
                            if dt and dt.year == y and dt.month == m and dt.day == dd:
                                v = extract_col_value(r, col, param)
                                if v is not None:
                                    # Cột F đã là m³/s, không chia 1000
                                    if param == "qve":
                                        return f"{v:.2f}"
                                    else:
                                        return f"{v:.2f}"
                        return "-"

                    line = [f"**{d}/{month}**", day_val(year, month, d)]
                    if compare and compare_week_num:
                        line.append(day_val(compare_year, compare_month, d))
                    out += f"| {' | '.join(line)} |\n"

                # Tự động vẽ đồ thị cho tuần
                chart_data = []
                for d in range(sd, min(ed + 1, 32)):
                    item = {"Ngay": f"{d}/{month}"}
                    v_str_cur = day_val(year, month, d)
                    item[str(year)] = float(v_str_cur) if v_str_cur != "-" else 0.0
                    if compare and compare_week_num:
                        v_str_comp = day_val(compare_year, compare_month, d)
                        item[str(compare_year)] = float(v_str_comp) if v_str_comp != "-" else 0.0
                    chart_data.append(item)

                chart_json = {
                    "type": "bar" if param == "qve" else "line",
                    "title": f"Biểu đồ {name.split(' (')[0]} tuần {week_num} tháng {month}/{year}",
                    "data": chart_data,
                    "xKey": "Ngay",
                    "yKeys": [str(year)] + ([str(compare_year)] if (compare and compare_week_num) else []),
                    "colors": ["#3b82f6", "#10b981"],
                    "unit": " m" if param == "water_level" else " m³/s"
                }
                import json
                out += f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n"

                out += "\n---\n"

            out += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Sông Hinh"
            return out.strip()

        return "Lỗi: Loại khoảng thời gian không hợp lệ. Sử dụng 'year', 'month', hoặc 'week'."

    def _get_date_range_statistics(
        self,
        start_date: str,
        end_date: str,
        parameters: List[str],
        rows: List[List[str]],
        col_date: int,
        col_qve: int,
        col_water: int,
        parse_stats_date,
        extract_col_value
    ) -> str:
        """
        Thống kê theo ngày cho khoảng thời gian từ start_date đến end_date
        """
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

        start_dt = parse_date_str(start_date)
        end_dt = parse_date_str(end_date)

        if not start_dt or not end_dt:
            return f"### Lỗi\n\nKhông thể parse ngày. Sử dụng format DD/MM/YYYY (ví dụ: 1/1/2026)"

        if start_dt > end_dt:
            return f"### Lỗi\n\nNgày bắt đầu ({start_date}) phải nhỏ hơn hoặc bằng ngày kết thúc ({end_date})"

        out = f"""
### 📊 Thống kê theo Ngày - Thủy điện Sông Hinh
**Khoảng thời gian:** Từ {start_date} đến {end_date}
"""
        out += "\n---\n"

        for param in parameters:
            col = col_qve if param == "qve" else col_water
            name = "Lưu lượng về Qve (m³/s)" if param == "qve" else "Mực nước hồ (m)"
            out += f"\n#### {name}\n\n"

            # Hiển thị đúng đơn vị cho từng tham số
            unit = "m³/s" if param == "qve" else "m"
            out += f"| Ngày | Giá trị ({unit}) |\n"
            out += "|---|---:|\n"

            values_in_range: List[float] = []
            current_dt = start_dt
            while current_dt <= end_dt:
                day_str = f"**{current_dt.day}/{current_dt.month}/{current_dt.year}**"

                value_str = "-"
                for r in rows:
                    dt = parse_stats_date(safe_cell(r, col_date))
                    if dt and dt.year == current_dt.year and dt.month == current_dt.month and dt.day == current_dt.day:
                        v = extract_col_value(r, col, param)
                        if v is not None:
                            value_str = f"{v:.2f}"
                            values_in_range.append(v)
                        break

                out += f"| {day_str} | {value_str} |\n"
                current_dt += timedelta(days=1)

            avg_str = f"{sum(values_in_range) / len(values_in_range):.2f}" if values_in_range else "-"
            out += f"| **Trung bình** | {avg_str} |\n"

            # Tự động vẽ đồ thị cho khoảng ngày
            chart_data = []
            current_dt = start_dt
            while current_dt <= end_dt:
                for r in rows:
                    dt = parse_stats_date(safe_cell(r, col_date))
                    if dt and dt.year == current_dt.year and dt.month == current_dt.month and dt.day == current_dt.day:
                        v = extract_col_value(r, col, param)
                        if v is not None:
                            chart_data.append({
                                "Ngay": f"{current_dt.day}/{current_dt.month}",
                                "GiaTri": round(v, 2)
                            })
                        break
                current_dt += timedelta(days=1)

            if chart_data:
                chart_json = {
                    "type": "bar" if param == "qve" else "line",
                    "title": f"Biểu đồ biến động {name.split(' (')[0]}",
                    "data": chart_data,
                    "xKey": "Ngay",
                    "yKeys": ["GiaTri"],
                    "colors": ["#3b82f6"],
                    "unit": f" {unit}"
                }
                import json
                out += f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n"

            out += "\n---\n"

        out += "\n**Nguồn:** Google Sheets thống kê - Thủy điện Sông Hinh"
        return out.strip()
