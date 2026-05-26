"""
Rainfall service - Get rainfall statistics for Vĩnh Sơn
"""

import calendar
from datetime import datetime
from typing import Optional, List, Dict

from ..utils.dates import parse_date


class RainfallService:
    """Service for rainfall statistics"""

    def __init__(self):
        pass

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
                    years = [year]
                    start_date = f"{year}-01-01"
                    end_date = f"{year}-12-31"
                print(f"[INFO] Querying rainfall data from {start_date} to {end_date} for year {year}", flush=True)
                all_records = query_rainfall_data(start_date=start_date, end_date=end_date, limit=10000)
                if year == 2025:
                    year_2025_records = query_rainfall_data(start_date="2025-01-01", end_date="2025-12-31", limit=10000)
                    if len(year_2025_records) > len([r for r in all_records if r.get('Thoi_gian', '').startswith('2025-')]):
                        other_years = [r for r in all_records if not r.get('Thoi_gian', '').startswith('2025-')]
                        all_records = other_years + year_2025_records
                if not all_records:
                    return f"Không có dữ liệu đo mưa cho {reservoir}"
                print(f"[INFO] Loaded {len(all_records)} rainfall records for comparison", flush=True)
                monthly_totals_current = {}
                monthly_station_data = {}
                for month in range(1, 13):
                    total_rainfall = 0
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
                                    if value is not None:
                                        try:
                                            val = float(value)
                                            if val > 0 or val == 0:
                                                total_rainfall += val
                                                has_data = True
                                                if col not in station_totals:
                                                    station_totals[col] = 0
                                                station_totals[col] += val
                                        except (ValueError, TypeError):
                                            pass
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
                                    if value is not None:
                                        try:
                                            val = float(value)
                                            if val >= 0:
                                                total += val
                                        except (ValueError, TypeError):
                                            pass
                            except Exception:
                                pass
                        monthly_total_by_year[(m, yr)] = total

                # Chỉ hiển thị chi tiết theo tháng cho năm được hỏi (không có tháng 2024/2023)
                station_headers = [STATION_COLUMN_MAP[col] for col in station_columns]
                header_row = "| Tháng | " + " | ".join(station_headers) + " |"
                separator_row = "|-------|" + " | ".join(["---"] * len(station_columns)) + " |"
                result = f"""# Thống kê Lượng Mưa - Vĩnh Sơn
* Năm được hỏi:* {year}
* Số trạm:* {len(station_columns)} trạm (Hồ A, B, C - TĐ Vĩnh Sơn)
---
# Bảng 1 - Chi tiết các tháng năm {year} của 3 trạm Vĩnh Sơn
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
# Bảng 2 - So sánh Tổng lượng mưa các năm cùng kỳ ({n_years - 1} năm trước)
| Tháng | {year_cols} |
|-------|{"|".join(["-------------"] * n_years)}|"""
                    for m in range(1, 13):
                        row_vals = [monthly_total_by_year.get((m, y), 0.0) for y in years]
                        result += f"\n| **Tháng {m}** | {' | '.join(f'{v:.1f}' for v in row_vals)} |"

                result += "\n*Nguồn:* Supabase - Bảng Do_Mua_VSH"
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
                            if v is not None:
                                try:
                                    daily_data_by_station[col_key][day_idx] += float(v)
                                except (ValueError, TypeError):
                                    pass
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
                monthly_total_by_year: Dict[tuple, float] = {}
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
                                    if v is not None:
                                        try:
                                            total += float(v)
                                        except (ValueError, TypeError):
                                            pass
                        except Exception:
                            pass
                    monthly_total_by_year[(month, y)] = total

                year_cols = " | ".join([f"{y} (mm)" for y in years])
                result += f"""
---
## Bảng 2 – Tổng lượng mưa năm {year} và 3 năm liền kề
| Tháng | {year_cols} |
|-------|{"|".join(["-------------"] * 4)}|
"""
                result += f"| **Tháng {month}** | {' | '.join(f'{monthly_total_by_year.get((month, y), 0.0):.1f}' for y in years)} |\n"
                result += "\n*Nguồn:* Supabase - Bảng Do_Mua_VSH"
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
                total_rainfall = 0
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
                                if value is not None:
                                    try:
                                        val = float(value)
                                        if val > 0 or val == 0:
                                            total_rainfall += val
                                            has_data = True
                                            if col not in station_totals:
                                                station_totals[col] = 0
                                            station_totals[col] += val
                                    except (ValueError, TypeError):
                                        pass
                    except Exception:
                        pass
                monthly_totals[(month, year)] = total_rainfall if has_data else None
                monthly_station_data[(month, year)] = station_totals if has_data else {}
            result = f"""## Thống kê Lượng Mưa theo Tháng - Vĩnh Sơn ({reservoir})
* Khoảng thời gian:* Từ tháng {start_month}/{start_year} đến tháng {end_month}/{end_year}
**Số trạm:* {len(station_columns)} trạm (Tất cả các hồ A, B, C)
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
            result += f"""
---
*Tổng lượng mưa trong khoảng thời gian:* {range_total:.1f} mm
*Nguồn:* Supabase - Bảng Do_Mua_VSH"""
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
                            if value is not None:
                                try:
                                    val = float(value)
                                    if val >= 0:
                                        daily_data[date_key][col] = daily_data[date_key].get(col, 0.0) + val
                                except (ValueError, TypeError):
                                    pass
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

            result += f"""
---

**Tổng lượng mưa trong khoảng thời gian:** {total_range:.1f} mm
**Số ngày có dữ liệu:** {len(sorted_dates)} ngày
**Nguồn:** Supabase - Bảng Do_Mua_VSH
"""
            return result.strip()

        except Exception as e:
            error_msg = f"Lỗi khi thống kê lượng mưa chi tiết: {str(e)}"
            print(f"[ERROR] {error_msg}", flush=True)
            import traceback
            traceback.print_exc()
            return error_msg
