"""
Rainfall service - Get rainfall statistics for Sông Hinh
"""

import calendar
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from ..utils.numbers import parse_float_loose
from ..utils.dates import parse_date


# Station column mapping
STATION_COLUMN_MAP = {
    "UBND_xa_Song_Hinh": "UBND xã Sông Hinh",
    "Xa_Ea_M_doan": "Xã Ea M'doan",
    "Thon_10_Xa_Ea_M_Doal": "Thôn 10 Xã Ea M'Đoal",
    "Cu_Kroa": "Cư Króa",
    "Dap_Tran": "Đập Tràn",
    "Xa_Ea_Trang": "Xã Ea Trang",
}


def _resolve_station_columns(stations: Optional[List[str]]) -> List[str]:
    if not stations:
        return list(STATION_COLUMN_MAP.keys())
    reverse_map = {v: k for k, v in STATION_COLUMN_MAP.items()}
    return [reverse_map.get(s, s) for s in stations]


class RainfallService:
    """Service for rainfall statistics"""

    def __init__(self):
        pass

    def _append_excel_block(
        self,
        out: str,
        period_type: str,
        period_value: Optional[str],
        start_date: Optional[str],
        end_date: Optional[str],
        excel_sheets: list
    ) -> str:
        if not excel_sheets:
            return out

        import json
        filename = "bao-cao-luong-mua-song-hinh.xlsx"
        title = "Báo cáo thống kê lượng mưa Sông Hinh"
        if period_type == "year":
            y_val = period_value or datetime.now().year
            filename = f"bao-cao-luong-mua-song-hinh-nam-{y_val}.xlsx"
            title = f"Báo cáo thống kê lượng mưa năm {y_val} - Sông Hinh"
        elif period_type == "month":
            m_val = str(period_value or f"{datetime.now().month}/{datetime.now().year}").replace("/", "-")
            filename = f"bao-cao-luong-mua-song-hinh-thang-{m_val}.xlsx"
            title = f"Báo cáo thống kê lượng mưa tháng {m_val} - Sông Hinh"
        elif period_type == "week":
            w_val = str(period_value or f"{(datetime.now().day - 1) // 7 + 1}/{datetime.now().month}/{datetime.now().year}").replace("/", "-")
            filename = f"bao-cao-luong-mua-song-hinh-tuan-{w_val}.xlsx"
            title = f"Báo cáo thống kê lượng mưa tuần {w_val} - Sông Hinh"
        elif start_date and end_date:
            sd_fn = start_date.replace("/", "-")
            ed_fn = end_date.replace("/", "-")
            filename = f"bao-cao-luong-mua-song-hinh-ngay-{sd_fn}-den-{ed_fn}.xlsx"
            title = f"Báo cáo thống kê lượng mưa từ {start_date} đến {end_date} - Sông Hinh"

        excel_json = {
            "title": title,
            "fileName": filename,
            "prompt": "Bạn có muốn xuất kết quả thống kê lượng mưa ra file Excel không?",
            "sheets": excel_sheets
        }
        excel_block = f"\n\n```excel\n{json.dumps(excel_json, ensure_ascii=False, indent=2)}\n```\n"
        return out + excel_block

    def get_rainfall_statistics(
        self,
        period_type: str,
        period_value: str,
        stations: Optional[List[str]] = None,
        compare_years: int = 1
    ) -> str:
        """
        Thống kê lượng mưa theo cấu trúc thời gian (năm/tháng/tuần) cho Sông Hinh.
        - Khi period_type='year' và compare_years=1: chỉ hiển thị Bảng 1 (chi tiết tháng trong năm)
        - Khi period_type='year' và compare_years>1: hiển thị Bảng 1 + Bảng 2 (so sánh với N năm)
        """
        from thuyvan_data_client import query_rainfall_data

        print(f"[INFO] SONG HINH RAINFALL: {period_type} {period_value}, stations={stations}", flush=True)

        station_columns = _resolve_station_columns(stations)

        try:
            if period_type == "year":
                year = int(period_value)
                # Khi compare_years=1: chỉ lấy dữ liệu năm được hỏi
                # Khi compare_years>1: lấy dữ liệu năm được hỏi + N năm cùng kỳ
                if compare_years > 1:
                    n_years = min(max(compare_years, 1), 5) + 1
                    years = [year - i for i in range(n_years)]
                    oldest_year = min(years)
                    # Query từ năm oldest đến năm hiện tại để lấy dữ liệu so sánh
                    start_date = f"{oldest_year}-01-01"
                    end_date = f"{year}-12-31"
                else:
                    n_years = 1
                    years = [year]
                    start_date = f"{year}-01-01"
                    end_date = f"{year}-12-31"

                all_records = query_rainfall_data(start_date=start_date, end_date=end_date, limit=10000)

                if not all_records:
                    return "Không có dữ liệu đo mưa"

                # Monthly totals (current year) + per-station totals
                monthly_totals: Dict[int, Optional[float]] = {}
                monthly_station: Dict[int, Dict[str, float]] = {}

                for m in range(1, 13):
                    total = 0.0
                    has_data = False
                    station_totals: Dict[str, float] = {}

                    for rec in all_records:
                        ds = rec.get("Thoi_gian", "")
                        if not ds:
                            continue
                        try:
                            dt = datetime.strptime(ds, "%Y-%m-%d")
                        except Exception:
                            continue
                        if dt.year != year or dt.month != m:
                            continue

                        for col in station_columns:
                            v = parse_float_loose(rec.get(col))
                            if v is None:
                                continue
                            total += v
                            has_data = True
                            station_totals[col] = station_totals.get(col, 0.0) + v

                    monthly_totals[m] = total if has_data else None
                    monthly_station[m] = station_totals if has_data else {}

                # Bảng 2: Tổng lượng mưa các trạm hằng tháng của năm hỏi và 2 năm liền kề (cùng 1 bảng)
                monthly_total_by_year: Dict[Tuple[int, int], float] = {}
                for m in range(1, 13):
                    for yr in years:
                        total = 0.0
                        for rec in all_records:
                            ds = rec.get("Thoi_gian", "")
                            if not ds:
                                continue
                            try:
                                dt = datetime.strptime(ds, "%Y-%m-%d")
                            except Exception:
                                continue
                            if dt.year != yr or dt.month != m:
                                continue
                            for c in station_columns:
                                v = parse_float_loose(rec.get(c))
                                if v is None:
                                    continue
                                total += v
                        monthly_total_by_year[(m, yr)] = total

                # Chỉ hiển thị chi tiết theo tháng cho năm được hỏi (không có tháng năm khác)
                station_headers = [STATION_COLUMN_MAP[c] for c in station_columns]
                header_row = "| Tháng | " + " | ".join(station_headers) + " |"
                sep_row = "|-------|" + " | ".join(["---"] * len(station_columns)) + " |"
                # Build result
                result = f"""
# 🌧️ Thống kê Lượng Mưa - Sông Hinh

*Năm được hỏi:* {year}
*Số trạm:* {len(station_columns)} trạm

---

## Bảng 1 - Chi tiết các tháng năm {year} của các trạm Sông Hinh
{header_row}
{sep_row}
"""
                for m in range(1, 13):
                    row = [f"**Tháng {m}**"]
                    per = monthly_station.get(m, {})
                    for c in station_columns:
                        row.append(f"{per.get(c, 0.0):.1f}" if m in monthly_station and per else "-")
                    result += f"| {' | '.join(row)} |\n"

                # Bảng 2 - Tổng lượng mưa các trạm hằng tháng (năm được hỏi và N năm cùng kỳ)
                year_cols = " | ".join([f"{y} (mm)" for y in years])
                result += f"""
---

## Bảng 2 - So sánh Tổng lượng mưa các trạm hằng tháng (năm được hỏi và {n_years - 1} năm cùng kỳ)
| Tháng | {year_cols} |
|-------|{"|".join(["-------------"] * n_years)}|
"""
                for m in range(1, 13):
                    row_vals = [monthly_total_by_year.get((m, y), 0.0) for y in years]
                    result += f"| **Tháng {m}** | {' | '.join(f'{v:.1f}' for v in row_vals)} |\n"

                # Chart 1: Lượng mưa chi tiết các trạm năm được hỏi
                chart_data = []
                for m in range(1, 13):
                    item = {"Thang": f"Tháng {m}"}
                    per = monthly_station.get(m, {})
                    for c in station_columns:
                        item[STATION_COLUMN_MAP[c]] = round(per.get(c, 0.0), 1)
                    chart_data.append(item)

                chart_json = {
                    "type": "bar",
                    "title": f"Biểu đồ lượng mưa các trạm đo năm {year} (mm)",
                    "data": chart_data,
                    "xKey": "Thang",
                    "yKeys": [STATION_COLUMN_MAP[c] for c in station_columns],
                    "colors": ["#10b981", "#3b82f6", "#ef4444", "#f59e0b", "#06b6d4", "#a855f7"],
                    "unit": " mm"
                }
                import json
                result += f"\n\n```chart\n{json.dumps(chart_json, ensure_ascii=False, indent=2)}\n```\n"

                # Chart 2: So sánh qua các năm nếu có so sánh
                if compare_years > 1:
                    comp_chart_data = []
                    for m in range(1, 13):
                        item = {"Thang": f"Tháng {m}"}
                        for y in years:
                            item[str(y)] = round(monthly_total_by_year.get((m, y), 0.0), 1)
                        comp_chart_data.append(item)

                    comp_chart_json = {
                        "type": "line",
                        "title": f"So sánh tổng lượng mưa tháng qua các năm (mm)",
                        "data": comp_chart_data,
                        "xKey": "Thang",
                        "yKeys": [str(y) for y in years],
                        "colors": ["#10b981", "#3b82f6", "#ef4444", "#f59e0b"],
                        "unit": " mm"
                    }
                    result += f"\n\n```chart\n{json.dumps(comp_chart_json, ensure_ascii=False, indent=2)}\n```\n"

                # Sinh Excel rows cho Year
                excel_sheets = []
                excel_rows = []
                excel_rows.append([f"BÁO CÁO CHI TIẾT LƯỢNG MƯA NĂM {year} - SÔNG HINH"])
                excel_rows.append([])
                excel_rows.append(["Tháng"] + station_headers)
                for m in range(1, 13):
                    row = [f"Tháng {m}"]
                    per = monthly_station.get(m, {})
                    for c in station_columns:
                        row.append(round(per.get(c, 0.0), 1) if m in monthly_station and per else "-")
                    excel_rows.append(row)
                
                excel_rows.append([])
                excel_rows.append([f"BÁO CÁO SO SÁNH TỔNG LƯỢNG MƯA HẰNG THÁNG QUA CÁC NĂM"])
                excel_rows.append([])
                excel_rows.append(["Tháng"] + [f"{y} (mm)" for y in years])
                for m in range(1, 13):
                    row_vals = [monthly_total_by_year.get((m, y), 0.0) for y in years]
                    excel_rows.append([f"Tháng {m}"] + [round(v, 1) for v in row_vals])
                
                excel_sheets.append({
                    "name": f"Nam {year}",
                    "rows": excel_rows
                })

                result += "\n**Nguồn:** CSDL thongsothuyvan - TramDoMuaVrain"
                result = self._append_excel_block(result, "year", period_value, None, None, excel_sheets)
                return result.strip()

            elif period_type == "month":
                parts = period_value.strip().split("/")
                if len(parts) != 2:
                    return f"Lỗi: Khi period_type='month', period_value phải có dạng 'tháng/năm' (vd: '1/2026'). Nhận được: '{period_value}'."
                month_s, year_s = parts[0].strip(), parts[1].strip()
                month = int(month_s)
                year = int(year_s)
                # Năm được hỏi + 3 năm liền kề = 4 cột
                years = [year - i for i in range(4)]
                oldest_year = min(years)
                last_day = calendar.monthrange(year, month)[1]
                start_date = f"{oldest_year}-{month:02d}-01"
                end_date = f"{year}-{month:02d}-{last_day:02d}"
                all_records = query_rainfall_data(start_date=start_date, end_date=end_date, limit=10000)
                if not all_records:
                    return "Không có dữ liệu đo mưa"

                # Bảng 1: Thống kê các trạm từ ngày 1 đến last_day (tháng/năm được hỏi)
                daily_data_by_station: Dict[str, List[float]] = {col: [0.0] * 31 for col in station_columns}
                for rec in all_records:
                    ds = rec.get("Thoi_gian", "")
                    if not ds:
                        continue
                    try:
                        dt = datetime.strptime(ds, "%Y-%m-%d")
                    except Exception:
                        continue
                    if dt.year != year or dt.month != month:
                        continue
                    day_idx = dt.day - 1
                    if day_idx < 0 or day_idx > 30:
                        continue
                    for col in station_columns:
                        v = parse_float_loose(rec.get(col))
                        if v is not None:
                            daily_data_by_station[col][day_idx] += v

                station_headers = [STATION_COLUMN_MAP[c] for c in station_columns]
                header_row = "| Ngày | " + " | ".join(station_headers) + " | Tổng (mm) |"
                sep_row = "|------|" + " | ".join(["---"] * len(station_columns)) + "|-----------|"
                result = f"""
## Thống kê Lượng Mưa - Sông Hinh

**Tháng {month}/{year} – Các trạm từ ngày 1 đến 31**
**Số trạm:** {len(station_columns)} trạm

---
### Bảng 1 – Thống kê các trạm từ ngày 1 đến 31/{month}/{year}
{header_row}
{sep_row}
"""
                for day in range(1, 32):
                    row = [f"**{day}**"]
                    day_total = 0.0
                    for col in station_columns:
                        v = daily_data_by_station[col][day - 1]
                        row.append(f"{v:.1f}")
                        day_total += v
                    row.append(f"{day_total:.1f}")
                    result += f"| {' | '.join(row)} |\n"

                # Bảng 2: Tổng lượng mưa năm được hỏi và 3 năm liền kề (theo tháng đó)
                monthly_total_by_year: Dict[Tuple[int, int], float] = {}
                for y in years:
                    total = 0.0
                    for rec in all_records:
                        ds = rec.get("Thoi_gian", "")
                        if not ds:
                            continue
                        try:
                            dt = datetime.strptime(ds, "%Y-%m-%d")
                        except Exception:
                            continue
                        if dt.year != y or dt.month != month:
                            continue
                        for c in station_columns:
                            v = parse_float_loose(rec.get(c))
                            if v is not None:
                                total += v
                    monthly_total_by_year[(month, y)] = total

                year_cols = " | ".join([f"{y} (mm)" for y in years])
                result += f"""
---
### Bảng so sánh các năm cùng kỳ
| Tháng | {year_cols} |
|-------|{"|".join(["-------------"] * 4)}|
"""
                result += f"| **Tháng {month}** | {' | '.join(f'{monthly_total_by_year.get((month, y), 0.0):.1f}' for y in years)} |\n"

                # Chart 1: Daily rainfall
                daily_chart_data = []
                for day in range(1, last_day + 1):
                    item = {"Ngay": str(day)}
                    for col in station_columns:
                        item[STATION_COLUMN_MAP[col]] = round(daily_data_by_station[col][day - 1], 1)
                    daily_chart_data.append(item)

                daily_chart_json = {
                    "type": "line",
                    "title": f"Biểu đồ lượng mưa hàng ngày tháng {month}/{year} (mm)",
                    "data": daily_chart_data,
                    "xKey": "Ngay",
                    "yKeys": [STATION_COLUMN_MAP[c] for c in station_columns],
                    "colors": ["#10b981", "#3b82f6", "#ef4444", "#f59e0b", "#06b6d4", "#a855f7"],
                    "unit": " mm"
                }
                import json
                result += f"\n\n```chart\n{json.dumps(daily_chart_json, ensure_ascii=False, indent=2)}\n```\n"

                # Chart 2: 4 years comparison of monthly total
                comp_chart_data = []
                for y in reversed(years):
                    comp_chart_data.append({
                        "Nam": str(y),
                        "TongLuongMua": round(monthly_total_by_year.get((month, y), 0.0), 1)
                    })
                comp_chart_json = {
                    "type": "bar",
                    "title": f"So sánh tổng lượng mưa tháng {month} qua các năm (mm)",
                    "data": comp_chart_data,
                    "xKey": "Nam",
                    "yKeys": ["TongLuongMua"],
                    "colors": ["#3b82f6"],
                    "unit": " mm"
                }
                result += f"\n\n```chart\n{json.dumps(comp_chart_json, ensure_ascii=False, indent=2)}\n```\n"

                # Sinh Excel rows cho Month
                excel_sheets = []
                excel_rows = []
                excel_rows.append([f"BÁO CÁO LƯỢNG MƯA HÀNG NGÀY THÁNG {month}/{year} - SÔNG HINH"])
                excel_rows.append([])
                excel_rows.append(["Ngày"] + station_headers + ["Tổng (mm)"])
                for day in range(1, 32):
                    row = [str(day)]
                    day_total = 0.0
                    for col in station_columns:
                        v = daily_data_by_station[col][day - 1]
                        row.append(round(v, 1))
                        day_total += v
                    row.append(round(day_total, 1))
                    excel_rows.append(row)
                
                excel_rows.append([])
                excel_rows.append([f"BÁO CÁO SO SÁNH TỔNG LƯỢNG MƯA THÁNG {month} QUA CÁC NĂM CÙNG KỲ"])
                excel_rows.append([])
                excel_rows.append(["Tháng"] + [f"{y} (mm)" for y in years])
                excel_rows.append([f"Tháng {month}"] + [round(monthly_total_by_year.get((month, y), 0.0), 1) for y in years])
                
                excel_sheets.append({
                    "name": f"Thang {month}-{year}",
                    "rows": excel_rows
                })

                result += "\n**Nguồn:** CSDL thongsothuyvan - TramDoMuaVrain"
                result = self._append_excel_block(result, "month", period_value, None, None, excel_sheets)
                return result.strip()

            elif period_type == "week":
                parts = period_value.strip().split("/")
                if len(parts) != 3:
                    return f"Lỗi: Khi period_type='week', period_value phải có dạng 'tuần/tháng/năm' (vd: '3/1/2026'). Nhận được: '{period_value}'."
                week_s, month_s, year_s = parts[0].strip(), parts[1].strip(), parts[2].strip()
                week_num = int(week_s)
                month = int(month_s)
                year = int(year_s)

                week_ranges = {1: (1, 7), 2: (8, 14), 3: (15, 21), 4: (22, 28), 5: (29, 31)}
                sd, ed = week_ranges.get(week_num, (1, 7))

                last_day = calendar.monthrange(year, month)[1]
                start_date = f"{year-2}-{month:02d}-01"
                end_date = f"{year}-{month:02d}-{min(ed, last_day):02d}"
                all_records = query_rainfall_data(start_date=start_date, end_date=end_date, limit=10000)
                if not all_records:
                    return "Không có dữ liệu đo mưa"

                periods = [(year, ), (year - 1, ), (year - 2, )]

                result = f"""
# 🌧️ Thống kê Lượng Mưa theo Ngày - Sông Hinh

*So sánh tuần {week_num} tháng {month} qua 3 năm:* {year}, {year-1}, {year-2}
*Số trạm:** {len(station_columns)} trạm

---

| Ngày | {year} (mm) | {year-1} (mm) | {year-2} (mm) |
|------|-------------|---------------|---------------|
"""
                for d in range(sd, min(ed + 1, 32)):
                    row = [f"**{d}/{month}**"]
                    for y in [year, year - 1, year - 2]:
                        total = 0.0
                        has = False
                        for rec in all_records:
                            ds = rec.get("Thoi_gian", "")
                            if not ds:
                                continue
                            try:
                                dt = datetime.strptime(ds, "%Y-%m-%d")
                            except Exception:
                                continue
                            if dt.year == y and dt.month == month and dt.day == d:
                                for c in station_columns:
                                    v = parse_float_loose(rec.get(c))
                                    if v is None:
                                        continue
                                    total += v
                                    has = True
                                break
                        row.append(f"{total:.1f}" if has else "-")
                    result += f"| {' | '.join(row)} |\n"

                week_chart_data = []
                for d in range(sd, min(ed + 1, 32)):
                    item = {"Ngay": f"{d}/{month}"}
                    for y in [year, year - 1, year - 2]:
                        total = 0.0
                        for rec in all_records:
                            ds = rec.get("Thoi_gian", "")
                            if not ds:
                                continue
                            try:
                                dt = datetime.strptime(ds, "%Y-%m-%d")
                            except Exception:
                                continue
                            if dt.year == y and dt.month == month and dt.day == d:
                                for c in station_columns:
                                    v = parse_float_loose(rec.get(c))
                                    if v is not None:
                                        total += v
                                break
                        item[str(y)] = round(total, 1)
                    week_chart_data.append(item)

                week_chart_json = {
                    "type": "bar",
                    "title": f"So sánh lượng mưa tuần {week_num} tháng {month} qua 3 năm (mm)",
                    "data": week_chart_data,
                    "xKey": "Ngay",
                    "yKeys": [str(y) for y in [year, year - 1, year - 2]],
                    "colors": ["#10b981", "#3b82f6", "#ef4444"],
                    "unit": " mm"
                }
                import json
                result += f"\n\n```chart\n{json.dumps(week_chart_json, ensure_ascii=False, indent=2)}\n```\n"

                # Sinh Excel rows cho Week
                excel_sheets = []
                excel_rows = []
                excel_rows.append([f"BÁO CÁO SO SÁNH LƯỢNG MƯA TUẦN {week_num} THÁNG {month} QUA 3 NĂM - SÔNG HINH"])
                excel_rows.append([])
                excel_rows.append(["Ngày", f"{year} (mm)", f"{year-1} (mm)", f"{year-2} (mm)"])
                for d in range(sd, min(ed + 1, 32)):
                    row = [f"{d}/{month}"]
                    for y in [year, year - 1, year - 2]:
                        total = 0.0
                        has = False
                        for rec in all_records:
                            ds = rec.get("Thoi_gian", "")
                            if not ds:
                                continue
                            try:
                                dt = datetime.strptime(ds, "%Y-%m-%d")
                            except Exception:
                                continue
                            if dt.year == y and dt.month == month and dt.day == d:
                                for c in station_columns:
                                    v = parse_float_loose(rec.get(c))
                                    if v is not None:
                                        total += v
                                        has = True
                                break
                        row.append(round(total, 1) if has else "-")
                    excel_rows.append(row)
                
                excel_sheets.append({
                    "name": f"Tuan {week_num}-{month}-{year}",
                    "rows": excel_rows
                })

                result += "\n**Nguồn:** CSDL thongsothuyvan - TramDoMuaVrain"
                result = self._append_excel_block(result, "week", period_value, None, None, excel_sheets)
                return result.strip()

            else:
                return f"Lỗi: Loại khoảng thời gian không hợp lệ: {period_type}"

        except Exception as e:
            error_msg = f"Lỗi khi thống kê lượng mưa: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg

    def get_rainfall_range_statistics(
        self,
        start_month: int,
        start_year: int,
        end_month: int,
        end_year: int,
        stations: Optional[List[str]] = None
    ) -> str:
        """
        Thống kê lượng mưa trong khoảng thời gian (từ tháng này đến tháng khác) cho Sông Hinh
        """
        from thuyvan_data_client import query_rainfall_data

        print(f"[INFO] SONG HINH RAINFALL RANGE: {start_month}/{start_year} to {end_month}/{end_year}, stations={stations}", flush=True)

        station_columns = _resolve_station_columns(stations)

        def last_day_of_month(y: int, m: int) -> int:
            if m == 12:
                return 31
            if m in (4, 6, 9, 11):
                return 30
            if m == 2:
                leap = (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0))
                return 29 if leap else 28
            return 31

        try:
            start_date = f"{int(start_year)}-{int(start_month):02d}-01"
            end_date = f"{int(end_year)}-{int(end_month):02d}-{last_day_of_month(int(end_year), int(end_month)):02d}"

            all_records = query_rainfall_data(start_date=start_date, end_date=end_date, limit=10000)
            if not all_records:
                return f"Không có dữ liệu đo mưa từ {start_month}/{start_year} đến {end_month}/{end_year}"

            # list months in range
            months: List[Tuple[int, int]] = []
            y, m = int(start_year), int(start_month)
            ey, em = int(end_year), int(end_month)
            while (y < ey) or (y == ey and m <= em):
                months.append((m, y))
                m += 1
                if m > 12:
                    m = 1
                    y += 1

            monthly_totals: Dict[Tuple[int, int], Optional[float]] = {}
            monthly_station: Dict[Tuple[int, int], Dict[str, float]] = {}

            for (m, y) in months:
                total = 0.0
                has = False
                per_station: Dict[str, float] = {}

                for rec in all_records:
                    ds = rec.get("Thoi_gian", "")
                    if not ds:
                        continue
                    try:
                        dt = datetime.strptime(ds, "%Y-%m-%d")
                    except Exception:
                        continue
                    if dt.year != y or dt.month != m:
                        continue

                    for c in station_columns:
                        v = parse_float_loose(rec.get(c))
                        if v is None:
                            continue
                        total += v
                        has = True
                        per_station[c] = per_station.get(c, 0.0) + v

                monthly_totals[(m, y)] = total if has else None
                monthly_station[(m, y)] = per_station if has else {}

            result = f"""
### 🌧️ Thống kê Lượng Mưa theo Tháng - Sông Hinh

**Khoảng thời gian:** Từ tháng {start_month}/{start_year} đến tháng {end_month}/{end_year}
**Số trạm:** {len(station_columns)} trạm

---

#### 📊 Tổng Lượng Mưa theo Tháng

| Tháng/Năm | Tổng Lượng Mưa (mm) |
|-----------|---------------------|
"""
            for (m, y) in months:
                val = monthly_totals[(m, y)]
                result += f"| **{m}/{y}** | {val:.1f} |\n" if val is not None else f"| **{m}/{y}** | - |\n"

            station_headers = [STATION_COLUMN_MAP[c] for c in station_columns]
            header_row = "| Tháng/Năm | " + " | ".join(station_headers) + " |"
            sep_row = "|-----------|" + " | ".join(["---"] * len(station_columns)) + " |"

            result += f"""

---

#### 📋 Chi tiết Lượng Mưa theo Từng Trạm

{header_row}
{sep_row}
"""
            for (m, y) in months:
                per = monthly_station.get((m, y), {})
                row = [f"**{m}/{y}**"]
                for c in station_columns:
                    row.append(f"{per.get(c, 0.0):.1f}" if per else "-")
                result += f"| {' | '.join(row)} |\n"

            range_total = sum(v for v in monthly_totals.values() if v is not None)

            # Chart: Monthly totals in range
            range_chart_data = []
            for (m, y) in months:
                val = monthly_totals.get((m, y))
                range_chart_data.append({
                    "Thang": f"{m}/{y}",
                    "TongLuongMua": round(val, 1) if val is not None else 0.0
                })

            range_chart_json = {
                "type": "bar",
                "title": "Biểu đồ tổng lượng mưa theo tháng (mm)",
                "data": range_chart_data,
                "xKey": "Thang",
                "yKeys": ["TongLuongMua"],
                "colors": ["#3b82f6"],
                "unit": " mm"
            }
            import json
            result += f"\n\n```chart\n{json.dumps(range_chart_json, ensure_ascii=False, indent=2)}\n```\n"

            # Sinh Excel rows cho Range
            excel_sheets = []
            excel_rows = []
            excel_rows.append([f"BÁO CÁO TỔNG LƯỢNG MƯA THEO THÁNG - SÔNG HINH"])
            excel_rows.append([f"Từ tháng {start_month}/{start_year} đến tháng {end_month}/{end_year}"])
            excel_rows.append([])
            excel_rows.append(["Tháng/Năm", "Tổng Lượng Mưa (mm)"])
            for (m, y) in months:
                val = monthly_totals[(m, y)]
                excel_rows.append([f"{m}/{y}", round(val, 1) if val is not None else "-"])
            
            excel_rows.append([])
            excel_rows.append([f"BÁO CÁO CHI TIẾT LƯỢNG MƯA THEO TRẠM - SÔNG HINH"])
            excel_rows.append([])
            excel_rows.append(["Tháng/Năm"] + station_headers)
            for (m, y) in months:
                per = monthly_station.get((m, y), {})
                row = [f"{m}/{y}"]
                for c in station_columns:
                    row.append(round(per.get(c, 0.0), 1) if per else "-")
                excel_rows.append(row)
            
            excel_sheets.append({
                "name": "Khoang thoi gian",
                "rows": excel_rows
            })

            result += f"""

---

**Tổng lượng mưa trong khoảng thời gian:** {range_total:.1f} mm
**Nguồn:** CSDL thongsothuyvan - TramDoMuaVrain
"""
            result = self._append_excel_block(result, "range", None, f"01/{start_month}/{start_year}", f"01/{end_month}/{end_year}", excel_sheets)
            return result.strip()

        except Exception as e:
            error_msg = f"Lỗi khi thống kê lượng mưa: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg

    def get_rainfall_daily_statistics(
        self,
        start_date: str,
        end_date: str,
        stations: Optional[List[str]] = None
    ) -> str:
        """
        Thống kê lượng mưa chi tiết theo từng ngày trong khoảng thời gian cho Sông Hinh.
        Args:
            start_date: Ngày bắt đầu (format: "DD/MM/YYYY" hoặc "YYYY-MM-DD")
            end_date: Ngày kết thúc (format: "DD/MM/YYYY" hoặc "YYYY-MM-DD")
            stations: Danh sách trạm đo mưa (optional)
        """
        from thuyvan_data_client import query_rainfall_data

        print(f"[INFO] SONG HINH RAINFALL DAILY: {start_date} to {end_date}, stations={stations}", flush=True)

        station_columns = _resolve_station_columns(stations)

        try:
            start_dt = parse_date(start_date)
            end_dt = parse_date(end_date)

            if not start_dt or not end_dt:
                return "Lỗi: Không thể parse ngày. Sử dụng format DD/MM/YYYY hoặc YYYY-MM-DD"

            if start_dt > end_dt:
                return "Lỗi: Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc"

            start_date_str = start_dt.strftime("%Y-%m-%d")
            end_date_str = end_dt.strftime("%Y-%m-%d")

            all_records = query_rainfall_data(start_date=start_date_str, end_date=end_date_str, limit=10000)

            if not all_records:
                return f"Không có dữ liệu đo mưa từ {start_date} đến {end_date}"

            # Tổ chức dữ liệu theo ngày
            daily_data: Dict[str, Dict[str, float]] = {}  # {date: {station: value}}

            for rec in all_records:
                date_str = rec.get("Thoi_gian", "")
                if not date_str:
                    continue
                try:
                    rec_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if start_dt <= rec_date <= end_dt:
                        date_key = rec_date.strftime("%d/%m/%Y")
                        if date_key not in daily_data:
                            daily_data[date_key] = {}

                        for col in station_columns:
                            v = parse_float_loose(rec.get(col))
                            if v is not None:
                                daily_data[date_key][col] = daily_data[date_key].get(col, 0.0) + v
                except (ValueError, TypeError):
                    continue

            if not daily_data:
                return f"Không có dữ liệu đo mưa từ {start_date} đến {end_date}"

            # Sắp xếp theo ngày
            sorted_dates = sorted(daily_data.keys(), key=lambda x: datetime.strptime(x, "%d/%m/%Y"))

            # Tạo bảng chi tiết
            station_headers = [STATION_COLUMN_MAP[c] for c in station_columns]
            header_row = "| Ngày | " + " | ".join(station_headers) + " | Tổng (mm) |"
            sep_row = "|------|" + " | ".join(["---"] * len(station_columns)) + " |-----------|"

            result = f"""## 🌧️ Thống kê Lượng Mưa Chi tiết theo Ngày - Sông Hinh

**Khoảng thời gian:* Từ {start_date} đến {end_date}
**Số trạm:** {len(station_columns)} trạm

---

#### 📋 Chi tiết Lượng Mưa theo Từng Ngày

{header_row}
{sep_row}
"""

            total_range = 0.0
            for date_key in sorted_dates:
                row_data = [f"**{date_key}**"]
                day_total = 0.0

                for col in station_columns:
                    val = daily_data[date_key].get(col, 0.0)
                    # Hiển thị giá trị ngay cả khi là 0, chỉ hiển thị "-" khi không có dữ liệu (None)
                    if col in daily_data[date_key]:
                        row_data.append(f"{val:.1f}")
                    else:
                        row_data.append("-")
                    day_total += val

                row_data.append(f"**{day_total:.1f}**")
                total_range += day_total
                result += f"| {' | '.join(row_data)} |\n"

            daily_chart_data = []
            for date_key in sorted_dates:
                item = {"Ngay": date_key}
                for col in station_columns:
                    item[STATION_COLUMN_MAP[col]] = round(daily_data[date_key].get(col, 0.0), 1)
                daily_chart_data.append(item)

            daily_chart_json = {
                "type": "line",
                "title": "Biểu đồ lượng mưa hàng ngày theo trạm (mm)",
                "data": daily_chart_data,
                "xKey": "Ngay",
                "yKeys": [STATION_COLUMN_MAP[c] for c in station_columns],
                "colors": ["#10b981", "#3b82f6", "#ef4444", "#f59e0b", "#06b6d4", "#a855f7"],
                "unit": " mm"
            }
            import json
            result += f"\n\n```chart\n{json.dumps(daily_chart_json, ensure_ascii=False, indent=2)}\n```\n"

            # Sinh Excel rows cho Daily
            excel_sheets = []
            excel_rows = []
            excel_rows.append([f"BÁO CÁO LƯỢNG MƯA CHI TIẾT THEO NGÀY - SÔNG HINH"])
            excel_rows.append([f"Từ {start_date} đến {end_date}"])
            excel_rows.append([])
            excel_rows.append(["Ngày"] + station_headers + ["Tổng (mm)"])
            for date_key in sorted_dates:
                row_data = [date_key]
                day_total = 0.0
                for col in station_columns:
                    val = daily_data[date_key].get(col, 0.0)
                    if col in daily_data[date_key]:
                        row_data.append(round(val, 1))
                    else:
                        row_data.append("-")
                    day_total += val
                row_data.append(round(day_total, 1))
                excel_rows.append(row_data)
            
            excel_rows.append([])
            excel_rows.append(["Tổng lượng mưa trong khoảng thời gian", round(total_range, 1)])
            
            excel_sheets.append({
                "name": "Chi tiet ngay",
                "rows": excel_rows
            })

            result += f"""
---

**Tổng lượng mưa trong khoảng thời gian:** {total_range:.1f} mm
**Số ngày có dữ liệu:** {len(sorted_dates)} ngày
**Nguồn:** CSDL thongsothuyvan - TramDoMuaVrain
"""
            result = self._append_excel_block(result, "daily", None, start_date, end_date, excel_sheets)
            return result.strip()

        except Exception as e:
            error_msg = f"Lỗi khi thống kê lượng mưa chi tiết: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg
