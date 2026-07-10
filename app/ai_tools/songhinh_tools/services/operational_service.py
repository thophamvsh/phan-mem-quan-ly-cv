"""
Operational service - Get operational data for Sông Hinh
"""

from datetime import datetime, date
from typing import Dict, List, Optional
from ..config.columns import OP_COLS
from ..core.sheets_client import GoogleSheetsClientManager
from ..utils.dates import normalize_date, parse_dmy_to_date
from ..utils.numbers import safe_cell, parse_float_loose, fmt_pct
from .hours_service import HoursService


class OperationalService:
    def __init__(self, manager: GoogleSheetsClientManager, op_cols=None, hours_service: Optional[HoursService] = None):
        self.mgr = manager
        self.cols = op_cols or OP_COLS
        self.hours = hours_service

    @staticmethod
    def connection_error_markdown() -> str:
        return """### Lỗi kết nối CSDL thongsothuyvan

Không thể kết nối CSDL thongsothuyvan. Vui lòng kiểm tra:

1. **Kết nối CSDL**: Kiểm tra PostgreSQL/Django database đang hoạt động
2. **Dữ liệu thủy văn**: Kiểm tra bảng app/thongsothuyvan đã có dữ liệu tương ứng
3. **Migration/model**: Kiểm tra migration và model thongsothuyvan
4. **Bộ lọc nhà máy**: Kiểm tra nha_may trong dữ liệu là đúng

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
            return "Không có dữ liệu trong CSDL thongsothuyvan"

        data_rows = all_data[2:]

        filtered: List[List[str]] = []
        if start_date_str and end_date_str:
            # Date range query: get all data between start_date and end_date
            try:
                start_date_obj = normalize_date(start_date_str)
                end_date_obj = normalize_date(end_date_str)
                if not start_date_obj or not end_date_obj:
                    raise ValueError
                start_date_str = start_date_obj.strftime("%d/%m/%Y")
                end_date_str = end_date_obj.strftime("%d/%m/%Y")

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

                # Build chart data
                chart_data = []
                for row in filtered:
                    try:
                        qve = parse_float_loose(safe_cell(row, self.cols.COL_INFLOW)) or 0.0
                        qcm = parse_float_loose(safe_cell(row, self.cols.COL_TURBINE)) or 0.0
                        qxl = parse_float_loose(safe_cell(row, self.cols.COL_SPILLWAY)) or 0.0
                        chart_data.append({
                            "Ngay": safe_cell(row, self.cols.COL_DATE),
                            "Qve": qve,
                            "Qcm": qcm,
                            "Qxl": qxl
                        })
                    except Exception:
                        pass

                if chart_data:
                    chart_json = {
                        "type": "line",
                        "title": "Biểu đồ lưu lượng nước (m³/s)",
                        "data": chart_data,
                        "xKey": "Ngay",
                        "yKeys": ["Qve", "Qcm", "Qxl"],
                        "colors": ["#10b981", "#3b82f6", "#ef4444"],
                        "unit": " m³/s"
                    }
                    import json
                    result += f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n"

                result += "\n---\n\n**Nguồn:** CSDL thongsothuyvan - Thủy điện Sông Hinh"
                return result.strip()

            except ValueError:
                return f"Lỗi định dạng ngày. Vui lòng dùng format DD/MM/YYYY (ví dụ: 01/01/2026)"

        elif date_str:
            target = normalize_date(date_str)
            if not target:
                return f"Lỗi định dạng ngày. Vui lòng dùng format DD/MM/YYYY (ví dụ: 01/01/2026)"
            date_str = target.strftime("%d/%m/%Y")
            date_obj = datetime.combine(target, datetime.min.time())

            filtered = self._find_rows_by_date(data_rows, target)

            if not filtered:
                return f"Không tìm thấy dữ liệu cho ngày {date_str}"

            # Single day: current-day production report.
            current = filtered[0]

            def c(idx: int, default: str = "-") -> str:
                val = safe_cell(current, idx, default)
                # Return default only if val is truly empty (after strip)
                return val if val else default

            def fmt_num(val_str):
                if not val_str or val_str == "-":
                    return "-"
                from ai_tools.songhinh_tools.utils.numbers import parse_float_loose
                val = parse_float_loose(val_str)
                if val is None:
                    return val_str
                if abs(val - round(val)) < 0.000001:
                    return f"{round(val):,}".replace(",", ".")
                res = f"{val:,.3f}".replace(",", "_").replace(".", ",").replace("_", ".")
                if "," in res:
                    res = res.rstrip("0").rstrip(",")
                return res

            date_current = c(self.cols.COL_DATE, "-")

            water_level_raw = c(self.cols.COL_WATER_LEVEL)
            volume_raw = c(self.cols.COL_VOLUME)
            inflow_raw = c(self.cols.COL_INFLOW)
            turbine_raw = c(self.cols.COL_TURBINE)
            spillway_raw = c(self.cols.COL_SPILLWAY)

            output_day_raw = c(self.cols.COL_OUTPUT_DAY)
            commercial_day_raw = c(self.cols.COL_COMMERCIAL_DAY)
            qc_day_raw = c(self.cols.COL_QC_DAY)
            # Ngày 1 tháng: "tháng" = lũy kế tháng = chỉ ngày đó; sheet có thể ghi nhầm tổng tháng trước
            if target.day == 1:
                output_month_raw = output_day_raw
                commercial_month_raw = commercial_day_raw
                qc_month_raw = qc_day_raw
            else:
                output_month_raw = c(self.cols.COL_OUTPUT_MONTH)
                commercial_month_raw = c(self.cols.COL_COMMERCIAL_MONTH)
                qc_month_raw = c(self.cols.COL_QC_MONTH_ACC)
            output_year_raw = c(self.cols.COL_OUTPUT_YEAR)
            commercial_year_raw = c(self.cols.COL_COMMERCIAL_YEAR)
            qc_year_raw = c(self.cols.COL_QC_YEAR_ACC)
            plan_year_raw = c(self.cols.COL_PLAN_YEAR)
            self_use_raw = c(self.cols.COL_SELF_USE)

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

            plan_year_for_report_raw = plan_year_raw if plan_year_raw != "-" else qc_year_raw
            percent_day_current = pct_complete(qc_day_raw, commercial_day_raw)
            percent_month_current = pct_complete(qc_month_raw, commercial_month_raw)
            percent_complete_current = pct_complete(plan_year_for_report_raw, commercial_year_raw)

            # hours data
            if self.hours:
                hours_current = self.hours.get_hours_data(date_obj, ws_hours)

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
            else:
                tm1_op_cur = tm2_op_cur = tm1_stop_cur = tm2_stop_cur = tm1_ytd_cur = tm2_ytd_cur = "-"

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

            self_use_ratio_current_raw = self_use_ratio(output_year_raw, commercial_year_raw)

            # Format all display strings
            water_level_current = fmt_num(water_level_raw)
            volume_current = fmt_num(volume_raw)
            inflow_current = fmt_num(inflow_raw)
            turbine_current = fmt_num(turbine_raw)
            spillway_current = fmt_num(spillway_raw)
            self_use_current = fmt_num(self_use_raw)

            output_day_current = fmt_num(output_day_raw)
            commercial_day_current = fmt_num(commercial_day_raw)
            qc_day_current = fmt_num(qc_day_raw)

            output_month_current = fmt_num(output_month_raw)
            commercial_month_current = fmt_num(commercial_month_raw)
            qc_month_current = fmt_num(qc_month_raw)

            output_year_current = fmt_num(output_year_raw)
            commercial_year_current = fmt_num(commercial_year_raw)
            plan_year_for_report = fmt_num(plan_year_for_report_raw)
            self_use_ratio_current = fmt_num(self_use_ratio_current_raw)

            tm1_op_cur = fmt_num(tm1_op_cur)
            tm2_op_cur = fmt_num(tm2_op_cur)
            tm1_stop_cur = fmt_num(tm1_stop_cur)
            tm2_stop_cur = fmt_num(tm2_stop_cur)
            tm1_ytd_cur = fmt_num(tm1_ytd_cur)
            tm2_ytd_cur = fmt_num(tm2_ytd_cur)

            return f"""
### Dữ liệu vận hành Thủy điện Sông Hinh

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
|----------|---------|
| **Mực nước thượng lưu (m)** | {water_level_current} |
| **Dung tích hữu ích (tr.m³)** | {volume_current} |
| **Lưu lượng về - Qve (m³/s)** | {inflow_current} |
| **Lưu lượng chạy máy - Qcm (m³/s)** | {turbine_current} |
| **Lưu lượng xả lũ - Qxl (m³/s)** | {spillway_current} |
| **Sản lượng tự dùng ngày (kWh)** | {self_use_current} |
| **Tỷ lệ tự dùng/tổn thất năm (%)** | {self_use_ratio_current} |
| **Số giờ phát điện tổ máy 1 (h)** | {tm1_op_cur} |
| **Số giờ phát điện tổ máy 2 (h)** | {tm2_op_cur} |
| **Số giờ ngừng tổ máy H1 (h)** | {tm1_stop_cur} |
| **Số giờ ngừng tổ máy H2 (h)** | {tm2_stop_cur} |
| **Lũy kế thời gian chạy máy tổ máy 1 (h)** | {tm1_ytd_cur} |
| **Lũy kế thời gian chạy máy tổ máy 2 (h)** | {tm2_ytd_cur} |

---

**Nguồn:** CSDL thongsothuyvan - Thủy điện Sông Hinh
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

**Nguồn:** CSDL thongsothuyvan (Dữ liệu thực tế)
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

            # Build chart data
            chart_data = []
            for row in filtered:
                try:
                    qve = parse_float_loose(safe_cell(row, self.cols.COL_INFLOW)) or 0.0
                    qcm = parse_float_loose(safe_cell(row, self.cols.COL_TURBINE)) or 0.0
                    qxl = parse_float_loose(safe_cell(row, self.cols.COL_SPILLWAY)) or 0.0
                    chart_data.append({
                        "Ngay": safe_cell(row, self.cols.COL_DATE),
                        "Qve": qve,
                        "Qcm": qcm,
                        "Qxl": qxl
                    })
                except Exception:
                    pass

            if chart_data:
                chart_json = {
                    "type": "line",
                    "title": "Biểu đồ lưu lượng nước (m³/s)",
                    "data": chart_data,
                    "xKey": "Ngay",
                    "yKeys": ["Qve", "Qcm", "Qxl"],
                    "colors": ["#10b981", "#3b82f6", "#ef4444"],
                    "unit": " m³/s"
                }
                import json
                result += f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n"

            result += "\n---\n\n**Nguồn:** CSDL thongsothuyvan - Thủy điện Sông Hinh"
            return result.strip()
