"""
Comparative analysis service - Compare data between time periods for Sông Hinh
"""

from datetime import datetime
from typing import Optional, List, Dict
from ..config.columns import OP_COLS
from ..core.sheets_client import GoogleSheetsClientManager
from ..utils.dates import parse_dmy_to_date
from ..utils.numbers import safe_cell, parse_float_loose


class ComparativeAnalysisService:
    def __init__(self, manager: GoogleSheetsClientManager, cols=None):
        self.mgr = manager
        self.cols = cols or OP_COLS

    def get_comparative_analysis(self, start_date: str, end_date: str, parameters: Optional[List[str]] = None) -> str:
        print(f"[INFO] SONG HINH TOOL: Comparative analysis from {start_date} to {end_date}, parameters={parameters}", flush=True)

        if not parameters:
            parameters = ["water_level", "inflow", "turbine", "spillway"]

        start_obj = datetime.strptime(start_date, "%d/%m/%Y")
        end_obj = datetime.strptime(end_date, "%d/%m/%Y")
        start_last_year = start_obj.replace(year=start_obj.year - 1)
        end_last_year = end_obj.replace(year=end_obj.year - 1)

        ws_operational, _ = self.mgr.get_read_worksheets()
        if not ws_operational:
            return "### Lỗi kết nối Google Sheets\n\nKhông thể kết nối Google Sheets."

        all_data = self.mgr.get_all_values_cached(ws_operational, cache_key="operational_all_values")
        if len(all_data) < 3:
            return "Không có dữ liệu"

        data_rows = all_data[2:]

        cur_period: List[List[str]] = []
        ly_period: List[List[str]] = []

        for row in data_rows:
            row_date = parse_dmy_to_date(safe_cell(row, self.cols.COL_DATE))
            if not row_date:
                continue
            if start_obj.date() <= row_date <= end_obj.date():
                cur_period.append(row)
            if start_last_year.date() <= row_date <= end_last_year.date():
                ly_period.append(row)

        if not cur_period:
            return f"Không tìm thấy dữ liệu cho khoảng thời gian {start_date} đến {end_date}"
        if not ly_period:
            return (
                f"Không tìm thấy dữ liệu cùng kỳ năm trước "
                f"({start_last_year.strftime('%d/%m/%Y')} đến {end_last_year.strftime('%d/%m/%Y')})"
            )

        def extract_values(rows: List[List[str]], col_idx: int) -> List[float]:
            vals: List[float] = []
            for r in rows:
                v = parse_float_loose(safe_cell(r, col_idx))
                if v is not None:
                    vals.append(v)
            return vals

        def stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"min": 0, "max": 0, "avg": 0, "total": 0, "count": 0}
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "total": sum(values),
                "count": float(len(values)),
            }

        result = f"""
### Phân tích So sánh - Thủy điện Sông Hinh

**Khoảng thời gian:**
- **Năm nay:** {start_date} đến {end_date} ({len(cur_period)} ngày)
- **Cùng kỳ năm trước:** {start_last_year.strftime('%d/%m/%Y')} đến {end_last_year.strftime('%d/%m/%Y')} ({len(ly_period)} ngày)

---

"""
        sections: List[str] = []

        if "water_level" in parameters:
            cur = stats(extract_values(cur_period, self.cols.COL_WATER_LEVEL))
            ly = stats(extract_values(ly_period, self.cols.COL_WATER_LEVEL))
            avg_change = cur["avg"] - ly["avg"]
            avg_pct = (avg_change / ly["avg"] * 100) if ly["avg"] > 0 else 0

            sections.append(f"""
#### 📊 Mực nước thượng lưu (m)

| Chỉ số | Năm nay | Cùng kỳ năm trước | Thay đổi |
|--------|---------|-------------------|----------|
| **Thấp nhất** | {cur['min']:.2f} m | {ly['min']:.2f} m | {cur['min'] - ly['min']:+.2f} m |
| **Cao nhất** | {cur['max']:.2f} m | {ly['max']:.2f} m | {cur['max'] - ly['max']:+.2f} m |
| **Trung bình** | {cur['avg']:.2f} m | {ly['avg']:.2f} m | {avg_change:+.2f} m ({avg_pct:+.1f}%) |
| **Biên độ** | {cur['max'] - cur['min']:.2f} m | {ly['max'] - ly['min']:.2f} m | - |
""".strip())

        if "inflow" in parameters:
            cur = stats(extract_values(cur_period, self.cols.COL_INFLOW))
            ly = stats(extract_values(ly_period, self.cols.COL_INFLOW))
            avg_change = cur["avg"] - ly["avg"]
            avg_pct = (avg_change / ly["avg"] * 100) if ly["avg"] > 0 else 0
            total_change = cur["total"] - ly["total"]
            total_pct = (total_change / ly["total"] * 100) if ly["total"] > 0 else 0

            sections.append(f"""
#### 💧 Lưu lượng về - Qve (m³/s)

| Chỉ số | Năm nay | Cùng kỳ năm trước | Thay đổi |
|--------|---------|-------------------|----------|
| **Thấp nhất** | {cur['min']:.2f} | {ly['min']:.2f} | {cur['min'] - ly['min']:+.2f} |
| **Cao nhất** | {cur['max']:.2f} | {ly['max']:.2f} | {cur['max'] - ly['max']:+.2f} |
| **Trung bình** | {cur['avg']:.2f} | {ly['avg']:.2f} | {avg_change:+.2f} ({avg_pct:+.1f}%) |
| **Tổng lưu lượng** | {cur['total']:,.0f} | {ly['total']:,.0f} | {total_change:+,.0f} ({total_pct:+.1f}%) |
""".strip())

        if "turbine" in parameters:
            cur = stats(extract_values(cur_period, self.cols.COL_TURBINE))
            ly = stats(extract_values(ly_period, self.cols.COL_TURBINE))
            avg_change = cur["avg"] - ly["avg"]
            avg_pct = (avg_change / ly["avg"] * 100) if ly["avg"] > 0 else 0

            sections.append(f"""
#### ⚙️ Lưu lượng chạy máy - Qcm (m³/s)

| Chỉ số | Năm nay | Cùng kỳ năm trước | Thay đổi |
|--------|---------|-------------------|----------|
| **Thấp nhất** | {cur['min']:.2f} | {ly['min']:.2f} | {cur['min'] - ly['min']:+.2f} |
| **Cao nhất** | {cur['max']:.2f} | {ly['max']:.2f} | {cur['max'] - ly['max']:+.2f} |
| **Trung bình** | {cur['avg']:.2f} | {ly['avg']:.2f} | {avg_change:+.2f} ({avg_pct:+.1f}%) |
""".strip())

        if "spillway" in parameters:
            cur = stats(extract_values(cur_period, self.cols.COL_SPILLWAY))
            ly = stats(extract_values(ly_period, self.cols.COL_SPILLWAY))
            avg_change = cur["avg"] - ly["avg"]
            avg_pct = (avg_change / ly["avg"] * 100) if ly["avg"] > 0 else 0

            sections.append(f"""
#### 🌊 Lưu lượng xả lũ - Qxl (m³/s)

| Chỉ số | Năm nay | Cùng kỳ năm trước | Thay đổi |
|--------|---------|-------------------|----------|
| **Thấp nhất** | {cur['min']:.2f} | {ly['min']:.2f} | {cur['min'] - ly['min']:+.2f} |
| **Cao nhất** | {cur['max']:.2f} | {ly['max']:.2f} | {cur['max'] - ly['max']:+.2f} |
| **Trung bình** | {cur['avg']:.2f} | {ly['avg']:.2f} | {avg_change:+.2f} ({avg_pct:+.1f}%) |
""".strip())

        result += "\n\n---\n\n".join(sections)

        # Tự động vẽ đồ thị so sánh cho các thông số
        chart_sections = []
        for param in parameters:
            if param == "water_level":
                col_idx = self.cols.COL_WATER_LEVEL
                label = "Mực nước thượng lưu"
                unit = " m"
                chart_type = "line"
            elif param == "inflow":
                col_idx = self.cols.COL_INFLOW
                label = "Lưu lượng về Qve"
                unit = " m³/s"
                chart_type = "line"
            elif param == "turbine":
                col_idx = self.cols.COL_TURBINE
                label = "Lưu lượng chạy máy Qcm"
                unit = " m³/s"
                chart_type = "line"
            elif param == "spillway":
                col_idx = self.cols.COL_SPILLWAY
                label = "Lưu lượng xả lũ Qxl"
                unit = " m³/s"
                chart_type = "line"
            else:
                continue

            chart_data = []
            max_len = max(len(cur_period), len(ly_period))
            for idx in range(max_len):
                item = {"Ngay": f"N{idx+1}"}
                if idx < len(cur_period):
                    val_cur = parse_float_loose(safe_cell(cur_period[idx], col_idx))
                    if val_cur is not None:
                        item["NamNay"] = round(val_cur, 2)
                        d_str = safe_cell(cur_period[idx], self.cols.COL_DATE)
                        if "/" in d_str:
                            item["Ngay"] = "/".join(d_str.split("/")[:2])
                if idx < len(ly_period):
                    val_ly = parse_float_loose(safe_cell(ly_period[idx], col_idx))
                    if val_ly is not None:
                        item["NamNgoai"] = round(val_ly, 2)
                chart_data.append(item)
            
            if chart_data:
                chart_json = {
                    "type": chart_type,
                    "title": f"So sánh {label} (Năm nay vs Năm ngoái)",
                    "data": chart_data,
                    "xKey": "Ngay",
                    "yKeys": ["NamNay", "NamNgoai"],
                    "colors": ["#3b82f6", "#10b981"],
                    "unit": unit
                }
                import json
                chart_sections.append(f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n")

        if chart_sections:
            result += "\n\n---\n\n" + "\n\n".join(chart_sections)

        result += "\n\n---\n\n**Nguồn:** Google Sheets - Thủy điện Sông Hinh"
        return result.strip()
