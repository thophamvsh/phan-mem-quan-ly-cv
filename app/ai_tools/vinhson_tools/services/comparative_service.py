"""
Comparative analysis service - Compare data between time periods for Vĩnh Sơn
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from ..config.columns import COL_DATE, COL_RESERVOIR, COL_WATER_LEVEL, COL_INFLOW, COL_TURBINE, COL_SPILLWAY
from ..core.sheets_client import SheetsClient
from ..core.retry import retry_with_backoff
from ..utils.dates import normalize_date


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
        reservoir: str = "Vinh Son -A",
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
                return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets."

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
                    try:
                        if len(row) > col_idx and row[col_idx]:
                            val = float(row[col_idx].replace(',', '').replace('.', ''))
                            values.append(val)
                    except (ValueError, AttributeError):
                        pass
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

            def build_section_for_reservoir(res_name: str, cur_data: List, ly_data: List) -> str:
                """Build comparison section for a single reservoir"""
                section = ""

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
                return section

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
            if use_all:
                # Process each reservoir separately
                for idx, res_name in enumerate(RESERVOIR_NAMES, 1):
                    cur_data = cur_data_by_res.get(res_name, [])
                    ly_data = ly_data_by_res.get(res_name, [])

                    if not cur_data:
                        result += f"##### Bảng {idx}: {res_name}\n\n*Không có dữ liệu năm nay*\n\n---\n\n"
                        continue
                    if not ly_data:
                        result += f"##### Bảng {idx}: {res_name}\n\n*Không có dữ liệu cùng kỳ năm trước*\n\n---\n\n"
                        continue

                    result += f"##### Bảng {idx}: {res_name}\n\n"
                    result += build_section_for_reservoir(res_name, cur_data, ly_data)
                    result += "\n---\n\n"
            else:
                # Single reservoir mode (original behavior)
                result += build_section_for_reservoir(reservoir, current_period_data, last_year_period_data)

            result += "\n**Nguồn:** Google Sheets - Thủy điện Vĩnh Sơn"
            return result.strip()

        except ValueError as e:
            return f"Lỗi định dạng ngày: {e}. Vui lòng dùng format DD/MM/YYYY"
        except Exception as e:
            error_msg = f"Lỗi khi phân tích dữ liệu: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            return error_msg
