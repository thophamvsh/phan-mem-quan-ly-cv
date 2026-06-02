"""
Rainfall service - Get rainfall statistics for Vĩnh Sơn
"""

import calendar
import json
from datetime import datetime
from typing import Optional, List, Dict, Tuple

from ..utils.dates import parse_date
from ..utils.numbers import parse_float_loose


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

        filename = "bao-cao-luong-mua-vinh-son.xlsx"
        title = "Báo cáo thống kê lượng mưa Vĩnh Sơn"
        if period_type == "year":
            y_val = period_value or datetime.now().year
            filename = f"bao-cao-luong-mua-vinh-son-nam-{y_val}.xlsx"
            title = f"Báo cáo thống kê lượng mưa năm {y_val} - Vĩnh Sơn"
        elif period_type == "month":
            m_val = str(period_value or f"{datetime.now().month}/{datetime.now().year}").replace("/", "-")
            filename = f"bao-cao-luong-mua-vinh-son-thang-{m_val}.xlsx"
            title = f"Báo cáo thống kê lượng mưa tháng {m_val} - Vĩnh Sơn"
        elif period_type == "week":
            w_val = str(period_value or f"{(datetime.now().day - 1) // 7 + 1}/{datetime.now().month}/{datetime.now().year}").replace("/", "-")
            filename = f"bao-cao-luong-mua-vinh-son-tuan-{w_val}.xlsx"
            title = f"Báo cáo thống kê lượng mưa tuần {w_val} - Vĩnh Sơn"
        elif start_date and end_date:
            sd_fn = start_date.replace("/", "-")
            ed_fn = end_date.replace("/", "-")
            filename = f"bao-cao-luong-mua-vinh-son-ngay-{sd_fn}-den-{ed_fn}.xlsx"
            title = f"Báo cáo thống kê lượng mưa từ {start_date} đến {end_date} - Vĩnh Sơn"

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
        reservoir: str = "Vinh Son -A",
        stations: Optional[List[str]] = None,
        compare_years: int = 1
    ) -> str:
        """Thống kê lượng mưa theo cấu trúc thời gian (năm/tháng/tuần) cho Vĩnh Sơn.
        - Khi period_type='year' và compare_years=1: chỉ hiển thị Bảng 1 (chi tiết tháng trong năm)
        - Khi period_type='year' và compare_years>1: hiển thị Bảng 1 + Bảng 2 (so sánh với N năm)
        """
        from thuyvan_data_client import query_rainfall_data
        print(f"[INFO] VINH SON RAINFALL: {period_type} {period_value}, reservoir={reservoir}, stations={stations}", flush=True)
        STATION_COLUMN_MAP = {
            "Ho_A_TD_Vinh_Son": "Hồ A - TĐ Vĩnh Sơn",
            "Ho_B_TD_Vinh_Son": "Hồ B - TĐ Vĩnh Sơn",
            "Ho_C_TD_Vinh_Son": "Hồ C - TĐ Vĩnh Sơn"
        }
        if not stations:
            station_columns = list(STATION_COLUMN_MAP.keys())
        else:
            reverse_map = {v: k for k, v in STATION_COLUMN_MAP.items()}
            station_columns = [reverse_map.get(s, s) for s in stations]

        try:
            if period_type == "year":
                year = int(period_value)
                # Khi compare_years=1: chỉ lấy dữ liệu năm được hỏi
                # Khi compare_years>1: lấy dữ liệu năm được hỏi + N năm cùng kỳ
                if compare_years > 1:
                    n_years = min(max(compare_years, 1), 5) + 1
                    years = [year - i for i in range(n_years)]
                    oldest_year = min(years)
                    start_date = f"{oldest_year}-01-01"
                    end_date = f"{year}-12-31"
                else:
                    n_years = 1
                    years = [year]
                    start_date = f"{year}-01-01"
                    end_date = f"{year}-12-31"
                print(f"[INFO] Querying rainfall data from {start_date} to {end_date} for year {year}", flush=True)
                all_records = query_rainfall_data(start_date=start_date, end_date=end_date, limit=10000)
                if not all_records:
                    return f"Không có dữ liệu đo mưa cho {reservoir}"
                print(f"[INFO] Loaded {len(all_records)} rainfall records for comparison", flush=True)

                monthly_totals_current = {}
                monthly_station_data = {}
                for month in range(1, 13):
                    total_rainfall = 0.0
                    has_data = False
                    station_totals = {}
                    for record in all_records:
                        try:
                            date_str = record.get('Thoi_gian', '')
                            if not date_str:
                                continue
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            if date_obj.year == year and date_obj.month == month:
                                for col in station_columns:
                                    value = record.get(col)
                                    val = parse_float_loose(value)
                                    if val is not None:
                                        total_rainfall += val
                                        has_data = True
                                        station_totals[col] = station_totals.get(col, 0.0) + val
                        except Exception:
                            pass
                    monthly_totals_current[month] = total_rainfall if has_data else None
                    monthly_station_data[month] = station_totals if has_data else {}

                # Bảng 2: Tổng lượng mưa các trạm hằng tháng (năm hỏi và N năm cùng kỳ)
                monthly_total_by_year = {}  # (month, yr) -> total (tổng tất cả trạm)
                for m in range(1, 13):
                    for yr in years:
                        total = 0.0
                        for record in all_records:
                            try:
                                date_str = record.get('Thoi_gian', '')
                                if not date_str:
                                    continue
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                                if date_obj.year != yr or date_obj.month != m:
                                    continue
                                for col in station_columns:
                                    value = record.get(col)
                                    val = parse_float_loose(value)
                                    if val is not None:
                                        total += val
                            except Exception:
                                pass
                        monthly_total_by_year[(m, yr)] = total

                # Chỉ hiển thị chi tiết theo tháng cho năm được hỏi (không có tháng 2024/2023)
                station_headers = [STATION_COLUMN_MAP[col] for col in station_columns]
                header_row = "| Tháng | " + " | ".join(station_headers) + " |"
                separator_row = "|-------|" + " | ".join(["---"] * len(station_columns)) + " |"
                result = f"""# Thống kê Lượng Mưa - Vĩnh Sơn
*Năm được hỏi:* {year}
*Số trạm:* {len(station_columns)} trạm (Hồ A, B, C - TĐ Vĩnh Sơn)
---
## Bảng 1 - Chi tiết các tháng năm {year} của các trạm Vĩnh Sơn
{header_row}
{separator_row}"""
                for month in range(1, 13):
                    row_data = [f"**Tháng {month}**"]
                    station_data = monthly_station_data.get(month, {})
                    for col in station_columns:
                        total = station_data.get(col)
                        if total is not None:
                            row_data.append(f"{total:.1f}")
                        else:
                            row_data.append("-")
                    result += f"\n| {' | '.join(row_data)} |"

                # Chỉ hiển thị Bảng 2 khi compare_years > 1 (user yêu cầu so sánh với N năm)
                if compare_years > 1:
                    year_cols = " | ".join([f"{y} (mm)" for y in years])
                    result += f"""
---
## Bảng 2 - So sánh Tổng lượng mưa các năm cùng kỳ ({n_years - 1} năm trước)
| Tháng | {year_cols} |
|-------|{"|".join(["-------------"] * n_years)}|"""
                    for m in range(1, 13):
                        row_vals = [monthly_total_by_year.get((m, y), 0.0) for y in years]
                        result += f"\n| **Tháng {m}** | {' | '.join(f'{v:.1f}' for v in row_vals)} |"

                # Chart 1: Lượng mưa chi tiết các trạm năm được hỏi
                chart_data = []
                for m in range(1, 13):
                    item = {"Thang": f"Tháng {m}"}
                    per = monthly_station_data.get(m, {})
                    for c in station_columns:
                        item[STATION_COLUMN_MAP[c]] = round(per.get(c, 0.0), 1)
                    chart_data.append(item)

                chart_json = {
                    "type": "bar",
                    "title": f"Biểu đồ lượng mưa các trạm đo năm {year} (mm)",
                    "data": chart_data,
                    "xKey": "Thang",
                    "yKeys": [STATION_COLUMN_MAP[c] for c in station_columns],
                    "colors": ["#10b981", "#3b82f6", "#ef4444"],
                    "unit": " mm"
                }
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
                excel_rows.append([f"BÁO CÁO CHI TIẾT LƯỢNG MƯA NĂM {year} - VĨNH SƠN"])
                excel_rows.append([])
                excel_rows.append(["Tháng"] + station_headers)
                for month in range(1, 13):
                    row_data = [f"Tháng {month}"]
                    station_data = monthly_station_data.get(month, {})
                    for col in station_columns:
                        total = station_data.get(col)
                        if total is not None:
                            row_data.append(round(total, 1))
                        else:
                            row_data.append("-")
                    excel_rows.append(row_data)

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

                result += "\n*Nguồn:* CSDL thongsothuyvan - TramDoMuaVrain"
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
                    return f"Không có dữ liệu đo mưa cho tháng {month}/{year}"

                # Bảng 1: Thống kê các trạm từ ngày 1 đến last_day (tháng/năm được hỏi)
                daily_data_by_station: Dict[str, List[float]] = {col: [0.0] * 31 for col in station_columns}
                for rec in all_records:
                    try:
                        ds = rec.get("Thoi_gian", "")
                        if not ds:
                            continue
                        dt = datetime.strptime(ds, "%Y-%m-%d")
                        if dt.year != year or dt.month != month:
                            continue
                        day_idx = dt.day - 1
                        if day_idx < 0 or day_idx > 30:
                            continue
                        for col_key in station_columns:
                            v = rec.get(col_key)
                            val = parse_float_loose(v)
                            if val is not None:
                                daily_data_by_station[col_key][day_idx] += val
                    except Exception:
                        pass

                station_headers = [STATION_COLUMN_MAP[col] for col in station_columns]
                header_row = "| Ngày | " + " | ".join(station_headers) + " | Tổng (mm) |"
                sep_row = "|------|" + " | ".join(["---"] * len(station_columns)) + "|-----------|"
                result = f"""# Thống kê Lượng Mưa - Vĩnh Sơn
*Tháng {month}/{year} – Các trạm từ ngày 1 đến 31*
*Số trạm:* {len(station_columns)} trạm

---
## Bảng 1 – Thống kê các trạm từ ngày 1 đến 31/{month}/{year}
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
                        try:
                            ds = rec.get("Thoi_gian", "")
                            if not ds:
                                continue
                            dt = datetime.strptime(ds, "%Y-%m-%d")
                            if dt.year == y and dt.month == month:
                                for col_key in station_columns:
                                    v = rec.get(col_key)
                                    val = parse_float_loose(v)
                                    if val is not None:
                                        total += val
                        except Exception:
                            pass
                    monthly_total_by_year[(month, y)] = total

                year_cols = " | ".join([f"{y} (mm)" for y in years])
                result += f"""
---
## Bảng so sánh các năm cùng kỳ
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
                    "colors": ["#10b981", "#3b82f6", "#ef4444"],
                    "unit": " mm"
                }
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
                excel_rows.append([f"BÁO CÁO LƯỢNG MƯA HÀNG NGÀY THÁNG {month}/{year} - VĨNH SƠN"])
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

                result += "\n*Nguồn:* CSDL thongsothuyvan - TramDoMuaVrain"
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

                result = f"""# Thống kê Lượng Mưa - Vĩnh Sơn
*So sánh tuần {week_num} tháng {month} qua 3 năm:* {year}, {year-1}, {year-2}
*Số trạm:* {len(station_columns)} trạm
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
                                    if v is not None:
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
                result += f"\n\n```chart\n{json.dumps(week_chart_json, ensure_ascii=False, indent=2)}\n```\n"

                # Sinh Excel rows cho Week
                excel_sheets = []
                excel_rows = []
                excel_rows.append([f"BÁO CÁO SO SÁNH LƯỢNG MƯA TUẦN {week_num} THÁNG {month} QUA 3 NĂM - VĨNH SƠN"])
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

                result += "\n*Nguồn:* CSDL thongsothuyvan - TramDoMuaVrain"
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
        reservoir: str = "Vinh Son -A",
        stations: Optional[List[str]] = None
    ) -> str:
        """Thống kê lượng mưa trong khoảng thời gian (từ tháng này đến tháng khác) cho Vĩnh Sơn"""
        from thuyvan_data_client import query_rainfall_data
        print(f"[INFO] VINH SON RAINFALL RANGE: {start_month}/{start_year} to {end_month}/{end_year}, reservoir={reservoir}, stations={stations}", flush=True)
        STATION_COLUMN_MAP = {
            "Ho_A_TD_Vinh_Son": "Hồ A - TĐ Vĩnh Sơn",
            "Ho_B_TD_Vinh_Son": "Hồ B - TĐ Vĩnh Sơn",
            "Ho_C_TD_Vinh_Son": "Hồ C - TĐ Vĩnh Sơn"
        }
        if not stations:
            station_columns = list(STATION_COLUMN_MAP.keys())
        else:
            reverse_map = {v: k for k, v in STATION_COLUMN_MAP.items()}
            station_columns = [reverse_map.get(s, s) for s in stations]
        try:
            start_date = f"{start_year}-{start_month:02d}-01"
            if end_month == 12:
                last_day = 31
            elif end_month in [4, 6, 9, 11]:
                last_day = 30
            elif end_month == 2:
                last_day = 29 if (end_year % 4 == 0 and (end_year % 100 != 0 or end_year % 400 == 0)) else 28
            else:
                last_day = 31
            end_date = f"{end_year}-{end_month:02d}-{last_day}"
            print(f"[INFO] Querying rainfall data from {start_date} to {end_date}", flush=True)
            all_records = query_rainfall_data(start_date=start_date, end_date=end_date, limit=10000)
            if not all_records:
                return f"Không có dữ liệu đo mưa từ {start_month}/{start_year} đến {end_month}/{end_year} cho {reservoir}"
            print(f"[INFO] Loaded {len(all_records)} rainfall records", flush=True)
            months_in_range = []
            current_year = start_year
            current_month = start_month
            while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
                months_in_range.append((current_month, current_year))
                current_month += 1
                if current_month > 12:
                    current_month = 1
                    current_year += 1
            monthly_totals = {}
            monthly_station_data = {}
            for month, year in months_in_range:
                total_rainfall = 0.0
                has_data = False
                station_totals = {}
                for record in all_records:
                    try:
                        date_str = record.get('Thoi_gian', '')
                        if not date_str:
                            continue
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        if date_obj.year == year and date_obj.month == month:
                            for col in station_columns:
                                value = record.get(col)
                                val = parse_float_loose(value)
                                if val is not None:
                                    total_rainfall += val
                                    has_data = True
                                    station_totals[col] = station_totals.get(col, 0.0) + val
                    except Exception:
                        pass
                monthly_totals[(month, year)] = total_rainfall if has_data else None
                monthly_station_data[(month, year)] = station_totals if has_data else {}
            result = f"""## Thống kê Lượng Mưa theo Tháng - Vĩnh Sơn ({reservoir})
*Khoảng thời gian:* Từ tháng {start_month}/{start_year} đến tháng {end_month}/{end_year}
*Số trạm:* {len(station_columns)} trạm (Tất cả các hồ A, B, C)
---
## 📊 Tổng Lượng Mưa theo Tháng
| Tháng/Năm | Tổng Lượng Mưa (mm) |
|-----------|---------------------|"""
            for month, year in months_in_range:
                total = monthly_totals.get((month, year))
                if total is not None:
                    result += f"\n| **{month}/{year}** | {total:.1f} |"
                else:
                    result += f"\n| **{month}/{year}** | - |"
            station_headers = [STATION_COLUMN_MAP[col] for col in station_columns]
            header_row = "| Tháng/Năm | " + " | ".join(station_headers) + " |"
            separator_parts = ["---"] * len(station_columns)
            separator_row = "|-----------|" + " | ".join(separator_parts) + " |"
            result += f"""
---
## 📋 Chi tiết Lượng Mưa theo Từng Trạm
{header_row}
{separator_row}"""
            for month, year in months_in_range:
                row_data = [f"**{month}/{year}**"]
                station_data = monthly_station_data.get((month, year), {})
                for col in station_columns:
                    total = station_data.get(col)
                    if total is not None:
                        row_data.append(f"{total:.1f}")
                    else:
                        row_data.append("-")
                result += f"\n| {' | '.join(row_data)} |"
            range_total = sum([v for v in monthly_totals.values() if v is not None])

            # Chart: Monthly totals in range
            range_chart_data = []
            for month, year in months_in_range:
                val = monthly_totals.get((month, year))
                range_chart_data.append({
                    "Thang": f"{month}/{year}",
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
            result += f"\n\n```chart\n{json.dumps(range_chart_json, ensure_ascii=False, indent=2)}\n```\n"

            # Sinh Excel rows cho Range
            excel_sheets = []
            excel_rows = []
            excel_rows.append([f"BÁO CÁO TỔNG LƯỢNG MƯA THEO THÁNG - VĨNH SƠN"])
            excel_rows.append([f"Từ tháng {start_month}/{start_year} đến tháng {end_month}/{end_year}"])
            excel_rows.append([])
            excel_rows.append(["Tháng/Năm", "Tổng Lượng Mưa (mm)"])
            for month, year in months_in_range:
                val = monthly_totals.get((month, year))
                excel_rows.append([f"{month}/{year}", round(val, 1) if val is not None else "-"])

            excel_rows.append([])
            excel_rows.append([f"BÁO CÁO CHI TIẾT LƯỢNG MƯA THEO TRẠM - VĨNH SƠN"])
            excel_rows.append([])
            excel_rows.append(["Tháng/Năm"] + station_headers)
            for month, year in months_in_range:
                station_data = monthly_station_data.get((month, year), {})
                row = [f"{month}/{year}"]
                for col in station_columns:
                    total = station_data.get(col)
                    row.append(round(total, 1) if total is not None else "-")
                excel_rows.append(row)

            excel_sheets.append({
                "name": "Khoang thoi gian",
                "rows": excel_rows
            })

            result += f"""
---
*Tổng lượng mưa trong khoảng thời gian:* {range_total:.1f} mm
*Nguồn:* CSDL thongsothuyvan - TramDoMuaVrain"""
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
        reservoir: str = "Vinh Son -A",
        stations: Optional[List[str]] = None
    ) -> str:
        """
        Thống kê lượng mưa chi tiết theo từng ngày trong khoảng thời gian cho Vĩnh Sơn.
        Args:
            start_date: Ngày bắt đầu (format: "DD/MM/YYYY" hoặc "YYYY-MM-DD")
            end_date: Ngày kết thúc (format: "DD/MM/YYYY" hoặc "YYYY-MM-DD")
            reservoir: Hồ (Vinh Son -A, Vinh Son -B, Vinh Son -C)
            stations: Danh sách trạm đo mưa (optional)
        """
        from thuyvan_data_client import query_rainfall_data
        print(f"[INFO] VINH SON RAINFALL DAILY: {start_date} to {end_date}, reservoir={reservoir}, stations={stations}", flush=True)

        STATION_COLUMN_MAP = {
            "Ho_A_TD_Vinh_Son": "Hồ A - TĐ Vĩnh Sơn",
            "Ho_B_TD_Vinh_Son": "Hồ B - TĐ Vĩnh Sơn",
            "Ho_C_TD_Vinh_Son": "Hồ C - TĐ Vĩnh Sơn"
        }

        if not stations:
            station_columns = list(STATION_COLUMN_MAP.keys())
        else:
            reverse_map = {v: k for k, v in STATION_COLUMN_MAP.items()}
            station_columns = [reverse_map.get(s, s) for s in stations]

        try:
            start_dt = parse_date(start_date)
            end_dt = parse_date(end_date)

            if not start_dt or not end_dt:
                return "Lỗi: Không thể parse ngày. Sử dụng format DD/MM/YYYY hoặc YYYY-MM-DD"

            if start_dt > end_dt:
                return "Lỗi: Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc"

            start_date_str = start_dt.strftime("%Y-%m-%d")
            end_date_str = end_dt.strftime("%Y-%m-%d")

            print(f"[INFO] Querying rainfall data from {start_date_str} to {end_date_str}", flush=True)
            all_records = query_rainfall_data(start_date=start_date_str, end_date=end_date_str, limit=10000)

            if not all_records:
                return f"Không có dữ liệu đo mưa từ {start_date} đến {end_date} cho {reservoir}"

            print(f"[INFO] Loaded {len(all_records)} rainfall records", flush=True)

            # Tổ chức dữ liệu theo ngày
            daily_data = {}  # {date: {station: value}}

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
                            value = rec.get(col)
                            val = parse_float_loose(value)
                            if val is not None:
                                daily_data[date_key][col] = daily_data[date_key].get(col, 0.0) + val
                except (ValueError, TypeError):
                    continue

            if not daily_data:
                return f"Không có dữ liệu đo mưa từ {start_date} đến {end_date} cho {reservoir}"

            # Sắp xếp theo ngày
            sorted_dates = sorted(daily_data.keys(), key=lambda x: datetime.strptime(x, "%d/%m/%Y"))

            # Tạo bảng chi tiết
            station_headers = [STATION_COLUMN_MAP[col] for col in station_columns]
            header_row = "| Ngày | " + " | ".join(station_headers) + " | Tổng (mm) |"
            sep_row = "|------|" + " | ".join(["---"] * len(station_columns)) + " |-----------|"

            result = f"""# 🌧️ Thống kê Lượng Mưa Chi tiết theo Ngày - Vĩnh Sơn ({reservoir})

*Khoảng thời gian:* Từ {start_date} đến {end_date}
*Số trạm:* {len(station_columns)} trạm (Tất cả các hồ A, B, C)

---

## 📋 Chi tiết Lượng Mưa theo Từng Ngày

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

            # Chart: Daily rainfall line chart
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
                "colors": ["#10b981", "#3b82f6", "#ef4444"],
                "unit": " mm"
            }
            result += f"\n\n```chart\n{json.dumps(daily_chart_json, ensure_ascii=False, indent=2)}\n```\n"

            # Sinh Excel rows cho Daily
            excel_sheets = []
            excel_rows = []
            excel_rows.append([f"BÁO CÁO LƯỢNG MƯA CHI TIẾT THEO NGÀY - VĨNH SƠN"])
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
