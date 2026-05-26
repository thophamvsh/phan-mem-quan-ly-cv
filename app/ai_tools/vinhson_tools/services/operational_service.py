"""
Operational service - Get operational data for Vĩnh Sơn
"""

from datetime import datetime
from typing import Optional
from ..config.columns import (
    COL_DATE, COL_RESERVOIR, COL_WATER_LEVEL, COL_VOLUME, COL_INFLOW,
    COL_TURBINE, COL_SPILLWAY, COL_OUTPUT_DAY, COL_COMMERCIAL_DAY,COL_QC_DAY,COL_QC_MONTH_ACC ,COL_QC_YEAR_ACC,
    COL_OUTPUT_MONTH, COL_COMMERCIAL_MONTH, COL_OUTPUT_YEAR, COL_COMMERCIAL_YEAR,
    COL_PLAN_YEAR, COL_SELF_USE
)
from ..core.sheets_client import SheetsClient
from ..core.retry import retry_with_backoff
from ..utils.dates import normalize_date
from ..utils.numbers import parse_number
from .hours_service import HoursService


class OperationalService:
    """Service for retrieving operational data from Google Sheets"""

    def __init__(self):
        self.sheets_client = SheetsClient()
        self.hours_service = HoursService(self.sheets_client)

    def get_operational_data(
        self,
        date: Optional[str] = None,
        num_days: int = 7,
        reservoir: str = "Vinh Son -A",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Lấy dữ liệu vận hành từ Google Sheets cho Vĩnh Sơn.

        Kết quả gồm hai bảng:
        - Bảng 1 - Thông số thủy văn: Ngày, (Hồ nếu All), Mực nước, Dung tích, Qve, Qcm, Qxl
        - Bảng 2 - Sản lượng điện: Ngày, (Hồ nếu All), Đầu cực/Thương phẩm ngày-tháng-năm

        Args:
            date: Ngày cụ thể (format: 'DD/MM/YYYY'). Nếu None, lấy dữ liệu gần đây.
            num_days: Số ngày gần nhất cần lấy (default: 7).
            reservoir: Tên hồ ("Vinh Son -A", "Vinh Son -B", "Vinh Son -C", hoặc "All")
            start_date: Ngày bắt đầu (format: 'DD/MM/YYYY').
            end_date: Ngày kết thúc (format: 'DD/MM/YYYY').
        Returns:
            String với dữ liệu vận hành (markdown formatted)
        """
        print(f"[INFO] VINH SON TOOL: Getting operational data (date={date}, num_days={num_days}, reservoir={reservoir}, start_date={start_date}, end_date={end_date})", flush=True)

        try:
            client, worksheet, worksheet_hours = self.sheets_client.get_client()

            if not worksheet:
                return """### Lỗi kết nối Google Sheets

Không thể kết nối Google Sheets. Vui lòng kiểm tra:

1. **Service Account File**: Kiểm tra file vinhson-account-key.json có tồn tại
2. **Google Sheets API**: Đảm bảo đã enable Google Sheets API trong Google Cloud Console
3. **Spreadsheet Sharing**: Kiểm tra spreadsheet đã được share với service account email
4. **Worksheet Name**: Kiểm tra tên sheet là "VinhSon"

Xem console log để biết chi tiết lỗi."""

            # Get all data (with retry)
            def fetch_operational_data():
                return worksheet.get_all_values()

            all_data = retry_with_backoff(fetch_operational_data, max_retries=3, initial_delay=1)

            if len(all_data) < 3:
                return "Không có dữ liệu trong Google Sheets"

            headers = all_data[1]
            data_rows = all_data[2:]

            filtered_data = []
            filtered_data_last_year = []

            if start_date and end_date:
                try:
                    start_obj = datetime.strptime(start_date, '%d/%m/%Y')
                    end_obj = datetime.strptime(end_date, '%d/%m/%Y')
                    start_date_obj = start_obj.date()
                    end_date_obj = end_obj.date()
                    print(f"[INFO] Looking for date range: {start_date} to {end_date}", flush=True)
                except ValueError:
                    return f"Lỗi định dạng ngày. Vui lòng dùng format DD/MM/YYYY (ví dụ: 01/01/2026)"

                for row in data_rows:
                    if len(row) > COL_RESERVOIR:
                        reservoir_name = row[COL_RESERVOIR].strip()
                        row_date = row[COL_DATE].strip()

                        reservoir_match = (reservoir.lower() == "all" or reservoir_name == reservoir)

                        if row_date and reservoir_match:
                            row_date_normalized = normalize_date(row_date)
                            if row_date_normalized and start_date_obj <= row_date_normalized <= end_date_obj:
                                filtered_data.append(row)

                filtered_data.sort(key=lambda r: normalize_date(r[COL_DATE].strip()) if r[COL_DATE].strip() else datetime.min.date())

            elif date:
                try:
                    date_obj = datetime.strptime(date, '%d/%m/%Y')
                    date_last_year_obj = date_obj.replace(year=date_obj.year - 1)
                    date_last_year = date_last_year_obj.strftime('%d/%m/%Y')
                    print(f"[INFO] Looking for date: {date} and last year: {date_last_year}", flush=True)
                except ValueError:
                    return f"Lỗi định dạng ngày. Vui lòng dùng format DD/MM/YYYY (ví dụ: 27/04/2020)"

                target_date = date_obj.date()
                target_date_last_year = date_last_year_obj.date()

                for row in data_rows:
                    if len(row) > COL_RESERVOIR:
                        reservoir_name = row[COL_RESERVOIR].strip()
                        row_date = row[COL_DATE].strip()

                        reservoir_match = (reservoir.lower() == "all" or reservoir_name == reservoir)

                        if row_date and reservoir_match:
                            row_date_normalized = normalize_date(row_date)
                            if row_date_normalized:
                                if row_date_normalized == target_date:
                                    filtered_data.append(row)
                                elif row_date_normalized == target_date_last_year:
                                    filtered_data_last_year.append(row)

            else:
                for row in reversed(data_rows):
                    if len(row) > COL_RESERVOIR:
                        reservoir_name = row[COL_RESERVOIR].strip()
                        row_date = row[COL_DATE].strip()

                        reservoir_match = (reservoir.lower() == "all" or reservoir_name == reservoir)

                        if row_date and reservoir_match:
                            filtered_data.append(row)
                            if reservoir.lower() != "all" and len(filtered_data) >= num_days:
                                break
                            elif reservoir.lower() == "all" and len(filtered_data) >= num_days * 3:
                                break

                filtered_data.reverse()

            if not filtered_data:
                if reservoir in ["Vinh Son -B", "Vinh Son -C"]:
                    return ""

                if start_date and end_date:
                    return f"Không tìm thấy dữ liệu cho khoảng thời gian từ {start_date} đến {end_date} và hồ {reservoir}"
                elif date:
                    return f"Không tìm thấy dữ liệu cho ngày {date} và hồ {reservoir}"
                else:
                    return f"Không tìm thấy dữ liệu gần đây cho hồ {reservoir}"

            # Date range query
            if start_date and end_date and len(filtered_data) >= 1:
                results = []
                for row in filtered_data:
                    reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                    date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                    water_level = row[COL_WATER_LEVEL] if len(row) > COL_WATER_LEVEL else ""
                    volume = row[COL_VOLUME] if len(row) > COL_VOLUME else ""
                    inflow = row[COL_INFLOW] if len(row) > COL_INFLOW else ""
                    turbine = row[COL_TURBINE] if len(row) > COL_TURBINE else ""
                    spillway = row[COL_SPILLWAY] if len(row) > COL_SPILLWAY else ""
                    output_day = row[COL_OUTPUT_DAY] if len(row) > COL_OUTPUT_DAY else ""
                    commercial_day = row[COL_COMMERCIAL_DAY] if len(row) > COL_COMMERCIAL_DAY else ""
                    qc_day = row[COL_QC_DAY] if len(row) > COL_QC_DAY else ""
                    qc_month_acc = row[COL_QC_MONTH_ACC] if len(row) > COL_QC_MONTH_ACC else ""
                    qc_year_acc = row[COL_QC_YEAR_ACC] if len(row) > COL_QC_YEAR_ACC else "",

                    results.append({
                        'reservoir': reservoir_name,
                        'date': date_str,
                        'water_level': water_level,
                        'volume': volume,
                        'inflow': inflow,
                        'turbine': turbine,
                        'spillway': spillway,
                        'output_day': output_day,
                        'commercial_day': commercial_day,
                        'qc_day': qc_day,
                        'qc_month_acc': qc_month_acc,
                        'qc_year_acc': qc_year_acc,
                    })

                unique_reservoirs = set(r['reservoir'] for r in results if r['reservoir'])
                has_multiple_reservoirs = len(unique_reservoirs) > 1

                if has_multiple_reservoirs or reservoir.lower() == "all":
                    # Hai bảng: 1) Thông số thủy văn (mực nước, dung tích, Qve, Qcm, Qxl); 2) Sản lượng điện
                    output = f"""### Dữ liệu vận hành Thủy điện Vĩnh Sơn

**Nguồn:** Google Sheets (Dữ liệu thực tế)
**Khoảng thời gian:** {start_date} đến {end_date}
**Số bản ghi:** {len(filtered_data)} ngày

---

#### Bảng 1 - Thông số thủy văn

| Ngày | Hồ | Mực nước (m) | Dung tích (tr.m³) | Qve (m³/s) | Qcm (m³/s) | Qxl (m³/s) |
|------|------|---------|---------|---------|---------|---------|
"""
                    for row in filtered_data:
                        date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                        reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                        water_level = row[COL_WATER_LEVEL] if len(row) > COL_WATER_LEVEL else ""
                        volume = row[COL_VOLUME] if len(row) > COL_VOLUME else ""
                        inflow = row[COL_INFLOW] if len(row) > COL_INFLOW else ""
                        turbine = row[COL_TURBINE] if len(row) > COL_TURBINE else ""
                        spillway = row[COL_SPILLWAY] if len(row) > COL_SPILLWAY else ""

                        output += f"| {date_str} | {reservoir_name} | {water_level} | {volume} | {inflow} | {turbine} | {spillway} |\n"

                    output += """

---

#### Bảng 2 - Sản lượng điện (ngày)

| Ngày | Hồ | Đầu cực ngày | Thương phẩm ngày |Qc ngày |
|--------|------|--------------|--------------|--------------|
"""
                    for row in filtered_data:
                        date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                        reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                        output_day = row[COL_OUTPUT_DAY] if len(row) > COL_OUTPUT_DAY else ""
                        commercial_day = row[COL_COMMERCIAL_DAY] if len(row) > COL_COMMERCIAL_DAY else ""
                        qc_day = row[COL_QC_DAY] if len(row) > COL_QC_DAY else ""
                        row_date = normalize_date(date_str.strip()) if date_str else None
                        if row_date and row_date.day == 1:
                            output_month = output_day
                            commercial_month = commercial_day
                        else:
                            output_month = row[COL_OUTPUT_MONTH] if len(row) > COL_OUTPUT_MONTH else ""
                            commercial_month = row[COL_COMMERCIAL_MONTH] if len(row) > COL_COMMERCIAL_MONTH else ""
                        output_year = row[COL_OUTPUT_YEAR] if len(row) > COL_OUTPUT_YEAR else ""
                        commercial_year = row[COL_COMMERCIAL_YEAR] if len(row) > COL_COMMERCIAL_YEAR else ""
                        # self_use_year = row[COL_SELF_USE] if len(row) > COL_SELF_USE else ""

                        output += f"| {date_str} | {reservoir_name} | {output_day} | {commercial_day} | {qc_day} |\n"

                    output += """

---

#### Bảng 2 - Sản lượng điện (tháng)

| Ngày | Hồ | Đầu cực tháng | Thương phẩm tháng | Qc tháng |
|------|------|--------------|-----------------|--------------|
"""
                    for row in filtered_data:
                        date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                        reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                        row_date = normalize_date(date_str.strip()) if date_str else None
                        if row_date and row_date.day == 1:
                            output_month = row[COL_OUTPUT_DAY] if len(row) > COL_OUTPUT_DAY else ""
                            commercial_month = row[COL_COMMERCIAL_DAY] if len(row) > COL_COMMERCIAL_DAY else ""
                        else:
                            output_month = row[COL_OUTPUT_MONTH] if len(row) > COL_OUTPUT_MONTH else ""
                            commercial_month = row[COL_COMMERCIAL_MONTH] if len(row) > COL_COMMERCIAL_MONTH else ""
                            qc_month_acc = row[COL_QC_MONTH_ACC] if len(row) > COL_QC_MONTH_ACC else ""

                        output += f"| {date_str} | {reservoir_name} | {output_month} | {commercial_month} | {qc_month_acc} |\n"

                    output += """

---

#### Bảng 2 - Sản lượng điện (năm)

| Ngày | Hồ | Đầu cực năm | Thương phẩm năm | Qc năm |
|------|------|-----------------|-----------------|--------------|
"""
                    for row in filtered_data:
                        date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                        reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                        output_year = row[COL_OUTPUT_YEAR] if len(row) > COL_OUTPUT_YEAR else ""
                        commercial_year = row[COL_COMMERCIAL_YEAR] if len(row) > COL_COMMERCIAL_YEAR else ""
                        qc_year_acc = row[COL_QC_YEAR_ACC] if len(row) > COL_QC_YEAR_ACC else ""

                        output += f"| {date_str} | {reservoir_name} | {output_year} | {commercial_year} | {qc_year_acc} |\n"

                    output += """

---

**Nguồn:** Google Sheets - Thủy điện Vĩnh Sơn
"""
                    return output.strip()

                else:
                    # Hai bảng: 1) Thông số thủy văn; 2) Sản lượng điện (một hồ)
                    output = f"""### Dữ liệu vận hành Thủy điện Vĩnh Sơn - {reservoir}

**Nguồn:** Google Sheets (Dữ liệu thực tế)
**Khoảng thời gian:** {start_date} đến {end_date}
**Số bản ghi:** {len(filtered_data)} ngày

---

#### Bảng 1 - Thông số thủy văn

| Ngày | Mực nước (m) | Dung tích (tr.m³) | Qve (m³/s) | Qcm (m³/s) | Qxl (m³/s) |
|:------:|:---------:|:---------:|:---------:|:---------:|:---------:|
"""
                    for row in filtered_data:
                        date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                        water_level = row[COL_WATER_LEVEL] if len(row) > COL_WATER_LEVEL else ""
                        volume = row[COL_VOLUME] if len(row) > COL_VOLUME else ""
                        inflow = row[COL_INFLOW] if len(row) > COL_INFLOW else ""
                        turbine = row[COL_TURBINE] if len(row) > COL_TURBINE else ""
                        spillway = row[COL_SPILLWAY] if len(row) > COL_SPILLWAY else ""

                        output += f"| {date_str} | {water_level} | {volume} | {inflow} | {turbine} | {spillway} |\n"

                    output += """

---

#### Bảng 2 - Sản lượng điện (ngày)

| Ngày | Đầu cực ngày | Thương phẩm ngày | Qc ngày |
|---------|--------------|--------------|--------------|
"""
                    for row in filtered_data:
                        date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                        output_day = row[COL_OUTPUT_DAY] if len(row) > COL_OUTPUT_DAY else ""
                        commercial_day = row[COL_COMMERCIAL_DAY] if len(row) > COL_COMMERCIAL_DAY else ""
                        qc_day = row[COL_QC_DAY] if len(row) > COL_QC_DAY else ""
                        row_date = normalize_date(date_str.strip()) if date_str else None
                        if row_date and row_date.day == 1:
                            output_month = output_day
                            commercial_month = commercial_day
                        else:
                            output_month = row[COL_OUTPUT_MONTH] if len(row) > COL_OUTPUT_MONTH else ""
                            commercial_month = row[COL_COMMERCIAL_MONTH] if len(row) > COL_COMMERCIAL_MONTH else ""
                        output_year = row[COL_OUTPUT_YEAR] if len(row) > COL_OUTPUT_YEAR else ""
                        commercial_year = row[COL_COMMERCIAL_YEAR] if len(row) > COL_COMMERCIAL_YEAR else ""
                        self_use_year = row[COL_SELF_USE] if len(row) > COL_SELF_USE else ""

                        output += f"| {date_str} | {output_day} | {commercial_day} | {qc_day} |\n"

                    output += """

---

#### Bảng 2 - Sản lượng điện (tháng)

| Ngày | Đầu cực tháng | Thương phẩm tháng | Qc tháng |
|---------|--------------|-----------------|--------------|
"""
                    for row in filtered_data:
                        date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                        row_date = normalize_date(date_str.strip()) if date_str else None
                        if row_date and row_date.day == 1:
                            output_month = row[COL_OUTPUT_DAY] if len(row) > COL_OUTPUT_DAY else ""
                            commercial_month = row[COL_COMMERCIAL_DAY] if len(row) > COL_COMMERCIAL_DAY else ""
                            qc_month_acc = row[COL_QC_MONTH_ACC] if len(row) > COL_QC_MONTH_ACC else ""
                        else:
                            output_month = row[COL_OUTPUT_MONTH] if len(row) > COL_OUTPUT_MONTH else ""
                            commercial_month = row[COL_COMMERCIAL_MONTH] if len(row) > COL_COMMERCIAL_MONTH else ""
                            qc_month_acc = row[COL_QC_MONTH_ACC] if len(row) > COL_QC_MONTH_ACC else ""

                        output += f"| {date_str} | {output_month} | {commercial_month} | {qc_month_acc} |\n"

                    output += """

---

#### Bảng 2 - Sản lượng điện (năm)

| Ngày | Đầu cực năm | Thương phẩm năm | Qc năm |
|---------|-----------------|-----------------|--------------|
"""
                    for row in filtered_data:
                        date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                        output_year = row[COL_OUTPUT_YEAR] if len(row) > COL_OUTPUT_YEAR else ""
                        commercial_year = row[COL_COMMERCIAL_YEAR] if len(row) > COL_COMMERCIAL_YEAR else ""
                        qc_year_acc = row[COL_QC_YEAR_ACC] if len(row) > COL_QC_YEAR_ACC else ""

                        output += f"| {date_str} | {output_year} | {commercial_year} | {qc_year_acc} |\n"

                    output += """

---

**Nguồn:** Google Sheets - Thủy điện Vĩnh Sơn
"""
                return output.strip()

            # Specific date query
            elif date and len(filtered_data) >= 1:
                results = []
                for current_row in filtered_data:
                    reservoir_name = current_row[COL_RESERVOIR] if len(current_row) > COL_RESERVOIR else ""

                    last_year_row = None
                    for row in filtered_data_last_year:
                        if len(row) > COL_RESERVOIR and row[COL_RESERVOIR] == reservoir_name:
                            last_year_row = row
                            break

                    date_current = current_row[COL_DATE] if len(current_row) > COL_DATE else ""
                    water_level_current = current_row[COL_WATER_LEVEL] if len(current_row) > COL_WATER_LEVEL else ""
                    volume_current = current_row[COL_VOLUME] if len(current_row) > COL_VOLUME else ""
                    inflow_current = current_row[COL_INFLOW] if len(current_row) > COL_INFLOW else ""
                    turbine_current = current_row[COL_TURBINE] if len(current_row) > COL_TURBINE else ""
                    spillway_current = current_row[COL_SPILLWAY] if len(current_row) > COL_SPILLWAY else ""
                    output_day_current = current_row[COL_OUTPUT_DAY] if len(current_row) > COL_OUTPUT_DAY else ""
                    commercial_day_current = current_row[COL_COMMERCIAL_DAY] if len(current_row) > COL_COMMERCIAL_DAY else ""
                    # Ngày 1 tháng: "tháng" = lũy kế tháng = chỉ ngày đó; sheet có thể ghi nhầm tổng tháng trước
                    if target_date.day == 1:
                        output_month_current = output_day_current
                        commercial_month_current = commercial_day_current
                    else:
                        output_month_current = current_row[COL_OUTPUT_MONTH] if len(current_row) > COL_OUTPUT_MONTH else ""
                        commercial_month_current = current_row[COL_COMMERCIAL_MONTH] if len(current_row) > COL_COMMERCIAL_MONTH else ""
                    output_year_current = current_row[COL_OUTPUT_YEAR] if len(current_row) > COL_OUTPUT_YEAR else ""
                    commercial_year_current = current_row[COL_COMMERCIAL_YEAR] if len(current_row) > COL_COMMERCIAL_YEAR else ""
                    plan_year_current = current_row[COL_PLAN_YEAR] if len(current_row) > COL_PLAN_YEAR else ""
                    self_use_current = current_row[COL_SELF_USE] if len(current_row) > COL_SELF_USE else ""

                    if last_year_row:
                        def safe_cell(row, col_idx, default=""):
                            """Safely get cell value, return default if empty or out of range"""
                            if len(row) <= col_idx:
                                return default
                            val = row[col_idx]
                            if val is None or (isinstance(val, str) and val.strip() == ""):
                                return default
                            return str(val).strip() if isinstance(val, str) else str(val)

                        date_last_year = safe_cell(last_year_row, COL_DATE, "N/A")
                        water_level_last_year = safe_cell(last_year_row, COL_WATER_LEVEL, "-")
                        volume_last_year = safe_cell(last_year_row, COL_VOLUME, "-")
                        inflow_last_year = safe_cell(last_year_row, COL_INFLOW, "-")
                        turbine_last_year = safe_cell(last_year_row, COL_TURBINE, "-")
                        spillway_last_year = safe_cell(last_year_row, COL_SPILLWAY, "-")
                        output_day_last_year = safe_cell(last_year_row, COL_OUTPUT_DAY, "-")
                        commercial_day_last_year = safe_cell(last_year_row, COL_COMMERCIAL_DAY, "-")
                        output_month_last_year = safe_cell(last_year_row, COL_OUTPUT_MONTH, "-")
                        commercial_month_last_year = safe_cell(last_year_row, COL_COMMERCIAL_MONTH, "-")
                        output_year_last_year = safe_cell(last_year_row, COL_OUTPUT_YEAR, "-")
                        commercial_year_last_year = safe_cell(last_year_row, COL_COMMERCIAL_YEAR, "-")
                        plan_year_last_year = safe_cell(last_year_row, COL_PLAN_YEAR, "-")
                        self_use_last_year = safe_cell(last_year_row, COL_SELF_USE, "-")

                        print(f"[DEBUG] Last year data found: date={date_last_year}, output_year={output_year_last_year}, commercial_year={commercial_year_last_year}, plan_year={plan_year_last_year}", flush=True)
                    else:
                        date_last_year = "N/A"
                        water_level_last_year = volume_last_year = inflow_last_year = turbine_last_year = spillway_last_year = "-"
                        output_day_last_year = commercial_day_last_year = output_month_last_year = commercial_month_last_year = "-"
                        output_year_last_year = commercial_year_last_year = plan_year_last_year = self_use_last_year = "-"
                        print(f"[DEBUG] Last year row NOT found for reservoir '{reservoir_name}'", flush=True)

                    percent_complete_current = ""
                    if plan_year_current and commercial_year_current:
                        try:
                            plan_val = float(str(plan_year_current).replace(',', '').replace('.', ''))
                            commercial_val = float(str(commercial_year_current).replace(',', '').replace('.', ''))
                            if plan_val > 0:
                                percent_complete_current = f"{(commercial_val / plan_val * 100):.2f}%"
                        except (ValueError, ZeroDivisionError):
                            percent_complete_current = "-"
                    else:
                        percent_complete_current = "-"

                    # Parse last year values - check for valid non-empty values
                    plan_val_ly = None
                    commercial_val_ly = None
                    if plan_year_last_year and plan_year_last_year != "-" and plan_year_last_year.strip():
                        plan_val_ly = parse_number(plan_year_last_year)
                    if commercial_year_last_year and commercial_year_last_year != "-" and commercial_year_last_year.strip():
                        commercial_val_ly = parse_number(commercial_year_last_year)

                    percent_complete_last_year = "-"
                    if plan_val_ly is not None and commercial_val_ly is not None and plan_val_ly > 0:
                        percent_complete_last_year = f"{(commercial_val_ly / plan_val_ly * 100):.2f}%"

                    print(f"[DEBUG] Last year percent calculation: plan_year_last_year='{plan_year_last_year}', commercial_year_last_year='{commercial_year_last_year}', plan_val_ly={plan_val_ly}, commercial_val_ly={commercial_val_ly}, result={percent_complete_last_year}", flush=True)

                    hours_current = self.hours_service.get_hours_data(date_obj, reservoir_name, worksheet_hours)
                    units_current = hours_current['units']

                    hours_last_year = self.hours_service.get_hours_data(date_last_year_obj, reservoir_name, worksheet_hours)
                    units_last_year = hours_last_year['units']

                    h1_operating_current = "-"
                    h1_stopped_current = "-"
                    h1_ytd_current = "-"
                    h2_operating_current = "-"
                    h2_stopped_current = "-"
                    h2_ytd_current = "-"

                    if units_current:
                        for unit in units_current:
                            if unit['unit'] == 'H1':
                                h1_operating_current = unit['hours_operating']
                                h1_stopped_current = unit['hours_stopped']
                                h1_ytd_current = unit.get('ytd', '-')
                            elif unit['unit'] == 'H2':
                                h2_operating_current = unit['hours_operating']
                                h2_stopped_current = unit['hours_stopped']
                                h2_ytd_current = unit.get('ytd', '-')

                    h1_operating_last_year = "-"
                    h1_stopped_last_year = "-"
                    h1_ytd_last_year = "-"
                    h2_operating_last_year = "-"
                    h2_stopped_last_year = "-"
                    h2_ytd_last_year = "-"

                    if units_last_year:
                        for unit in units_last_year:
                            if unit['unit'] == 'H1':
                                h1_operating_last_year = unit['hours_operating']
                                h1_stopped_last_year = unit['hours_stopped']
                                h1_ytd_last_year = unit.get('ytd', '-')
                            elif unit['unit'] == 'H2':
                                h2_operating_last_year = unit['hours_operating']
                                h2_stopped_last_year = unit['hours_stopped']
                                h2_ytd_last_year = unit.get('ytd', '-')

                    self_use_ratio_current = "-"
                    if output_year_current and commercial_year_current:
                        try:
                            output_year_val = float(str(output_year_current).replace(',', '').replace('.', ''))
                            commercial_year_val = float(str(commercial_year_current).replace(',', '').replace('.', ''))
                            if output_year_val > 0:
                                loss = output_year_val - commercial_year_val
                                self_use_ratio_current = f"{(loss / output_year_val * 100):.3f}"
                        except (ValueError, ZeroDivisionError):
                            self_use_ratio_current = "-"

                    # Parse last year values - check for valid non-empty values
                    out_year_val_ly = None
                    com_year_val_ly = None
                    if output_year_last_year and output_year_last_year != "-" and output_year_last_year.strip():
                        out_year_val_ly = parse_number(output_year_last_year)
                    if commercial_year_last_year and commercial_year_last_year != "-" and commercial_year_last_year.strip():
                        com_year_val_ly = parse_number(commercial_year_last_year)

                    self_use_ratio_last_year = "-"
                    if out_year_val_ly is not None and com_year_val_ly is not None and out_year_val_ly > 0:
                        self_use_ratio_last_year = f"{((out_year_val_ly - com_year_val_ly) / out_year_val_ly * 100):.3f}"

                    # print(f"[DEBUG] Last year self-use ratio calculation: output_year_last_year='{output_year_last_year}', commercial_year_last_year='{commercial_year_last_year}', out_year_val_ly={out_year_val_ly}, com_year_val_ly={com_year_val_ly}, result={self_use_ratio_last_year}", flush=True)

                    result = f"""
### Dữ liệu vận hành Thủy điện Vĩnh Sơn - {reservoir_name}

**Nguồn:** Google Sheets (Dữ liệu thực tế)
**So sánh:** {date_current} vs. {date_last_year}

---

| Thông số | {date_current} | {date_last_year} |
|:----------|:---------------|:----------------|
| **Mực nước thượng lưu (m)** | {water_level_current} | {water_level_last_year} |
| **Dung tích hữu ích (tr.m³)** | {volume_current} | {volume_last_year} |
| **Lưu lượng về - Qve (m³/s)** | {inflow_current} | {inflow_last_year} |
| **Lưu lượng chạy máy - Qcm (m³/s)** | {turbine_current} | {turbine_last_year} |
| **Lưu lượng xả lũ - Qxl (m³/s)** | {spillway_current} | {spillway_last_year} |
| **Sản lượng đầu cực ngày (kWh)** | {output_day_current} | {output_day_last_year} |
| **Sản lượng thương phẩm ngày (kWh)** | {commercial_day_current} | {commercial_day_last_year} |
| **Sản lượng đầu cực tháng (kWh)** | {output_month_current} | {output_month_last_year} |
| **Sản lượng thương phẩm tháng (kWh)** | {commercial_month_current} | {commercial_month_last_year} |
| **Sản lượng đầu cực năm (kWh)** | {output_year_current} | {output_year_last_year} |
| **Sản lượng thương phẩm năm (kWh)** | {commercial_year_current} | {commercial_year_last_year} |
| **Sản lượng kế hoạch năm (kWh)** | {plan_year_current} | {plan_year_last_year} |
| **Sản lượng tự dùng ngày (kWh)** | {self_use_current} | {self_use_last_year} |
| **Tỷ lệ tự dùng: tôn thất (năm) (%)** | {self_use_ratio_current} | {self_use_ratio_last_year} |
| **Phần trăm thực hiện (%)** | {percent_complete_current} | {percent_complete_last_year} |
| **Số giờ phát điện H1 (h)** | {h1_operating_current} | {h1_operating_last_year} |
| **Số giờ phát điện H2 (h)** | {h2_operating_current} | {h2_operating_last_year} |
| **Số giờ ngừng H1 (h)** | {h1_stopped_current} | {h1_stopped_last_year} |
| **Số giờ ngừng H2 (h)** | {h2_stopped_current} | {h2_stopped_last_year} |
| **Lũy kế thời gian chạy máy H1 (h)** | {h1_ytd_current} | {h1_ytd_last_year} |
| **Lũy kế thời gian chạy máy H2 (h)** | {h2_ytd_current} | {h2_ytd_last_year} |

---

**Nguồn:** Google Sheets - Thủy điện Vĩnh Sơn

**Lưu ý:** Hiện tại chỉ có dữ liệu mực nước cho Hồ A (Vinh Son -A). Hồ B và C đã ngừng cập nhật từ năm 2021.
"""
                    results.append(result.strip())

                return "\n\n---\n\n".join(results)

            # Multiple days
            else:
                result = f"""
### Dữ liệu vận hành Thủy điện Vĩnh Sơn - {reservoir}

**Nguồn:** Google Sheets (Dữ liệu thực tế)
**Số bản ghi:** {len(filtered_data)} ngày

---

#### Bảng 1 - Thông số thủy văn

| Ngày | Hồ | Mực nước (m) | Dung tích (tr.m³) | Qve (m³/s) | Qcm (m³/s) | Qxl (m³/s) |
|------|------|--------------|-------------------|------------|------------|------------|
"""
                for row in filtered_data:
                    date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                    reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                    water_level = row[COL_WATER_LEVEL] if len(row) > COL_WATER_LEVEL else ""
                    volume = row[COL_VOLUME] if len(row) > COL_VOLUME else ""
                    inflow = row[COL_INFLOW] if len(row) > COL_INFLOW else ""
                    turbine = row[COL_TURBINE] if len(row) > COL_TURBINE else ""
                    spillway = row[COL_SPILLWAY] if len(row) > COL_SPILLWAY else ""

                    result += f"| {date_str} | {reservoir_name} | {water_level} | {volume} | {inflow} | {turbine} | {spillway} |\n"

                result += """

---

#### Bảng 2 - Sản lượng điện (ngày)

| Ngày | Hồ | Đầu cực ngày | Thương phẩm ngày | Qc ngày |
|------|------|--------------|--------------|--------------|
"""
                for row in filtered_data:
                    date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                    reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                    output_day = row[COL_OUTPUT_DAY] if len(row) > COL_OUTPUT_DAY else ""
                    commercial_day = row[COL_COMMERCIAL_DAY] if len(row) > COL_COMMERCIAL_DAY else ""
                    qc_day = row[COL_QC_DAY] if len(row) > COL_QC_DAY else ""

                    result += f"| {date_str} | {reservoir_name} | {output_day} | {commercial_day} | {qc_day} |\n"

                result += """

---

#### Bảng 2 - Sản lượng điện (tháng)

| Ngày | Hồ | Đầu cực tháng | Thương phẩm tháng | Qc tháng |
|------|------|--------------|-----------------|--------------|
"""
                for row in filtered_data:
                    date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                    reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                    row_date = normalize_date(date_str.strip()) if date_str else None
                    if row_date and row_date.day == 1:
                        output_month = row[COL_OUTPUT_DAY] if len(row) > COL_OUTPUT_DAY else ""
                        commercial_month = row[COL_COMMERCIAL_DAY] if len(row) > COL_COMMERCIAL_DAY else ""
                        qc_month_acc = row[COL_QC_MONTH_ACC] if len(row) > COL_QC_MONTH_ACC else ""
                    else:
                        output_month = row[COL_OUTPUT_MONTH] if len(row) > COL_OUTPUT_MONTH else ""
                        commercial_month = row[COL_COMMERCIAL_MONTH] if len(row) > COL_COMMERCIAL_MONTH else ""
                        qc_month_acc = row[COL_QC_MONTH_ACC] if len(row) > COL_QC_MONTH_ACC else ""

                    result += f"| {date_str} | {reservoir_name} | {output_month} | {commercial_month} | {qc_month_acc} |\n"

                result += """

---

#### Bảng 2 - Sản lượng điện (năm)

| Ngày | Hồ | Đầu cực năm | Thương phẩm năm | Qc năm |
|------|------|-----------------|-----------------|--------------|
"""
                for row in filtered_data:
                    date_str = row[COL_DATE] if len(row) > COL_DATE else ""
                    reservoir_name = row[COL_RESERVOIR] if len(row) > COL_RESERVOIR else ""
                    output_year = row[COL_OUTPUT_YEAR] if len(row) > COL_OUTPUT_YEAR else ""
                    commercial_year = row[COL_COMMERCIAL_YEAR] if len(row) > COL_COMMERCIAL_YEAR else ""
                    qc_year_acc = row[COL_QC_YEAR_ACC] if len(row) > COL_QC_YEAR_ACC else ""

                    result += f"| {date_str} | {reservoir_name} | {output_year} | {commercial_year} | {qc_year_acc} |\n"

                result += """

---

**Nguồn:** Google Sheets - Thủy điện Vĩnh Sơn
"""
                return result.strip()

        except Exception as e:
            error_msg = f"Lỗi khi lấy dữ liệu từ Google Sheets: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            return error_msg
