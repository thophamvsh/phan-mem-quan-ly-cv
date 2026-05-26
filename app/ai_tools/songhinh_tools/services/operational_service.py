"""
Operational service - Get operational data for Sông Hinh
"""

from datetime import datetime, date
from typing import Dict, List, Optional
from ..config.columns import OP_COLS
from ..core.sheets_client import GoogleSheetsClientManager
from ..utils.dates import parse_dmy_to_date
from ..utils.numbers import safe_cell, parse_float_loose, fmt_pct
from .hours_service import HoursService


class OperationalService:
    def __init__(self, manager: GoogleSheetsClientManager, op_cols=None, hours_service: Optional[HoursService] = None):
        self.mgr = manager
        self.cols = op_cols or OP_COLS
        self.hours = hours_service

    @staticmethod
    def connection_error_markdown() -> str:
        return """### Lỗi kết nối Google Sheets

Không thể kết nối Google Sheets. Vui lòng kiểm tra:

1. **Service Account File**: Kiểm tra file `ai-project-484022-8239457b26bb.json` có tồn tại
2. **Google Sheets API**: Đảm bảo đã enable Google Sheets API trong Google Cloud Console
3. **Spreadsheet Sharing**: Kiểm tra spreadsheet đã được share với service account email
4. **Worksheet Name**: Kiểm tra tên sheet là "Sản lượng"

Xem console log để biết chi tiết lỗi.
"""

    def _find_rows_by_date(self, data_rows: List[List[str]], target: date) -> List[List[str]]:
        out = []
        for row in data_rows:
            row_date = parse_dmy_to_date(safe_cell(row, self.cols.COL_DATE))
            if row_date == target:
                out.append(row)
        return out

    def _find_rows_by_date_range(self, data_rows: List[List[str]], start: date, end: date) -> List[List[str]]:
        out = []
        for row in data_rows:
            row_date = parse_dmy_to_date(safe_cell(row, self.cols.COL_DATE))
            if row_date and start <= row_date <= end:
                out.append(row)
        # Sort by date
        out.sort(key=lambda r: parse_dmy_to_date(safe_cell(r, self.cols.COL_DATE)) or date.min)
        return out

    def get_operational_data(self, date_str: Optional[str] = None, num_days: int = 7, start_date_str: Optional[str] = None, end_date_str: Optional[str] = None) -> str:
        print(f"[INFO] SONG HINH TOOL: Getting operational data (date={date_str}, num_days={num_days}, start_date={start_date_str}, end_date={end_date_str})", flush=True)

        ws_operational, ws_hours = self.mgr.get_read_worksheets()
        if not ws_operational:
            return self.connection_error_markdown()

        all_data = self.mgr.get_all_values_cached(ws_operational, cache_key="operational_all_values")
        if len(all_data) < 3:
            return "Không có dữ liệu trong Google Sheets"

        data_rows = all_data[2:]

        filtered: List[List[str]] = []
        filtered_last_year: List[List[str]] = []

        if start_date_str and end_date_str:
            # Date range query: get all data between start_date and end_date
            try:
                start_obj = datetime.strptime(start_date_str, "%d/%m/%Y")
                end_obj = datetime.strptime(end_date_str, "%d/%m/%Y")
                start_date_obj = start_obj.date()
                end_date_obj = end_obj.date()

                filtered = self._find_rows_by_date_range(data_rows, start_date_obj, end_date_obj)

                if not filtered:
                    return f"Không tìm thấy dữ liệu cho khoảng thời gian từ {start_date_str} đến {end_date_str}"

                # Build horizontal table for date range
                result = f"""
### Dữ liệu vận hành Thủy điện Sông Hinh

**Khoảng thời gian:** {start_date_str} đến {end_date_str}
**Số ngày:** {len(filtered)} ngày

---

#### Thông số thủy văn

| Ngày | Mực nước (m) | Dung tích (tr.m³) | Qve (m³/s) | Qcm (m³/s) | Qxl (m³/s) |
|--------|--------------|-------------------|------------|------------|------------|
"""
                for row in filtered:
                    result += (
                        f"| {safe_cell(row, self.cols.COL_DATE)}"
                        f" | {safe_cell(row, self.cols.COL_WATER_LEVEL)}"
                        f" | {safe_cell(row, self.cols.COL_VOLUME)}"
                        f" | {safe_cell(row, self.cols.COL_INFLOW)}"
                        f" | {safe_cell(row, self.cols.COL_TURBINE)}"
                        f" | {safe_cell(row, self.cols.COL_SPILLWAY)} |\n"
                    )

                result += """

---

#### Sản lượng điện (ngày)

| Ngày | Đầu cực ngày | Thương phẩm ngày | Qc ngày |
|------|--------------|--------------|--------------|
"""
                for row in filtered:
                    result += (
                        f"| {safe_cell(row, self.cols.COL_DATE)}"
                        f" | {safe_cell(row, self.cols.COL_OUTPUT_DAY)}"
                        f" | {safe_cell(row, self.cols.COL_COMMERCIAL_DAY)}"
                        f" | {safe_cell(row, self.cols.COL_QC_DAY)} |\n"
                    )

                result += """

---

#### Sản lượng điện (tháng)

| Ngày | Đầu cực tháng | Thương phẩm tháng | Qc tháng |
|------|---------------|--------------|--------------|
"""
                for row in filtered:
                    result += (
                        f"| {safe_cell(row, self.cols.COL_DATE)}"
                        f" | {safe_cell(row, self.cols.COL_OUTPUT_MONTH)}"
                        f" | {safe_cell(row, self.cols.COL_COMMERCIAL_MONTH)}"
                        f" | {safe_cell(row, self.cols.COL_QC_MONTH_ACC)} |\n"
                    )

                result += """

---

#### Sản lượng điện (năm)

| Ngày | Đầu cực năm | Thương phẩm năm | Qc năm | Tự dùng |
|-----------|-----------------|-----------------|-----------------|----------|
"""
                for row in filtered:
                    result += (
                        f"| {safe_cell(row, self.cols.COL_DATE)}"
                        f" | {safe_cell(row, self.cols.COL_OUTPUT_YEAR)}"
                        f" | {safe_cell(row, self.cols.COL_COMMERCIAL_YEAR)}"
                        f" | {safe_cell(row, self.cols.COL_QC_YEAR_ACC)}"
                        f" | {safe_cell(row, self.cols.COL_SELF_USE)} |\n"
                    )

                result += "\n---\n\n**Nguồn:** Google Sheets - Thủy điện Sông Hinh"
                return result.strip()

            except ValueError:
                return f"Lỗi định dạng ngày. Vui lòng dùng format DD/MM/YYYY (ví dụ: 01/01/2026)"

        elif date_str:
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            target = date_obj.date()
            target_last_year = date(date_obj.year - 1, date_obj.month, date_obj.day)

            filtered = self._find_rows_by_date(data_rows, target)
            filtered_last_year = self._find_rows_by_date(data_rows, target_last_year)

            if not filtered:
                return f"Không tìm thấy dữ liệu cho ngày {date_str}"

            # Single day: vertical comparison
            current = filtered[0]
            last = filtered_last_year[0] if filtered_last_year else None

            def c(idx: int, default: str = "-") -> str:
                val = safe_cell(current, idx, default)
                # Return default only if val is truly empty (after strip)
                return val if val else default

            def ly(idx: int, default: str = "-") -> str:
                if not last:
                    return default
                val = safe_cell(last, idx, default)
                # Return default only if val is truly empty (after strip)
                return val if val else default

            date_current = c(self.cols.COL_DATE, "-")
            date_last_year = ly(self.cols.COL_DATE, "N/A")

            water_level_current = c(self.cols.COL_WATER_LEVEL)
            volume_current = c(self.cols.COL_VOLUME)
            inflow_current = c(self.cols.COL_INFLOW)
            turbine_current = c(self.cols.COL_TURBINE)
            spillway_current = c(self.cols.COL_SPILLWAY)

            output_day_current = c(self.cols.COL_OUTPUT_DAY)
            commercial_day_current = c(self.cols.COL_COMMERCIAL_DAY)
            # Ngày 1 tháng: "tháng" = lũy kế tháng = chỉ ngày đó; sheet có thể ghi nhầm tổng tháng trước
            if target.day == 1:
                output_month_current = output_day_current
                commercial_month_current = commercial_day_current
            else:
                output_month_current = c(self.cols.COL_OUTPUT_MONTH)
                commercial_month_current = c(self.cols.COL_COMMERCIAL_MONTH)
            output_year_current = c(self.cols.COL_OUTPUT_YEAR)
            commercial_year_current = c(self.cols.COL_COMMERCIAL_YEAR)
            plan_year_current = c(self.cols.COL_PLAN_YEAR)
            self_use_current = c(self.cols.COL_SELF_USE)

            water_level_last = ly(self.cols.COL_WATER_LEVEL)
            volume_last = ly(self.cols.COL_VOLUME)
            inflow_last = ly(self.cols.COL_INFLOW)
            turbine_last = ly(self.cols.COL_TURBINE)
            spillway_last = ly(self.cols.COL_SPILLWAY)

            output_day_last = ly(self.cols.COL_OUTPUT_DAY)
            commercial_day_last = ly(self.cols.COL_COMMERCIAL_DAY)
            output_month_last = ly(self.cols.COL_OUTPUT_MONTH)
            commercial_month_last = ly(self.cols.COL_COMMERCIAL_MONTH)
            output_year_last = ly(self.cols.COL_OUTPUT_YEAR)
            commercial_year_last = ly(self.cols.COL_COMMERCIAL_YEAR)
            plan_year_last = ly(self.cols.COL_PLAN_YEAR)
            self_use_last = ly(self.cols.COL_SELF_USE)

            # percent complete
            def pct_complete(plan_s: str, commercial_s: str) -> str:
                plan = parse_float_loose(plan_s)
                comm = parse_float_loose(commercial_s)
                if plan is None or comm is None or plan <= 0:
                    print(f"[DEBUG] pct_complete failed: plan_s='{plan_s}' -> {plan}, comm_s='{commercial_s}' -> {comm}", flush=True)
                    return "-"
                result = fmt_pct(comm / plan * 100.0, digits=2)
                print(f"[DEBUG] pct_complete success: {comm}/{plan}*100 = {result}", flush=True)
                return result

            percent_complete_current = pct_complete(plan_year_current, commercial_year_current)
            percent_complete_last = pct_complete(plan_year_last, commercial_year_last) if last else "-"

            # hours data
            if self.hours:
                hours_current = self.hours.get_hours_data(date_obj, ws_hours)
                hours_last = self.hours.get_hours_data(date_obj.replace(year=date_obj.year - 1), ws_hours)

                def get_unit(units: List[Dict[str, str]], unit: str, field: str, default: str = "-") -> str:
                    for u in units:
                        if u.get("unit") == unit:
                            return u.get(field, default) or default
                    return default

                tm1_op_cur = get_unit(hours_current["units"], "1", "hours_operating")
                tm2_op_cur = get_unit(hours_current["units"], "2", "hours_operating")
                tm1_stop_cur = get_unit(hours_current["units"], "1", "hours_stopped")
                tm2_stop_cur = get_unit(hours_current["units"], "2", "hours_stopped")
                tm1_ytd_cur = get_unit(hours_current["units"], "1", "ytd")
                tm2_ytd_cur = get_unit(hours_current["units"], "2", "ytd")

                tm1_op_ly = get_unit(hours_last["units"], "1", "hours_operating")
                tm2_op_ly = get_unit(hours_last["units"], "2", "hours_operating")
                tm1_stop_ly = get_unit(hours_last["units"], "1", "hours_stopped")
                tm2_stop_ly = get_unit(hours_last["units"], "2", "hours_stopped")
                tm1_ytd_ly = get_unit(hours_last["units"], "1", "ytd")
                tm2_ytd_ly = get_unit(hours_last["units"], "2", "ytd")
            else:
                tm1_op_cur = tm2_op_cur = tm1_stop_cur = tm2_stop_cur = tm1_ytd_cur = tm2_ytd_cur = "-"
                tm1_op_ly = tm2_op_ly = tm1_stop_ly = tm2_stop_ly = tm1_ytd_ly = tm2_ytd_ly = "-"

            # self use ratio: ((Output_year - Commercial_year) / Output_year) * 100
            def self_use_ratio(output_s: str, comm_s: str) -> str:
                outv = parse_float_loose(output_s)
                comv = parse_float_loose(comm_s)
                if outv is None or comv is None or outv <= 0:
                    print(f"[DEBUG] self_use_ratio failed: output_s='{output_s}' -> {outv}, comm_s='{comm_s}' -> {comv}", flush=True)
                    return "-"
                result = f"{((outv - comv) / outv * 100.0):.3f}"
                print(f"[DEBUG] self_use_ratio success: ({outv}-{comv})/{outv}*100 = {result}", flush=True)
                return result

            self_use_ratio_current = self_use_ratio(output_year_current, commercial_year_current)
            self_use_ratio_last = self_use_ratio(output_year_last, commercial_year_last) if last else "-"

            return f"""
### Dữ liệu vận hành Thủy điện Sông Hinh

**Nguồn:** Google Sheets (Dữ liệu thực tế)
**So sánh:** {date_current} vs. {date_last_year}

---

| Thông số | {date_current} | {date_last_year} |
|----------|----------------|------------------|
| **Mực nước thượng lưu (m)** | {water_level_current} | {water_level_last} |
| **Dung tích hữu ích (tr.m³)** | {volume_current} | {volume_last} |
| **Lưu lượng về - Qve (m³/s)** | {inflow_current} | {inflow_last} |
| **Lưu lượng chạy máy - Qcm (m³/s)** | {turbine_current} | {turbine_last} |
| **Lưu lượng xả lũ - Qxl (m³/s)** | {spillway_current} | {spillway_last} |
| **Sản lượng đầu cực ngày (kWh)** | {output_day_current} | {output_day_last} |
| **Sản lượng thương phẩm ngày (kWh)** | {commercial_day_current} | {commercial_day_last} |
| **Sản lượng đầu cực tháng (kWh)** | {output_month_current} | {output_month_last} |
| **Sản lượng thương phẩm tháng (kWh)** | {commercial_month_current} | {commercial_month_last} |
| **Sản lượng đầu cực năm (kWh)** | {output_year_current} | {output_year_last} |
| **Sản lượng thương phẩm năm (kWh)** | {commercial_year_current} | {commercial_year_last} |
| **Sản lượng kế hoạch năm (kWh)** | {plan_year_current} | {plan_year_last} |
| **Sản lượng tự dùng ngày (kWh)** | {self_use_current} | {self_use_last} |
| **Tỷ lệ tự dùng: tôn thất (năm) (%)** | {self_use_ratio_current} | {self_use_ratio_last} |
| **Phần trăm thực hiện (%)** | {percent_complete_current} | {percent_complete_last} |
| **Số giờ phát điện tổ máy 1 (h)** | {tm1_op_cur} | {tm1_op_ly} |
| **Số giờ phát điện tổ máy 2 (h)** | {tm2_op_cur} | {tm2_op_ly} |
| **Số giờ ngừng tổ máy H1 (h)** | {tm1_stop_cur} | {tm1_stop_ly} |
| **Số giờ ngừng tổ máy H2 (h)** | {tm2_stop_cur} | {tm2_stop_ly} |
| **Lũy kế thời gian chạy máy tổ máy 1 (h)** | {tm1_ytd_cur} | {tm1_ytd_ly} |
| **Lũy kế thời gian chạy máy tổ máy 2 (h)** | {tm2_ytd_cur} | {tm2_ytd_ly} |

---

**Nguồn:** Google Sheets - Thủy điện Sông Hinh
""".strip()

        else:
            # Multi-day latest N
            filtered = []
            for row in reversed(data_rows):
                if safe_cell(row, self.cols.COL_DATE):
                    filtered.append(row)
                    if len(filtered) >= int(num_days or 7):
                        break
            filtered.reverse()

            if not filtered:
                return "Không tìm thấy dữ liệu gần đây"

            # Horizontal tables
            result = f"""
### Dữ liệu vận hành Thủy điện Sông Hinh

**Nguồn:** Google Sheets (Dữ liệu thực tế)
**Số bản ghi:** {len(filtered)} ngày

---

#### Thông số vận hành hàng ngày

| Ngày | Mực nước (m) | Dung tích (tr.m³) | Qve (m³/s) | Qcm (m³/s) | Qxl (m³/s) |
|------|--------------|-------------------|------------|------------|------------|
"""
            for row in filtered:
                result += (
                    f"| {safe_cell(row, self.cols.COL_DATE)}"
                    f" | {safe_cell(row, self.cols.COL_WATER_LEVEL)}"
                    f" | {safe_cell(row, self.cols.COL_VOLUME)}"
                    f" | {safe_cell(row, self.cols.COL_INFLOW)}"
                    f" | {safe_cell(row, self.cols.COL_TURBINE)}"
                    f" | {safe_cell(row, self.cols.COL_SPILLWAY)} |\n"
                )

            result += """

---

#### Sản lượng điện (ngày)

| Ngày | Đầu cực ngày | Thương phẩm ngày | Qc ngày |
|------|--------------|--------------|--------------|
"""
            for row in filtered:
                result += (
                    f"| {safe_cell(row, self.cols.COL_DATE)}"
                    f" | {safe_cell(row, self.cols.COL_OUTPUT_DAY)}"
                    f" | {safe_cell(row, self.cols.COL_COMMERCIAL_DAY)}"
                    f" | {safe_cell(row, self.cols.COL_QC_DAY)} |\n"
                )

            result += """

---

#### Sản lượng điện (tháng)

| Ngày | Đầu cực tháng | Thương phẩm tháng | Qc tháng |
|------|---------------|--------------|--------------|
"""
            for row in filtered:
                result += (
                    f"| {safe_cell(row, self.cols.COL_DATE)}"
                    f" | {safe_cell(row, self.cols.COL_OUTPUT_MONTH)}"
                    f" | {safe_cell(row, self.cols.COL_COMMERCIAL_MONTH)}"
                    f" | {safe_cell(row, self.cols.COL_QC_MONTH_ACC)} |\n"
                )

            result += """

---
#### Sản lượng điện (năm)

| Ngày | Đầu cực năm | Thương phẩm năm | Qc năm | Tự dùng |
|------|---------------|--------------|-----------------|-----------------|
"""
            for row in filtered:
                result += (
                    f"| {safe_cell(row, self.cols.COL_DATE)}"
                    f" | {safe_cell(row, self.cols.COL_OUTPUT_YEAR)}"
                    f" | {safe_cell(row, self.cols.COL_COMMERCIAL_YEAR)}"
                    f" | {safe_cell(row, self.cols.COL_QC_YEAR_ACC)}"
                    f" | {safe_cell(row, self.cols.COL_SELF_USE)} |\n"
                )

            result += """

---

**Nguồn:** Google Sheets - Thủy điện Sông Hinh
"""
            return result.strip()
