"""
Comparative analysis service - Compare data between time periods for Vĩnh Sơn
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import json
from ..config.columns import COL_DATE, COL_RESERVOIR, COL_WATER_LEVEL, COL_INFLOW, COL_TURBINE, COL_SPILLWAY
from ..core.sheets_client import SheetsClient
from ..core.retry import retry_with_backoff
from ..utils.dates import normalize_date
from ..utils.numbers import parse_float_loose, safe_cell


# Map reservoir name to index for multi-reservoir support
RES_MAP = {"Vinh Son -A": 0, "Vinh Son -B": 1, "Vinh Son -C": 2}
RESERVOIR_NAMES = ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"]


class ComparativeAnalysisService:
    """Service for comparative analysis between time periods"""

    def __init__(self):
        self.sheets_client = SheetsClient()

    def get_comparative_analysis(
        self,
        start_date: str,
        end_date: str,
        reservoir: str = "All",
        parameters: Optional[List[str]] = None
    ) -> str:
        """
        Phân tích so sánh dữ liệu giữa 2 khoảng thời gian (năm nay vs cùng kỳ năm trước)

        Args:
            reservoir: "Vinh Son -A", "Vinh Son -B", "Vinh Son -C", hoặc "All" để hiển thị cả 3 hồ
        """
        print(f"[INFO] VINH SON TOOL: Comparative analysis from {start_date} to {end_date}, reservoir={reservoir}, parameters={parameters}", flush=True)

        if not parameters:
            parameters = ["water_level", "inflow", "turbine", "spillway"]

        # Check if user wants all reservoirs
        use_all = reservoir in (None, "All", "")
        res_to_process = RESERVOIR_NAMES if use_all else [reservoir]

        # Validate reservoirs exist
        if not use_all and reservoir not in RESERVOIR_NAMES:
            return f"Hồ không hợp lệ: {reservoir}. Vui lòng chọn: Vinh Son -A, Vinh Son -B, Vinh Son -C, hoặc All"

        try:
            start_obj = datetime.strptime(start_date, '%d/%m/%Y')
            end_obj = datetime.strptime(end_date, '%d/%m/%Y')

            start_last_year = start_obj.replace(year=start_obj.year - 1)
            end_last_year = end_obj.replace(year=end_obj.year - 1)

            client, worksheet, worksheet_hours = self.sheets_client.get_client()

            if not worksheet:
                return "### Lỗi kết nối CSDL thongsothuyvan\n\nKhông thể kết nối CSDL thongsothuyvan."

            def fetch_data():
                return worksheet.get_all_values()

            all_data = retry_with_backoff(fetch_data, max_retries=3, initial_delay=1)
            if len(all_data) < 3:
                return "Không có dữ liệu"
            data_rows = all_data[2:]

            current_period_data = []
            last_year_period_data = []

            for row in data_rows:
                if len(row) > COL_RESERVOIR:
                    reservoir_name = row[COL_RESERVOIR].strip()
                    row_date_str = row[COL_DATE].strip()

                    # Filter by reservoir if not using all
                    if not use_all and reservoir_name != reservoir:
                        continue
                    if use_all and reservoir_name not in RESERVOIR_NAMES:
                        continue
                    if not row_date_str:
                        continue

                    row_date = normalize_date(row_date_str)
                    if not row_date:
                        continue

                    if start_obj.date() <= row_date <= end_obj.date():
                        current_period_data.append(row)

                    if start_last_year.date() <= row_date <= end_last_year.date():
                        last_year_period_data.append(row)

            # Group data by reservoir for multi-reservoir mode
            def get_data_by_reservoir(data_list):
                result = {res: [] for res in RESERVOIR_NAMES}
                for row in data_list:
                    if len(row) > COL_RESERVOIR:
                        res_name = row[COL_RESERVOIR].strip()
                        if res_name in result:
                            result[res_name].append(row)
                return result

            cur_data_by_res = get_data_by_reservoir(current_period_data)
            ly_data_by_res = get_data_by_reservoir(last_year_period_data)

            if not current_period_data:
                return f"Không tìm thấy dữ liệu cho hồ {reservoir} trong khoảng thời gian {start_date} đến {end_date}"

            if not last_year_period_data:
                return f"Không tìm thấy dữ liệu cùng kỳ năm trước cho hồ {reservoir} ({start_last_year.strftime('%d/%m/%Y')} đến {end_last_year.strftime('%d/%m/%Y')})"

            def extract_values(data, col_idx):
                values = []
                for row in data:
                    val = parse_float_loose(safe_cell(row, col_idx))
                    if val is not None:
                        values.append(val)
                return values

            def calc_stats(values):
                if not values:
                    return {"min": 0, "max": 0, "avg": 0, "total": 0, "count": 0}
                return {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "total": sum(values),
                    "count": len(values)
                }

            def build_section_for_reservoir(res_name: str, cur_data: List, ly_data: List) -> Tuple[str, List[List[Any]]]:
                """Build comparison section and excel rows for a single reservoir"""
                section = ""
                excel_rows = []

                if "water_level" in parameters:
                    wl_current = extract_values(cur_data, COL_WATER_LEVEL)
                    wl_last_year = extract_values(ly_data, COL_WATER_LEVEL)

                    stats_current = calc_stats(wl_current)
                    stats_last_year = calc_stats(wl_last_year)

                    avg_change = stats_current['avg'] - stats_last_year['avg']
                    avg_change_pct = (avg_change / stats_last_year['avg'] * 100) if stats_last_year['avg'] > 0 else 0

                    section += f"""
#### 📊 Mực nước thượng lưu (m)

| Chỉ số | Năm nay | Cùng kỳ năm trước | Thay đổi |
|--------|---------|-------------------|----------|
| **Thấp nhất** | {stats_current['min']:.2f} m | {stats_last_year['min']:.2f} m | {stats_current['min'] - stats_last_year['min']:+.2f} m |
| **Cao nhất** | {stats_current['max']:.2f} m | {stats_last_year['max']:.2f} m | {stats_current['max'] - stats_last_year['max']:+.2f} m |
| **Trung bình** | {stats_current['avg']:.2f} m | {stats_last_year['avg']:.2f} m | {avg_change:+.2f} m ({avg_change_pct:+.1f}%) |
| **Biên độ** | {stats_current['max'] - stats_current['min']:.2f} m | {stats_last_year['max'] - stats_last_year['min']:.2f} m | - |
"""
                    excel_rows.extend([
                        ["Mực nước thượng lưu (m)"],
                        ["Chỉ số", "Năm nay", "Cùng kỳ năm trước", "Thay đổi"],
                        ["Thấp nhất", round(stats_current['min'], 2), round(stats_last_year['min'], 2), f"{stats_current['min'] - stats_last_year['min']:+.2f} m"],
                        ["Cao nhất", round(stats_current['max'], 2), round(stats_last_year['max'], 2), f"{stats_current['max'] - stats_last_year['max']:+.2f} m"],
                        ["Trung bình", round(stats_current['avg'], 2), round(stats_last_year['avg'], 2), f"{avg_change:+.2f} m ({avg_change_pct:+.1f}%)"],
                        ["Biên độ", round(stats_current['max'] - stats_current['min'], 2), round(stats_last_year['max'] - stats_last_year['min'], 2), "-"],
                        []
                    ])

                if "inflow" in parameters:
                    inflow_current = extract_values(cur_data, COL_INFLOW)
                    inflow_last_year = extract_values(ly_data, COL_INFLOW)

                    stats_current = calc_stats(inflow_current)
                    stats_last_year = calc_stats(inflow_last_year)

                    avg_change = stats_current['avg'] - stats_last_year['avg']
                    avg_change_pct = (avg_change / stats_last_year['avg'] * 100) if stats_last_year['avg'] > 0 else 0
                    total_change = stats_current['total'] - stats_last_year['total']
                    total_change_pct = (total_change / stats_last_year['total'] * 100) if stats_last_year['total'] > 0 else 0

                    section += f"""
#### 💧 Lưu lượng về - Qve (m³/s)

| Chỉ số | Năm nay | Cùng kỳ năm trước | Thay đổi |
|--------|---------|-------------------|----------|
| **Thấp nhất** | {stats_current['min']:.2f} m³/s | {stats_last_year['min']:.2f} m³/s | {stats_current['min'] - stats_last_year['min']:+.2f} m³/s |
| **Cao nhất** | {stats_current['max']:.2f} m³/s | {stats_last_year['max']:.2f} m³/s | {stats_current['max'] - stats_last_year['max']:+.2f} m³/s |
| **Trung bình** | {stats_current['avg']:.2f} m³/s | {stats_last_year['avg']:.2f} m³/s | {avg_change:+.2f} m³/s ({avg_change_pct:+.1f}%) |
| **Tổng lưu lượng** | {stats_current['total']:,.0f} m³/s | {stats_last_year['total']:,.0f} m³/s | {total_change:+,.0f} m³/s ({total_change_pct:+.1f}%) |
"""
                    excel_rows.extend([
                        ["Lưu lượng về - Qve (m³/s)"],
                        ["Chỉ số", "Năm nay", "Cùng kỳ năm trước", "Thay đổi"],
                        ["Thấp nhất", round(stats_current['min'], 2), round(stats_last_year['min'], 2), f"{stats_current['min'] - stats_last_year['min']:+.2f} m³/s"],
                        ["Cao nhất", round(stats_current['max'], 2), round(stats_last_year['max'], 2), f"{stats_current['max'] - stats_last_year['max']:+.2f} m³/s"],
                        ["Trung bình", round(stats_current['avg'], 2), round(stats_last_year['avg'], 2), f"{avg_change:+.2f} m³/s ({avg_change_pct:+.1f}%)"],
                        ["Tổng lưu lượng", round(stats_current['total'], 0), round(stats_last_year['total'], 0), f"{total_change:+,.0f} m³/s ({total_change_pct:+.1f}%)"],
                        []
                    ])

                if "turbine" in parameters:
                    turbine_current = extract_values(cur_data, COL_TURBINE)
                    turbine_last_year = extract_values(ly_data, COL_TURBINE)

                    stats_current = calc_stats(turbine_current)
                    stats_last_year = calc_stats(turbine_last_year)

                    avg_change = stats_current['avg'] - stats_last_year['avg']
                    avg_change_pct = (avg_change / stats_last_year['avg'] * 100) if stats_last_year['avg'] > 0 else 0

                    section += f"""
#### ⚙️ Lưu lượng chạy máy - Qcm (m³/s)

| Chỉ số | Năm nay | Cùng kỳ năm trước | Thay đổi |
|--------|---------|-------------------|----------|
| **Thấp nhất** | {stats_current['min']:.2f} m³/s | {stats_last_year['min']:.2f} m³/s | {stats_current['min'] - stats_last_year['min']:+.2f} m³/s |
| **Cao nhất** | {stats_current['max']:.2f} m³/s | {stats_last_year['max']:.2f} m³/s | {stats_current['max'] - stats_last_year['max']:+.2f} m³/s |
| **Trung bình** | {stats_current['avg']:.2f} m³/s | {stats_last_year['avg']:.2f} m³/s | {avg_change:+.2f} m³/s ({avg_change_pct:+.1f}%) |
"""
                    excel_rows.extend([
                        ["Lưu lượng chạy máy - Qcm (m³/s)"],
                        ["Chỉ số", "Năm nay", "Cùng kỳ năm trước", "Thay đổi"],
                        ["Thấp nhất", round(stats_current['min'], 2), round(stats_last_year['min'], 2), f"{stats_current['min'] - stats_last_year['min']:+.2f} m³/s"],
                        ["Cao nhất", round(stats_current['max'], 2), round(stats_last_year['max'], 2), f"{stats_current['max'] - stats_last_year['max']:+.2f} m³/s"],
                        ["Trung bình", round(stats_current['avg'], 2), round(stats_last_year['avg'], 2), f"{avg_change:+.2f} m³/s ({avg_change_pct:+.1f}%)"],
                        []
                    ])

                if "spillway" in parameters:
                    spillway_current = extract_values(cur_data, COL_SPILLWAY)
                    spillway_last_year = extract_values(ly_data, COL_SPILLWAY)

                    stats_current = calc_stats(spillway_current)
                    stats_last_year = calc_stats(spillway_last_year)

                    avg_change = stats_current['avg'] - stats_last_year['avg']
                    avg_change_pct = (avg_change / stats_last_year['avg'] * 100) if stats_last_year['avg'] > 0 else 0

                    section += f"""
#### 🌊 Lưu lượng xả lũ - Qxl (m³/s)

| Chỉ số | Năm nay | Cùng kỳ năm trước | Thay đổi |
|--------|---------|-------------------|----------|
| **Thấp nhất** | {stats_current['min']:.2f} m³/s | {stats_last_year['min']:.2f} m³/s | {stats_current['min'] - stats_last_year['min']:+.2f} m³/s |
| **Cao nhất** | {stats_current['max']:.2f} m³/s | {stats_last_year['max']:.2f} m³/s | {stats_current['max'] - stats_last_year['max']:+.2f} m³/s |
| **Trung bình** | {stats_current['avg']:.2f} m³/s | {stats_last_year['avg']:.2f} m³/s | {avg_change:+.2f} m³/s ({avg_change_pct:+.1f}%) |
"""
                    excel_rows.extend([
                        ["Lưu lượng xả lũ - Qxl (m³/s)"],
                        ["Chỉ số", "Năm nay", "Cùng kỳ năm trước", "Thay đổi"],
                        ["Thấp nhất", round(stats_current['min'], 2), round(stats_last_year['min'], 2), f"{stats_current['min'] - stats_last_year['min']:+.2f} m³/s"],
                        ["Cao nhất", round(stats_current['max'], 2), round(stats_last_year['max'], 2), f"{stats_current['max'] - stats_last_year['max']:+.2f} m³/s"],
                        ["Trung bình", round(stats_current['avg'], 2), round(stats_last_year['avg'], 2), f"{avg_change:+.2f} m³/s ({avg_change_pct:+.1f}%)"],
                        []
                    ])

                return section, excel_rows

            # Build result header
            cur_year = start_obj.year
            ly_year = start_obj.year - 1

            if use_all:
                res_label = "cả 3 hồ A, B, C"
            else:
                res_label = reservoir

            result = f"""
### Phân tích So sánh - Thủy điện Vĩnh Sơn ({res_label})

**Khoảng thời gian:**
- **Năm nay:** {start_date} đến {end_date} ({len(current_period_data)} ngày)
- **Cùng kỳ năm trước:** {start_last_year.strftime('%d/%m/%Y')} đến {end_last_year.strftime('%d/%m/%Y')} ({len(last_year_period_data)} ngày)

---

"""
            # Build sections for each reservoir
            excel_sheets = []
            for idx, res_name in enumerate(res_to_process, 1):
                cur_data = cur_data_by_res.get(res_name, [])
                ly_data = ly_data_by_res.get(res_name, [])

                if not cur_data and not ly_data:
                    continue

                if use_all:
                    result += f"##### Bảng {idx}: {res_name}\n\n"
                
                if not cur_data:
                    result += f"*Không có dữ liệu năm nay cho hồ {res_name}*\n\n"
                elif not ly_data:
                    result += f"*Không có dữ liệu cùng kỳ năm trước cho hồ {res_name}*\n\n"
                else:
                    sect, sec_excel_rows = build_section_for_reservoir(res_name, cur_data, ly_data)
                    result += sect

                    # Xây dựng các dòng dữ liệu cho worksheet này
                    sheet_rows = [
                        [f"BÁO CÁO PHÂN TÍCH SO SÁNH - HỒ CHỨA {res_name.upper()}"],
                        [f"Năm nay: {start_date} đến {end_date} ({len(current_period_data)} ngày)"],
                        [f"Cùng kỳ năm trước: {start_last_year.strftime('%d/%m/%Y')} đến {end_last_year.strftime('%d/%m/%Y')} ({len(last_year_period_data)} ngày)"],
                        [],
                    ]
                    sheet_rows.extend(sec_excel_rows)

                    sheet_title = res_name.replace("Vinh Son -", "Ho ")
                    excel_sheets.append({
                        "name": sheet_title,
                        "rows": sheet_rows
                    })
            # Build conclusion section
            conclusion_items = []
            for res_name in res_to_process:
                cur_data = cur_data_by_res.get(res_name, [])
                ly_data = ly_data_by_res.get(res_name, [])
                if not cur_data or not ly_data:
                    continue

                res_conclusions = []
                lbl_map = {"Vinh Son -A": "Hồ A", "Vinh Son -B": "Hồ B", "Vinh Son -C": "Hồ C"}
                res_label = lbl_map.get(res_name, res_name)

                if "water_level" in parameters:
                    wl_current = extract_values(cur_data, COL_WATER_LEVEL)
                    wl_last_year = extract_values(ly_data, COL_WATER_LEVEL)
                    sc = calc_stats(wl_current)
                    sl = calc_stats(wl_last_year)
                    avg_change = sc['avg'] - sl['avg']
                    avg_change_pct = (avg_change / sl['avg'] * 100) if sl['avg'] > 0 else 0
                    direction = "tăng" if avg_change > 0 else "giảm"
                    if avg_change != 0:
                        res_conclusions.append(f"  - **Mực nước thượng lưu**: Trung bình đạt `{sc['avg']:.2f} m`, {direction} `{abs(avg_change):.2f} m` ({avg_change_pct:+.1f}%) so với cùng kỳ năm trước (trung bình `{sl['avg']:.2f} m`).")

                if "inflow" in parameters:
                    inflow_current = extract_values(cur_data, COL_INFLOW)
                    inflow_last_year = extract_values(ly_data, COL_INFLOW)
                    sc = calc_stats(inflow_current)
                    sl = calc_stats(inflow_last_year)
                    avg_change = sc['avg'] - sl['avg']
                    avg_change_pct = (avg_change / sl['avg'] * 100) if sl['avg'] > 0 else 0
                    direction = "tăng" if avg_change > 0 else "giảm"
                    if avg_change != 0:
                        res_conclusions.append(f"  - **Lưu lượng nước về (Qve)**: Trung bình đạt `{sc['avg']:.2f} m³/s`, {direction} `{abs(avg_change):.2f} m³/s` ({avg_change_pct:+.1f}%) so với cùng kỳ năm trước (trung bình `{sl['avg']:.2f} m³/s`).")

                if "turbine" in parameters:
                    turbine_current = extract_values(cur_data, COL_TURBINE)
                    turbine_last_year = extract_values(ly_data, COL_TURBINE)
                    sc = calc_stats(turbine_current)
                    sl = calc_stats(turbine_last_year)
                    avg_change = sc['avg'] - sl['avg']
                    avg_change_pct = (avg_change / sl['avg'] * 100) if sl['avg'] > 0 else 0
                    direction = "tăng" if avg_change > 0 else "giảm"
                    if avg_change != 0:
                        res_conclusions.append(f"  - **Lưu lượng qua máy (Qcm)**: Trung bình đạt `{sc['avg']:.2f} m³/s`, {direction} `{abs(avg_change):.2f} m³/s` ({avg_change_pct:+.1f}%) so với cùng kỳ năm trước (trung bình `{sl['avg']:.2f} m³/s`).")

                if "spillway" in parameters:
                    spillway_current = extract_values(cur_data, COL_SPILLWAY)
                    spillway_last_year = extract_values(ly_data, COL_SPILLWAY)
                    sc = calc_stats(spillway_current)
                    sl = calc_stats(spillway_last_year)
                    avg_change = sc['avg'] - sl['avg']
                    avg_change_pct = (avg_change / sl['avg'] * 100) if sl['avg'] > 0 else 0
                    direction = "tăng" if avg_change > 0 else "giảm"
                    if avg_change != 0:
                        res_conclusions.append(f"  - **Lưu lượng xả lũ (Qxl)**: Trung bình đạt `{sc['avg']:.2f} m³/s`, {direction} `{abs(avg_change):.2f} m³/s` ({avg_change_pct:+.1f}%) so với cùng kỳ năm trước (trung bình `{sl['avg']:.2f} m³/s`).")

                if res_conclusions:
                    conclusion_items.append(f"**{res_label}:**\n" + "\n".join(res_conclusions))

            if conclusion_items:
                result += "### 📌 Kết luận Phân tích So sánh\n\n" + "\n\n".join(conclusion_items) + "\n\n"

            result += "\n---\n\n"
            chart_sections = []
            for res_name in res_to_process:
                cur_data = cur_data_by_res.get(res_name, [])
                ly_data = ly_data_by_res.get(res_name, [])
                if not cur_data and not ly_data:
                    continue

                for param in parameters:
                    if param == "water_level":
                        col_idx = COL_WATER_LEVEL
                        label = "Mực nước thượng lưu"
                        unit = " m"
                        chart_type = "line"
                    elif param == "inflow":
                        col_idx = COL_INFLOW
                        label = "Lưu lượng về Qve"
                        unit = " m³/s"
                        chart_type = "line"
                    elif param == "turbine":
                        col_idx = COL_TURBINE
                        label = "Lưu lượng chạy máy Qcm"
                        unit = " m³/s"
                        chart_type = "line"
                    elif param == "spillway":
                        col_idx = COL_SPILLWAY
                        label = "Lưu lượng xả lũ Qxl"
                        unit = " m³/s"
                        chart_type = "line"
                    else:
                        continue

                    chart_data = []
                    max_len = max(len(cur_data), len(ly_data))
                    for idx in range(max_len):
                        item = {"Ngay": f"N{idx+1}"}
                        if idx < len(cur_data):
                            val_cur = parse_float_loose(safe_cell(cur_data[idx], col_idx))
                            if val_cur is not None:
                                item["NamNay"] = round(val_cur, 2)
                                d_str = safe_cell(cur_data[idx], COL_DATE)
                                if "/" in d_str:
                                    item["Ngay"] = "/".join(d_str.split("/")[:2])
                        if idx < len(ly_data):
                            val_ly = parse_float_loose(safe_cell(ly_data[idx], col_idx))
                            if val_ly is not None:
                                item["NamNgoai"] = round(val_ly, 2)
                        chart_data.append(item)

                    if chart_data:
                        chart_json = {
                            "type": chart_type,
                            "title": f"So sánh {label} - {res_name} (Năm nay vs Năm ngoái)" if use_all else f"So sánh {label} (Năm nay vs Năm ngoái)",
                            "data": chart_data,
                            "xKey": "Ngay",
                            "yKeys": ["NamNay", "NamNgoai"],
                            "colors": ["#3b82f6", "#10b981"],
                            "unit": unit
                        }
                        chart_sections.append(f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n")

            if chart_sections:
                result += "\n\n---\n\n" + "\n\n".join(chart_sections)

            # Thêm block xuất file excel
            if excel_sheets:
                excel_report_json = {
                    "title": f"Báo cáo so sánh Vĩnh Sơn ({start_date.replace('/', '')}_{end_date.replace('/', '')})",
                    "fileName": f"bao-cao-so-sanh-vinh-son-{start_date.replace('/', '-')}-den-{end_date.replace('/', '-')}.xlsx",
                    "prompt": "Bạn có cần xuất file Excel để báo cáo không?",
                    "sheets": excel_sheets
                }
                result += f"\n\n```excel\n{json.dumps(excel_report_json, ensure_ascii=False, indent=2)}\n```\n"

            result += "\n\n---\n\n**Nguồn:** CSDL thongsothuyvan - Thủy điện Vĩnh Sơn"
            return result.strip()

        except ValueError as e:
            return f"Lỗi định dạng ngày: {e}. Vui lòng dùng format DD/MM/YYYY"
        except Exception as e:
            error_msg = f"Lỗi khi phân tích dữ liệu: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            return error_msg
