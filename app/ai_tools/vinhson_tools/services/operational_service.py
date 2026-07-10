"""
Operational service - Get operational data for Vĩnh Sơn
"""

from datetime import datetime
from typing import Optional
from django.utils import timezone
from thongsothuyvan.models import ThongsoSanxuat, Vinhson_HoA, Vinhson_HoB, Vinhson_Hoc
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
    """Service for retrieving operational data from CSDL thongsothuyvan"""

    def __init__(self):
        self.sheets_client = SheetsClient()
        self.hours_service = HoursService(self.sheets_client)

    def get_operational_data(
        self,
        date: Optional[str] = None,
        num_days: int = 7,
        reservoir: str = "All",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """
        Lấy dữ liệu vận hành từ CSDL thongsothuyvan cho Vĩnh Sơn.

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
                return """### Lỗi kết nối CSDL thongsothuyvan

Không thể kết nối CSDL thongsothuyvan. Vui lòng kiểm tra:

1. **Kết nối CSDL**: Kiểm tra PostgreSQL/Django database đang hoạt động
2. **Dữ liệu thủy văn**: Kiểm tra bảng app/thongsothuyvan đã có dữ liệu tương ứng
3. **Migration/model**: Kiểm tra migration và model thongsothuyvan
4. **Bộ lọc nhà máy/hồ**: Kiểm tra nha_may và hồ trong dữ liệu là đúng

Xem console log để biết chi tiết lỗi."""

            # Direct DB queries bypassing sheets wrapper if using default DummyWorksheet
            if type(worksheet).__name__ != "DummyWorksheet" and type(worksheet).__name__ != "DummyWorksheetWrapper":
                all_data = retry_with_backoff(lambda: worksheet.get_all_values(), max_retries=3, initial_delay=1)
                if len(all_data) < 3:
                    return "Không có dữ liệu trong CSDL thongsothuyvan"
                data_rows = all_data[2:]
            else:
                records = ThongsoSanxuat.objects.filter(nha_may='vinhson').order_by('thoi_gian')
                record_dates = [timezone.localtime(r.thoi_gian).date() for r in records if r.thoi_gian]
                map_a = {timezone.localtime(r.created_at).date(): r for r in Vinhson_HoA.objects.filter(created_at__date__in=record_dates) if r.created_at}
                map_b = {timezone.localtime(r.created_at).date(): r for r in Vinhson_HoB.objects.filter(created_at__date__in=record_dates) if r.created_at}
                map_c = {timezone.localtime(r.created_at).date(): r for r in Vinhson_Hoc.objects.filter(created_at__date__in=record_dates) if r.created_at}

                data_rows = []
                for rec in records:
                    row = [""] * 30
                    rec_time = timezone.localtime(rec.thoi_gian)
                    rec_date = rec_time.date()
                    row[COL_DATE] = rec_time.strftime("%d/%m/%Y")
                    
                    res_name = (rec.cot_c or "").strip()
                    row[COL_RESERVOIR] = res_name
                    
                    sh = None
                    res_upper = res_name.upper()
                    if "A" in res_upper:
                        sh = map_a.get(rec_date)
                    elif "B" in res_upper:
                        sh = map_b.get(rec_date)
                    elif "C" in res_upper:
                        sh = map_c.get(rec_date)
                        
                    if sh:
                        row[COL_WATER_LEVEL] = str(sh.Mucnuoc) if sh.Mucnuoc is not None else ""
                        row[COL_VOLUME] = str(sh.dungtich) if sh.dungtich is not None else ""
                    else:
                        row[COL_WATER_LEVEL] = str(rec.cot_g) if rec.cot_g is not None else ""
                        row[COL_VOLUME] = str(rec.cot_h) if rec.cot_h is not None else ""
                        
                    inflow = None
                    if rec.cot_i is not None:
                        tot_inflow = float(rec.cot_i)
                        if "B" in res_upper:
                            inflow = float(rec.luuluong_ve_ho_b) if rec.luuluong_ve_ho_b is not None else 0.0
                        elif "C" in res_upper:
                            inflow = float(rec.luuluong_ve_ho_c) if rec.luuluong_ve_ho_c is not None else 0.0
                        else: # Lake A
                            inflow_b = float(rec.luuluong_ve_ho_b) if rec.luuluong_ve_ho_b is not None else 0.0
                            inflow_c = float(rec.luuluong_ve_ho_c) if rec.luuluong_ve_ho_c is not None else 0.0
                            inflow = round(tot_inflow - inflow_b - inflow_c, 2)
                    
                    row[COL_INFLOW] = str(inflow) if inflow is not None else ""
                    row[COL_TURBINE] = str(rec.cot_j) if rec.cot_j is not None else ""
                    row[COL_SPILLWAY] = str(rec.cot_k) if rec.cot_k is not None else ""
                    row[COL_QC_DAY] = str(rec.cot_l) if rec.cot_l is not None else ""
                    row[COL_OUTPUT_DAY] = str(rec.cot_m) if rec.cot_m is not None else ""
                    row[COL_COMMERCIAL_DAY] = str(rec.cot_n) if rec.cot_n is not None else ""
                    row[COL_QC_MONTH_ACC] = str(rec.cot_p) if rec.cot_p is not None else ""
                    row[COL_OUTPUT_MONTH] = str(rec.cot_q) if rec.cot_q is not None else ""
                    row[COL_COMMERCIAL_MONTH] = str(rec.cot_r) if rec.cot_r is not None else ""
                    row[COL_QC_YEAR_ACC] = str(rec.cot_t) if rec.cot_t is not None else ""
                    row[COL_OUTPUT_YEAR] = str(rec.cot_u) if rec.cot_u is not None else ""
                    row[COL_COMMERCIAL_YEAR] = str(rec.cot_v) if rec.cot_v is not None else ""
                    row[COL_PLAN_YEAR] = str(rec.cot_w) if rec.cot_w is not None else ""
                    row[COL_SELF_USE] = str(rec.cot_x) if rec.cot_x is not None else ""
                    
                    data_rows.append(row)

            filtered_data = []

            if start_date and end_date:
                try:
                    start_date_obj = normalize_date(start_date)
                    end_date_obj = normalize_date(end_date)
                    if not start_date_obj or not end_date_obj:
                        raise ValueError
                    start_date = start_date_obj.strftime("%d/%m/%Y")
                    end_date = end_date_obj.strftime("%d/%m/%Y")
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
                    target_date = normalize_date(date)
                    if not target_date:
                        raise ValueError
                    date = target_date.strftime("%d/%m/%Y")
                    date_obj = datetime.combine(target_date, datetime.min.time())
                    print(f"[INFO] Looking for date: {date}", flush=True)
                except ValueError:
                    return f"Lỗi định dạng ngày. Vui lòng dùng format DD/MM/YYYY (ví dụ: 27/04/2020)"

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

**Nguồn:** CSDL thongsothuyvan (Dữ liệu thực tế)
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

**Nguồn:** CSDL thongsothuyvan - Thủy điện Vĩnh Sơn
"""
                    return output.strip()

                else:
                    # Hai bảng: 1) Thông số thủy văn; 2) Sản lượng điện (một hồ)
                    output = f"""### Dữ liệu vận hành Thủy điện Vĩnh Sơn - {reservoir}

**Nguồn:** CSDL thongsothuyvan (Dữ liệu thực tế)
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

**Nguồn:** CSDL thongsothuyvan - Thủy điện Vĩnh Sơn
"""
                return output.strip()

            # Specific date query
            elif date and len(filtered_data) >= 1:
                results = []
                for current_row in filtered_data:
                    reservoir_name = current_row[COL_RESERVOIR] if len(current_row) > COL_RESERVOIR else ""

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
                    qc_day_current = current_row[COL_QC_DAY] if len(current_row) > COL_QC_DAY else ""
                    qc_month_current = (
                        qc_day_current
                        if target_date.day == 1
                        else current_row[COL_QC_MONTH_ACC] if len(current_row) > COL_QC_MONTH_ACC else ""
                    )
                    qc_year_current = current_row[COL_QC_YEAR_ACC] if len(current_row) > COL_QC_YEAR_ACC else ""

                    def pct_complete(plan_s: str, commercial_s: str) -> str:
                        plan_val = parse_number(plan_s)
                        commercial_val = parse_number(commercial_s)
                        if plan_val is None or commercial_val is None or plan_val <= 0:
                            return "-"
                        return f"{(commercial_val / plan_val * 100):.2f}%"

                    plan_year_for_report = plan_year_current or qc_year_current
                    percent_day_current = pct_complete(qc_day_current, commercial_day_current)
                    percent_month_current = pct_complete(qc_month_current, commercial_month_current)
                    percent_complete_current = pct_complete(plan_year_for_report, commercial_year_current)

                    hours_current = self.hours_service.get_hours_data(date_obj, reservoir_name, worksheet_hours)
                    units_current = hours_current.get('units', [])
                    h1_operating_current = "-"
                    h1_stopped_current = "-"
                    h1_ytd_current = "-"
                    h2_operating_current = "-"
                    h2_stopped_current = "-"
                    h2_ytd_current = "-"

                    for unit in units_current:
                        if unit.get('unit') == 'H1':
                            h1_operating_current = unit.get('hours_operating', '-')
                            h1_stopped_current = unit.get('hours_stopped', '-')
                            h1_ytd_current = unit.get('ytd', '-')
                        elif unit.get('unit') == 'H2':
                            h2_operating_current = unit.get('hours_operating', '-')
                            h2_stopped_current = unit.get('hours_stopped', '-')
                            h2_ytd_current = unit.get('ytd', '-')

                    self_use_ratio_current = "-"
                    output_year_val = parse_number(output_year_current)
                    commercial_year_val = parse_number(commercial_year_current)
                    if output_year_val is not None and commercial_year_val is not None and output_year_val > 0:
                        self_use_ratio_current = f"{((output_year_val - commercial_year_val) / output_year_val * 100):.3f}"

                    result = f"""
### Dữ liệu vận hành Thủy điện Vĩnh Sơn - {reservoir_name}

**Nguồn:** CSDL thongsothuyvan (Dữ liệu thực tế)
**Ngày báo cáo:** {date_current}

---

#### Sản lượng điện và mức đạt kế hoạch

| Chu kỳ | Sản lượng đầu cực (kWh) | Sản lượng thương phẩm (kWh) | Kế hoạch/Qc (kWh) | % đạt kế hoạch |
|--------|--------------------------|------------------------------|-------------------|----------------|
| Ngày | {output_day_current} | {commercial_day_current} | {qc_day_current} | {percent_day_current} |
| Tháng | {output_month_current} | {commercial_month_current} | {qc_month_current} | {percent_month_current} |
| Năm | {output_year_current} | {commercial_year_current} | {plan_year_for_report} | {percent_complete_current} |

---

#### Thông tin vận hành chính

| Thông số | Giá trị |
|:----------|:--------|
| **Mực nước thượng lưu (m)** | {water_level_current} |
| **Dung tích hữu ích (tr.m³)** | {volume_current} |
| **Lưu lượng về - Qve (m³/s)** | {inflow_current} |
| **Lưu lượng chạy máy - Qcm (m³/s)** | {turbine_current} |
| **Lưu lượng xả lũ - Qxl (m³/s)** | {spillway_current} |
| **Sản lượng tự dùng ngày (kWh)** | {self_use_current} |
| **Tỷ lệ tự dùng/tổn thất năm (%)** | {self_use_ratio_current} |
| **Số giờ phát điện H1 (h)** | {h1_operating_current} |
| **Số giờ phát điện H2 (h)** | {h2_operating_current} |
| **Số giờ ngừng H1 (h)** | {h1_stopped_current} |
| **Số giờ ngừng H2 (h)** | {h2_stopped_current} |
| **Lũy kế thời gian chạy máy H1 (h)** | {h1_ytd_current} |
| **Lũy kế thời gian chạy máy H2 (h)** | {h2_ytd_current} |

---

**Nguồn:** CSDL thongsothuyvan - Thủy điện Vĩnh Sơn

**Lưu ý:** Hiện tại chỉ có dữ liệu mực nước cho Hồ A (Vinh Son -A). Hồ B và C đã ngừng cập nhật từ năm 2021.
"""
                    results.append(result.strip())

                return "\n\n---\n\n".join(results)

            # Multiple days
            else:
                result = f"""
### Dữ liệu vận hành Thủy điện Vĩnh Sơn - {reservoir}

**Nguồn:** CSDL thongsothuyvan (Dữ liệu thực tế)
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

**Nguồn:** CSDL thongsothuyvan - Thủy điện Vĩnh Sơn
"""
                return result.strip()

        except Exception as e:
            error_msg = f"Lỗi khi lấy dữ liệu từ CSDL thongsothuyvan: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            return error_msg
