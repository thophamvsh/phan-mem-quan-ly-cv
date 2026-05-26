"""
Qve analysis service - Phân tích nguyên nhân Qve (so sánh năm hiện tại và cùng kỳ) cho Vĩnh Sơn.

Nguồn:
- Qve + MNH: Google Sheets stats_export (sheet "Thống kê")
- Sản lượng: Google Sheets vận hành
- Lượng mưa: Supabase Do_Mua_VSH
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Callable, Any, Tuple

from ..config.settings import GS_CONFIG
from ..config.columns import (
    COL_DATE,
    COL_RESERVOIR,
    COL_OUTPUT_DAY,
    COL_COMMERCIAL_DAY,
    COL_OUTPUT_MONTH,
    COL_COMMERCIAL_MONTH,
    COL_OUTPUT_YEAR,
    COL_COMMERCIAL_YEAR,
)
from ..core.stats_export_client import get_stats_export_client
from ..core.sheets_client import SheetsClient
from ..core.retry import retry_with_backoff
from ..utils.dates import normalize_date
from ..utils.numbers import parse_number, parse_number_for_mnh, parse_number_for_qve


# Supabase rainfall columns (3 trạm)
RAIN_COLS_VS = ["Ho_A_TD_Vinh_Son", "Ho_B_TD_Vinh_Son", "Ho_C_TD_Vinh_Son"]

# Sheet Thống kê (0-based)
COL_DATE_STATS = 0
COL_WATER_A, COL_WATER_B, COL_WATER_C = 1, 2, 3
COL_QVE_A, COL_QVE_B, COL_QVE_C = 4, 5, 6

RES_MAP = {"Vinh Son -A": 0, "Vinh Son -B": 1, "Vinh Son -C": 2}

_TR = 1e6  # triệu kWh


# -------------------------
# Parsing helpers
# -------------------------

def _parse_num(s: Any) -> Optional[float]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    return parse_number(t)


def _parse_num_mnh(s: Any) -> Optional[float]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    return parse_number_for_mnh(t)


def _parse_num_qve(s: Any) -> Optional[float]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    return parse_number_for_qve(t)


def _cell(row: list, i: int) -> str:
    return row[i] if i < len(row) else ""


def _date_from_operational_row(row: list) -> Optional[date]:
    for col in (0, COL_DATE):
        if col >= len(row):
            continue
        raw = str(_cell(row, col)).strip()
        if not raw:
            continue
        d = normalize_date(raw)
        if d:
            return d
    return None


# -------------------------
# Stats helpers
# -------------------------

@dataclass(frozen=True)
class Stats:
    min: float = 0.0
    max: float = 0.0
    avg: float = 0.0
    sum: float = 0.0
    n: int = 0


def calc_stats(rows: List[list], col: int, parser: Callable[[Any], Optional[float]]) -> Stats:
    vals: List[float] = []
    for r in rows:
        v = parser(r[col] if col < len(r) else None)
        if v is not None:
            vals.append(v)
    if not vals:
        return Stats()
    s = float(sum(vals))
    return Stats(min=min(vals), max=max(vals), avg=s / len(vals), sum=s, n=len(vals))


def safe_pct(delta: float, base: float) -> float:
    return (delta / base * 100.0) if base else 0.0


def is_full_year_range(start_obj: datetime, end_obj: datetime) -> bool:
    """Check if date range is a full year."""
    return (
        start_obj.day == 1 and start_obj.month == 1
        and end_obj.day == 31 and end_obj.month == 12
        and start_obj.year == end_obj.year
    )


def is_full_month_range(start_obj: datetime, end_obj: datetime) -> bool:
    """Check if date range is a full month (day 1 to last day of month)."""
    if start_obj.day != 1:
        return False
    if end_obj.month == 12:
        last_day = 31
    else:
        last_day = (end_obj.replace(day=1, month=end_obj.month + 1) - timedelta(days=1)).day
    return end_obj.day == last_day and start_obj.month == end_obj.month and start_obj.year == end_obj.year


def shift_year(dt: datetime, years: int) -> datetime:
    """Chuyển ngày sang năm khác, xử lý các ngày không hợp lệ (ví dụ: 29/02 -> 28/02 khi sang năm không nhuận)."""
    try:
        return dt.replace(year=dt.year + years)
    except ValueError:
        # Xử lý ngày 29/02 khi sang năm không nhuận
        import calendar
        max_day = calendar.monthrange(dt.year + years, dt.month)[1]
        return dt.replace(year=dt.year + years, day=max_day)


# -------------------------
# Data loading helpers
# -------------------------

def pick_stats_worksheet(spreadsheet):
    worksheets = spreadsheet.worksheets()
    for ws in worksheets:
        if "Thống kê" in ws.title or "Thống kê tháng" in ws.title:
            return ws
    return worksheets[0] if worksheets else None


def find_data_start_row(all_data: List[List[str]]) -> int:
    for i, row in enumerate(all_data):
        if not row:
            continue
        first = str(row[0]).strip()
        if not first:
            continue
        d = normalize_date(first)
        if d:
            return i
    if len(all_data) > 7:
        return 7
    return 1 if len(all_data) > 1 else 0


def filter_rows_by_period(
    rows: List[List[str]],
    start_d: date,
    end_d: date,
    date_col: int = COL_DATE_STATS,
) -> List[List[str]]:
    out: List[List[str]] = []
    for r in rows:
        if date_col >= len(r):
            continue
        ds = str(r[date_col]).strip()
        if not ds:
            continue
        d = normalize_date(ds)
        if not d:
            continue
        if start_d <= d <= end_d:
            out.append(r)
    return out


# -------------------------
# Main service
# -------------------------

class QveAnalysisService:
    """Phân tích Qve: so sánh năm nay vs cùng kỳ, kết hợp Qve + mưa + MNH + sản lượng."""

    def get_qve_analysis(
        self,
        start_date: str,
        end_date: str,
        reservoir: str = "All",
        parameters: Optional[List[str]] = None,
        analysis_focus: str = "qve",
    ) -> str:
        if not parameters:
            parameters = ["qve", "water_level", "rainfall", "commercial_output"]

        # Validate và parse ngày
        try:
            start_obj = datetime.strptime(start_date, "%d/%m/%Y")
            end_obj = datetime.strptime(end_date, "%d/%m/%Y")
        except ValueError as e:
            return f"Lỗi định dạng ngày: {e}. Vui lòng dùng DD/MM/YYYY."

        # Validate ngày hợp lệ (ví dụ: 31/02 không hợp lệ)
        import calendar
        _, last_day_start = calendar.monthrange(start_obj.year, start_obj.month)
        _, last_day_end = calendar.monthrange(end_obj.year, end_obj.month)
        if start_obj.day > last_day_start:
            return f"Lỗi: Ngày {start_obj.day}/{start_obj.month}/{start_obj.year} không hợp lệ (tháng {start_obj.month} chỉ có {last_day_start} ngày)."
        if end_obj.day > last_day_end:
            return f"Lỗi: Ngày {end_obj.day}/{end_obj.month}/{end_obj.year} không hợp lệ (tháng {end_obj.month} chỉ có {last_day_end} ngày)."

        # Validate start_date <= end_date
        if start_obj > end_obj:
            return "Lỗi: Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc."

        start_ly = shift_year(start_obj, -1)
        end_ly = shift_year(end_obj, -1)

        start_ly2 = shift_year(start_obj, -2)
        end_ly2 = shift_year(end_obj, -2)
        start_ly3 = shift_year(start_obj, -3)
        end_ly3 = shift_year(end_obj, -3)

        start_d, end_d = start_obj.date(), end_obj.date()
        start_ly_d, end_ly_d = start_ly.date(), end_ly.date()
        start_ly2_d, end_ly2_d = start_ly2.date(), end_ly2.date()
        start_ly3_d, end_ly3_d = start_ly3.date(), end_ly3.date()

        use_all = reservoir in (None, "All", "")
        res_idx = RES_MAP.get(reservoir, 0)

        # -------------------------
        # 1) Load stats sheet (Qve/MNH)
        # -------------------------
        _, spreadsheet = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
        if not spreadsheet:
            return (
                "### Lỗi kết nối Google Sheets\n\n"
                "Không thể kết nối Google Sheets thống kê (Phân tích Qve dùng Sheet ID đã cấu hình)."
            )

        stats_ws = pick_stats_worksheet(spreadsheet)
        if not stats_ws:
            return "### Lỗi\n\nKhông tìm thấy worksheet thống kê trong Google Sheets."

        all_data = retry_with_backoff(stats_ws.get_all_values, max_retries=3, initial_delay=1)
        if not all_data or len(all_data) < 2:
            return "Không có dữ liệu trong Google Sheets thống kê."

        data_start = find_data_start_row(all_data)
        data_rows = all_data[data_start:] if data_start < len(all_data) else []
        if not data_rows:
            return "Không có dữ liệu sau dòng tiêu đề trong Google Sheets thống kê."

        cur_rows = filter_rows_by_period(data_rows, start_d, end_d, COL_DATE_STATS)
        ly_rows = filter_rows_by_period(data_rows, start_ly_d, end_ly_d, COL_DATE_STATS)
        ly2_rows = filter_rows_by_period(data_rows, start_ly2_d, end_ly2_d, COL_DATE_STATS)
        ly3_rows = filter_rows_by_period(data_rows, start_ly3_d, end_ly3_d, COL_DATE_STATS)

        if not cur_rows:
            return f"Không tìm thấy dữ liệu vận hành cho khoảng {start_date} đến {end_date}."
        if not ly_rows:
            return (
                "Không tìm thấy dữ liệu cùng kỳ năm trước "
                f"({start_ly.strftime('%d/%m/%Y')} đến {end_ly.strftime('%d/%m/%Y')})."
            )

        # Stats theo hồ (MNH/Qve)
        reservoirs_data: List[Dict[str, Any]] = []
        if use_all:
            specs = [
                ("Hồ A", COL_WATER_A, COL_QVE_A),
                ("Hồ B", COL_WATER_B, COL_QVE_B),
                ("Hồ C", COL_WATER_C, COL_QVE_C),
            ]
        else:
            specs = [(reservoir, COL_WATER_A + res_idx, COL_QVE_A + res_idx)]

        for name, w_col, q_col in specs:
            reservoirs_data.append(
                {
                    "name": name,
                    "wl_cur": calc_stats(cur_rows, w_col, _parse_num_mnh),
                    "wl_ly": calc_stats(ly_rows, w_col, _parse_num_mnh),
                    "wl_ly2": calc_stats(ly2_rows, w_col, _parse_num_mnh),
                    "wl_ly3": calc_stats(ly3_rows, w_col, _parse_num_mnh),
                    "qve_cur": calc_stats(cur_rows, q_col, _parse_num_qve),
                    "qve_ly": calc_stats(ly_rows, q_col, _parse_num_qve),
                    "qve_ly2": calc_stats(ly2_rows, q_col, _parse_num_qve),
                    "qve_ly3": calc_stats(ly3_rows, q_col, _parse_num_qve),
                }
            )

        # Tổng hợp TB
        qve_cur_avg = sum(r["qve_cur"].avg for r in reservoirs_data) / len(reservoirs_data)
        qve_ly_avg = sum(r["qve_ly"].avg for r in reservoirs_data) / len(reservoirs_data)
        wl_cur_avg = sum(r["wl_cur"].avg for r in reservoirs_data) / len(reservoirs_data)
        wl_ly_avg = sum(r["wl_ly"].avg for r in reservoirs_data) / len(reservoirs_data)

        def collect_qve_vals(rows: List[list], q_cols: List[int]) -> List[float]:
            out: List[float] = []
            for r in rows:
                for c in q_cols:
                    v = _parse_num_qve(r[c] if c < len(r) else None)
                    if v is not None:
                        out.append(v)
            return out

        q_cols = [COL_QVE_A, COL_QVE_B, COL_QVE_C] if use_all else [COL_QVE_A + res_idx]
        qve_cur_vals_all = collect_qve_vals(cur_rows, q_cols)
        qve_ly_vals_all = collect_qve_vals(ly_rows, q_cols)

        qve_cur_min = min(qve_cur_vals_all) if qve_cur_vals_all else 0.0
        qve_cur_max = max(qve_cur_vals_all) if qve_cur_vals_all else 0.0
        qve_ly_min = min(qve_ly_vals_all) if qve_ly_vals_all else 0.0
        qve_ly_max = max(qve_ly_vals_all) if qve_ly_vals_all else 0.0

        # -------------------------
        # 2) Rainfall from Supabase
        # -------------------------
        rain_cur = rain_ly = rain_ly2 = rain_ly3 = 0.0
        has_rain = False

        if "rainfall" in parameters:
            from thuyvan_data_client import query_rainfall_data

            start_rain_query = f"{start_ly3_d}"
            end_rain_query = f"{end_d}"
            rain_records = query_rainfall_data(start_date=start_rain_query, end_date=end_rain_query, limit=10000) or []
            for rec in rain_records:
                ts = rec.get("Thoi_gian") or ""
                if not ts:
                    continue
                try:
                    t = datetime.strptime(ts[:10], "%Y-%m-%d").date()
                except Exception:
                    continue

                row_sum = 0.0
                for c in RAIN_COLS_VS:
                    v = rec.get(c)
                    if v is None:
                        continue
                    try:
                        row_sum += float(v)
                    except (TypeError, ValueError):
                        pass

                if start_d <= t <= end_d:
                    rain_cur += row_sum
                if start_ly_d <= t <= end_ly_d:
                    rain_ly += row_sum
                if start_ly2_d <= t <= end_ly2_d:
                    rain_ly2 += row_sum
                if start_ly3_d <= t <= end_ly3_d:
                    rain_ly3 += row_sum

            has_rain = (rain_cur > 0 or rain_ly > 0 or rain_ly2 > 0 or rain_ly3 > 0)

        # -------------------------
        # 3) Operational output (optional)
        # -------------------------
        # Sản lượng tháng (cột Q, R)
        out_cur_sum = out_ly_sum = out_ly2_sum = out_ly3_sum = 0.0
        out_cur_output = out_ly_output = out_ly2_output = out_ly3_output = 0.0
        # Lũy kế từ đầu năm (cột U, V)
        out_cur_sum_year = out_ly_sum_year = out_ly2_sum_year = out_ly3_sum_year = 0.0
        out_cur_output_year = out_ly_output_year = out_ly2_output_year = out_ly3_output_year = 0.0
        operational_latest_date_str = ""

        if "commercial_output" in parameters:
            _, op_ws, _ = SheetsClient().get_client()
            if op_ws:
                op_data = retry_with_backoff(op_ws.get_all_values, max_retries=3, initial_delay=1) or []
                if len(op_data) >= 2:
                    op_rows = op_data[2:] if len(op_data) >= 3 else op_data[1:]

                    cur_period: List[Tuple[date, str, list]] = []
                    ly_period: List[Tuple[date, str, list]] = []
                    ly2_period: List[Tuple[date, str, list]] = []
                    ly3_period: List[Tuple[date, str, list]] = []

                    all_dates: List[date] = []
                    for row in op_rows:
                        rd = _date_from_operational_row(row)
                        if not rd:
                            continue
                        all_dates.append(rd)

                        res_name = str(_cell(row, COL_RESERVOIR)).strip()
                        if not use_all and res_name != reservoir:
                            continue

                        if start_d <= rd <= end_d:
                            cur_period.append((rd, res_name, row))
                        if start_ly_d <= rd <= end_ly_d:
                            ly_period.append((rd, res_name, row))
                        if start_ly2_d <= rd <= end_ly2_d:
                            ly2_period.append((rd, res_name, row))
                        if start_ly3_d <= rd <= end_ly3_d:
                            ly3_period.append((rd, res_name, row))

                    if all_dates:
                        operational_latest_date_str = max(all_dates).strftime("%d/%m/%Y")

                    full_year = is_full_year_range(start_obj, end_obj)
                    full_month = is_full_month_range(start_obj, end_obj)

                    def add_day_values(row: list, acc_output: float, acc_commercial: float):
                        vo = _parse_num(_cell(row, COL_OUTPUT_DAY))
                        vc = _parse_num(_cell(row, COL_COMMERCIAL_DAY))
                        if vo is not None:
                            acc_output += vo
                        if vc is not None:
                            acc_commercial += vc
                        return acc_output, acc_commercial

                    def add_year_values(row: list, acc_output: float, acc_commercial: float):
                        vo = _parse_num(_cell(row, COL_OUTPUT_YEAR))
                        vc = _parse_num(_cell(row, COL_COMMERCIAL_YEAR))
                        if vo is not None:
                            acc_output += vo
                        if vc is not None:
                            acc_commercial += vc
                        return acc_output, acc_commercial

                    def add_month_values(row: list, acc_output: float, acc_commercial: float):
                        """Lấy sản lượng tháng từ cột Q (COL_OUTPUT_MONTH) và R (COL_COMMERCIAL_MONTH)."""
                        vo = _parse_num(_cell(row, COL_OUTPUT_MONTH))
                        vc = _parse_num(_cell(row, COL_COMMERCIAL_MONTH))
                        if vo is not None:
                            acc_output += vo
                        if vc is not None:
                            acc_commercial += vc
                        return acc_output, acc_commercial

                    if full_year:
                        # Full year: lấy cột U/V (năm) tại ngày cuối năm
                        if cur_period:
                            max_d = max(d for d, _, _ in cur_period)
                            for d, _, row in cur_period:
                                if d == max_d:
                                    out_cur_output, out_cur_sum = add_year_values(row, out_cur_output, out_cur_sum)
                        if ly_period:
                            max_d = max(d for d, _, _ in ly_period)
                            for d, _, row in ly_period:
                                if d == max_d:
                                    out_ly_output, out_ly_sum = add_year_values(row, out_ly_output, out_ly_sum)
                        if ly2_period:
                            max_d = max(d for d, _, _ in ly2_period)
                            for d, _, row in ly2_period:
                                if d == max_d:
                                    out_ly2_output, out_ly2_sum = add_year_values(row, out_ly2_output, out_ly2_sum)
                        if ly3_period:
                            max_d = max(d for d, _, _ in ly3_period)
                            for d, _, row in ly3_period:
                                if d == max_d:
                                    out_ly3_output, out_ly3_sum = add_year_values(row, out_ly3_output, out_ly3_sum)
                    elif full_month:
                        # Full month: lấy cột Q/R (tháng) VÀ cột U/V (lũy kế từ đầu năm) tại ngày cuối tháng
                        if cur_period:
                            max_d = max(d for d, _, _ in cur_period)
                            for d, _, row in cur_period:
                                if d == max_d:
                                    out_cur_output, out_cur_sum = add_month_values(row, out_cur_output, out_cur_sum)
                                    out_cur_output_year, out_cur_sum_year = add_year_values(row, out_cur_output_year, out_cur_sum_year)
                        if ly_period:
                            max_d = max(d for d, _, _ in ly_period)
                            for d, _, row in ly_period:
                                if d == max_d:
                                    out_ly_output, out_ly_sum = add_month_values(row, out_ly_output, out_ly_sum)
                                    out_ly_output_year, out_ly_sum_year = add_year_values(row, out_ly_output_year, out_ly_sum_year)
                        if ly2_period:
                            max_d = max(d for d, _, _ in ly2_period)
                            for d, _, row in ly2_period:
                                if d == max_d:
                                    out_ly2_output, out_ly2_sum = add_month_values(row, out_ly2_output, out_ly2_sum)
                                    out_ly2_output_year, out_ly2_sum_year = add_year_values(row, out_ly2_output_year, out_ly2_sum_year)
                        if ly3_period:
                            max_d = max(d for d, _, _ in ly3_period)
                            for d, _, row in ly3_period:
                                if d == max_d:
                                    out_ly3_output, out_ly3_sum = add_month_values(row, out_ly3_output, out_ly3_sum)
                                    out_ly3_output_year, out_ly3_sum_year = add_year_values(row, out_ly3_output_year, out_ly3_sum_year)
                    else:
                        # Cộng dồn theo ngày
                        for _, _, row in cur_period:
                            out_cur_output, out_cur_sum = add_day_values(row, out_cur_output, out_cur_sum)
                        for _, _, row in ly_period:
                            out_ly_output, out_ly_sum = add_day_values(row, out_ly_output, out_ly_sum)
                        for _, _, row in ly2_period:
                            out_ly2_output, out_ly2_sum = add_day_values(row, out_ly2_output, out_ly2_sum)
                        for _, _, row in ly3_period:
                            out_ly3_output, out_ly3_sum = add_day_values(row, out_ly3_output, out_ly3_sum)

        # -------------------------
        # Build report
        # -------------------------
        n_cur, n_ly = len(cur_rows), len(ly_rows)
        res_label = "cả 3 hồ A, B, C" if use_all else reservoir
        cur_year = start_obj.year
        ly_year = start_obj.year - 1

        buf: List[str] = []
        buf.append(f"### Phân tích Qve / MNH / Sản lượng - Thủy điện Vĩnh Sơn ({res_label})")
        buf.append("")
        buf.append("**Khoảng thời gian:**")
        buf.append(f"- **{cur_year}:** {start_date} đến {end_date} ({n_cur} bản ghi)")
        buf.append(f"- **{ly_year}:** {start_ly.strftime('%d/%m/%Y')} đến {end_ly.strftime('%d/%m/%Y')} ({n_ly} bản ghi)")
        buf.append(f"- **{ly_year - 1}:** So với {ly_year - 1}")
        buf.append(f"- **{ly_year - 2}:** So với {ly_year - 2}")
        buf.append("")
        buf.append("---")
        buf.append("")
        buf.append("#### Bảng số liệu so sánh")
        buf.append("")

        years_list = [cur_year, ly_year, ly_year - 1, ly_year - 2]

        if "qve" in parameters:
            buf.append("**Lưu lượng về (Qve) - m³/s:**")
            buf.append("")

            if use_all:
                header = f"| Hồ | {years_list[0]} (Min/Max/TB) | {years_list[1]} (Min/Max/TB) | {years_list[2]} (Min/Max/TB) | {years_list[3]} (Min/Max/TB) |"
                buf.append(header)
                buf.append("|------|---------------------|---------------------|---------------------|---------------------|")

                for rd in reservoirs_data:
                    cur = rd["qve_cur"]
                    ly = rd["qve_ly"]
                    ly2 = rd.get("qve_ly2")
                    ly3 = rd.get("qve_ly3")
                    lake_name = rd['name']
                    data_row = f"| {lake_name} | {cur.min:.2f}/{cur.max:.2f}/{cur.avg:.2f} | {ly.min:.2f}/{ly.max:.2f}/{ly.avg:.2f}"
                    if ly2:
                        data_row += f" | {ly2.min:.2f}/{ly2.max:.2f}/{ly2.avg:.2f}"
                    else:
                        data_row += " | -"
                    if ly3:
                        data_row += f" | {ly3.min:.2f}/{ly3.max:.2f}/{ly3.avg:.2f}"
                    else:
                        data_row += " | -"
                    data_row += " |"
                    buf.append(data_row)
                buf.append("")
            else:
                rd = reservoirs_data[0]
                cur = rd["qve_cur"]
                ly = rd["qve_ly"]
                ly2 = rd.get("qve_ly2")
                ly3 = rd.get("qve_ly3")
                lake_name = rd['name']
                header = f"| Hồ | {years_list[0]} (Min/Max/TB) | {years_list[1]} (Min/Max/TB) | {years_list[2]} (Min/Max/TB) | {years_list[3]} (Min/Max/TB) |"
                buf.append(header)
                buf.append("|------|---------------------|---------------------|---------------------|---------------------|")
                data_row = f"| {lake_name} | {cur.min:.2f}/{cur.max:.2f}/{cur.avg:.2f} | {ly.min:.2f}/{ly.max:.2f}/{ly.avg:.2f}"
                if ly2:
                    data_row += f" | {ly2.min:.2f}/{ly2.max:.2f}/{ly2.avg:.2f}"
                else:
                    data_row += " | -"
                if ly3:
                    data_row += f" | {ly3.min:.2f}/{ly3.max:.2f}/{ly3.avg:.2f}"
                else:
                    data_row += " | -"
                data_row += " |"
                buf.append(data_row)
            buf.append("")

        if "water_level" in parameters:
            buf.append("**Mực nước hồ (MNH) - m:**")
            buf.append("")

            if use_all:
                header = f"| Hồ | {years_list[0]} (Min/Max/TB) | {years_list[1]} (Min/Max/TB) | {years_list[2]} (Min/Max/TB) | {years_list[3]} (Min/Max/TB) |"
                buf.append(header)
                buf.append("|------|---------------------|---------------------|---------------------|---------------------|")

                for rd in reservoirs_data:
                    cur = rd["wl_cur"]
                    ly = rd["wl_ly"]
                    ly2 = rd.get("wl_ly2")
                    ly3 = rd.get("wl_ly3")
                    lake_name = rd['name']
                    data_row = f"| {lake_name} | {cur.min:.2f}/{cur.max:.2f}/{cur.avg:.2f} | {ly.min:.2f}/{ly.max:.2f}/{ly.avg:.2f}"
                    if ly2:
                        data_row += f" | {ly2.min:.2f}/{ly2.max:.2f}/{ly2.avg:.2f}"
                    else:
                        data_row += " | -"
                    if ly3:
                        data_row += f" | {ly3.min:.2f}/{ly3.max:.2f}/{ly3.avg:.2f}"
                    else:
                        data_row += " | -"
                    data_row += " |"
                    buf.append(data_row)
                buf.append("")
            else:
                rd = reservoirs_data[0]
                cur = rd["wl_cur"]
                ly = rd["wl_ly"]
                ly2 = rd.get("wl_ly2")
                ly3 = rd.get("wl_ly3")
                lake_name = rd['name']
                header = f"| Hồ | {years_list[0]} (Min/Max/TB) | {years_list[1]} (Min/Max/TB) | {years_list[2]} (Min/Max/TB) | {years_list[3]} (Min/Max/TB) |"
                buf.append(header)
                buf.append("|------|---------------------|---------------------|---------------------|---------------------|")
                data_row = f"| {lake_name} | {cur.min:.2f}/{cur.max:.2f}/{cur.avg:.2f} | {ly.min:.2f}/{ly.max:.2f}/{ly.avg:.2f}"
                if ly2:
                    data_row += f" | {ly2.min:.2f}/{ly2.max:.2f}/{ly2.avg:.2f}"
                else:
                    data_row += " | -"
                if ly3:
                    data_row += f" | {ly3.min:.2f}/{ly3.max:.2f}/{ly3.avg:.2f}"
                else:
                    data_row += " | -"
                data_row += " |"
                buf.append(data_row)
            buf.append("")

        if has_rain:
            buf.append("**Lượng mưa:**")
            buf.append("")
            buf.append(f"| Chỉ số | {years_list[0]} (mm) | {years_list[1]} (mm) | {years_list[2]} (mm) | {years_list[3]} (mm) |")
            buf.append("|-------------|-------------|-------------|-------------|-------------|")
            buf.append(f"| Tổng lượng mưa | {rain_cur:.1f} | {rain_ly:.1f} | {rain_ly2:.1f} | {rain_ly3:.1f} |")
            buf.append("")

        # Sản lượng
        has_any_output = (out_cur_sum > 0 or out_ly_sum > 0 or out_ly2_sum > 0 or out_ly3_sum > 0 or
                          out_cur_output > 0 or out_ly_output > 0 or out_ly2_output > 0 or out_ly3_output > 0 or
                          out_cur_sum_year > 0 or out_ly_sum_year > 0 or out_ly2_sum_year > 0 or out_ly3_sum_year > 0 or
                          out_cur_output_year > 0 or out_ly_output_year > 0 or out_ly2_output_year > 0 or out_ly3_output_year > 0)

        if "commercial_output" in parameters and has_any_output:
            buf.append("**Sản lượng (tr kWh):**")
            buf.append("")

            if full_month:
                # Hiển thị cả tháng và lũy kế từ đầu năm
                buf.append(f"| Chỉ số | {years_list[0]} | {years_list[1]} | {years_list[2]} | {years_list[3]} |")
                buf.append("|-------------|-------------|-------------|-------------|-------------|")
                buf.append(f"| Sản lượng đầu cực **tháng** (tr kWh) | {out_cur_output / _TR:.2f} | {out_ly_output / _TR:.2f} | {out_ly2_output / _TR:.2f} | {out_ly3_output / _TR:.2f} |")
                buf.append(f"| Sản lượng thương phẩm **tháng** (tr kWh) | {out_cur_sum / _TR:.2f} | {out_ly_sum / _TR:.2f} | {out_ly2_sum / _TR:.2f} | {out_ly3_sum / _TR:.2f} |")
                buf.append(f"| Sản lượng đầu cực **lũy kế** từ đầu năm (tr kWh) | {out_cur_output_year / _TR:.2f} | {out_ly_output_year / _TR:.2f} | {out_ly2_output_year / _TR:.2f} | {out_ly3_output_year / _TR:.2f} |")
                buf.append(f"| Sản lượng thương phẩm **lũy kế** từ đầu năm (tr kWh) | {out_cur_sum_year / _TR:.2f} | {out_ly_sum_year / _TR:.2f} | {out_ly2_sum_year / _TR:.2f} | {out_ly3_sum_year / _TR:.2f} |")
            elif full_year:
                buf.append(f"| Chỉ số | {years_list[0]} | {years_list[1]} | {years_list[2]} | {years_list[3]} |")
                buf.append("|-------------|-------------|-------------|-------------|-------------|")
                buf.append(f"| Sản lượng đầu cực năm (tr kWh) | {out_cur_output / _TR:.2f} | {out_ly_output / _TR:.2f} | {out_ly2_output / _TR:.2f} | {out_ly3_output / _TR:.2f} |")
                buf.append(f"| Sản lượng thương phẩm năm (tr kWh) | {out_cur_sum / _TR:.2f} | {out_ly_sum / _TR:.2f} | {out_ly2_sum / _TR:.2f} | {out_ly3_sum / _TR:.2f} |")
            else:
                buf.append(f"| Chỉ số | {years_list[0]} | {years_list[1]} | {years_list[2]} | {years_list[3]} |")
                buf.append("|-------------|-------------|-------------|-------------|-------------|")
                buf.append(f"| Sản lượng đầu cực ngày (tr kWh) | {out_cur_output / _TR:.2f} | {out_ly_output / _TR:.2f} | {out_ly2_output / _TR:.2f} | {out_ly3_output / _TR:.2f} |")
                buf.append(f"| Sản lượng thương phẩm ngày (tr kWh) | {out_cur_sum / _TR:.2f} | {out_ly_sum / _TR:.2f} | {out_ly2_sum / _TR:.2f} | {out_ly3_sum / _TR:.2f} |")
            buf.append("")

        buf.append("")
        buf.append("---")
        buf.append("")
        buf.append("#### Phân tích nguyên nhân")
        buf.append("")

        qve_up = qve_cur_avg > qve_ly_avg
        wl_up = wl_cur_avg > wl_ly_avg
        rain_up = rain_cur > rain_ly

        if "qve" in parameters:
            if qve_ly_avg <= 0:
                buf.append("- **Qve:** Không đủ dữ liệu cùng kỳ để so sánh.")
            else:
                delta = qve_cur_avg - qve_ly_avg
                pct = safe_pct(delta, qve_ly_avg)
                buf.append(
                    f"- **Qve:** TB {cur_year} **{qve_cur_avg:.2f} m³/s** (min {qve_cur_min:.2f}, max {qve_cur_max:.2f}), "
                    f"{ly_year} **{qve_ly_avg:.2f} m³/s** (min {qve_ly_min:.2f}, max {qve_ly_max:.2f}) → "
                    f"{'cao hơn' if qve_up else 'thấp hơn'} {abs(delta):.2f} m³/s ({pct:+.1f}%)."
                )

        if has_rain:
            delta = rain_cur - rain_ly
            buf.append(
                f"- **Lượng mưa:** {cur_year} **{rain_cur:.1f} mm**, {ly_year} **{rain_ly:.1f} mm** → "
                f"{'cao hơn' if rain_up else 'thấp hơn'} {abs(delta):.1f} mm."
            )

        # Thêm phân tích MNH khi có water_level trong parameters
        if "water_level" in parameters:
            if wl_ly_avg <= 0:
                buf.append("- **Mực nước hồ (MNH):** Không có dữ liệu cùng kỳ để so sánh.")
            else:
                wl_delta = wl_cur_avg - wl_ly_avg
                wl_pct = safe_pct(wl_delta, wl_ly_avg)
                wl_up = wl_cur_avg > wl_ly_avg
                buf.append(
                    f"- **Mực nước hồ (MNH):** TB {cur_year} **{wl_cur_avg:.2f} m**, {ly_year} **{wl_ly_avg:.2f} m** → "
                    f"{'cao hơn' if wl_up else 'thấp hơn'} {abs(wl_delta):.2f} m ({wl_pct:+.1f}%)."
                )

        if "commercial_output" in parameters:
            if has_any_output:
                if full_month:
                    label = "tháng"
                elif full_year:
                    label = "năm"
                else:
                    label = "ngày"
                buf.append(
                    f"- **Sản lượng {label} (tr kWh):** Đầu cực {cur_year} **{out_cur_output / _TR:.2f}**, Thương phẩm **{out_cur_sum / _TR:.2f}**; "
                    f"Đầu cực {ly_year} **{out_ly_output / _TR:.2f}**, Thương phẩm **{out_ly_sum / _TR:.2f}**."
                )
            else:
                tail = f" Dữ liệu trong sheet hiện có đến ngày {operational_latest_date_str}." if operational_latest_date_str else ""
                buf.append(f"- **Sản lượng:** Không tìm thấy dữ liệu trong khoảng {start_date}–{end_date} trong sheet vận hành.{tail}")

        buf.append("")

        # Focused conclusion
        if analysis_focus == "commercial_output" and has_any_output:
            buf.append("**Phân tích nguyên nhân Sản lượng:** Sản lượng tăng/giảm phụ thuộc vào Qve, mưa và MNH.")
            buf.append("- **Qve:** Nước về nhiều → có thể phát nhiều hơn; Qve thấp → sản lượng có xu hướng giảm.")
            buf.append("- **Mưa:** Mưa nhiều → tăng nước về lưu vực → Qve tăng; mưa ít → ngược lại.")
            buf.append("- **MNH:** MNH cao → trữ nước tốt, vận hành ổn định; MNH thấp → hạn chế phát.")
            if qve_ly_avg > 0:
                buf.append(
                    f" Trong kỳ này: Qve {cur_year} {'cao hơn' if qve_up else 'thấp hơn'} {ly_year}, "
                    f"mưa {'cao hơn' if rain_up else 'thấp hơn'}, MNH {'cao hơn' if wl_up else 'thấp hơn'} "
                    "→ sản lượng biến động phù hợp với nguồn nước về hồ."
                )
        else:
            if qve_ly_avg > 0 and ("qve" in parameters or analysis_focus == "qve"):
                buf.append("**Phân tích nguyên nhân Qve:** Qve tăng/giảm chủ yếu do **lượng mưa** và diễn biến dòng chảy lưu vực.")
                if qve_up and rain_up:
                    buf.append(f"**Kết luận:** Qve {cur_year} cao hơn {ly_year}, nguyên nhân chính do lượng mưa cao hơn → nước về hồ tăng.")
                elif qve_up and not rain_up:
                    buf.append("**Kết luận:** Qve cao hơn dù mưa thấp hơn; có thể do điều tiết/trữ nước từ trước hoặc độ phủ trạm mưa khác lưu vực.")
                elif (not qve_up) and rain_up:
                    buf.append("**Kết luận:** Mưa cao hơn nhưng Qve thấp hơn; có thể do tăng tích nước, tăng xả/tiêu thoát, hoặc độ trễ mưa–dòng chảy.")
                else:
                    buf.append(f"**Kết luận:** Qve {cur_year} thấp hơn {ly_year}, phù hợp với lượng mưa thấp hơn → nước về hồ giảm.")

        # Thêm kết luận MNH khi có water_level trong parameters
        if "water_level" in parameters and wl_ly_avg > 0:
            wl_up = wl_cur_avg > wl_ly_avg
            if wl_up:
                buf.append(f"**Kết luận MNH:** Mực nước hồ {cur_year} cao hơn {ly_year}, cho thấy lượng nước tích tụ trong hồ nhiều hơn.")
            else:
                buf.append(f"**Kết luận MNH:** Mực nước hồ {cur_year} thấp hơn {ly_year}, cần theo dõi và điều tiết phù hợp.")

        buf.append("")
        buf.append("---")
        buf.append("")

        return "\n".join(buf).strip()
