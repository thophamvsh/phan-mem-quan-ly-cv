"""
Qve analysis service - Phân tích nguyên nhân Qve (so sánh năm hiện tại và cùng kỳ) cho Sông Hinh.

Nguồn:
- Qve + MNH: Google Sheets stats_export (sheet "Thống kê")
- Sản lượng: Google Sheets vận hành
- Lượng mưa: Supabase Do_Mua_VSH
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional, List, Tuple, Any, Callable, Dict

from ..config.settings import GS_CONFIG
from ..config.columns import OP_COLS
from ..core.sheets_client import GoogleSheetsClientManager
from ..utils.dates import parse_dmy_to_date, normalize_date
from ..utils.numbers import safe_cell, parse_float_loose, parse_kwh_integer


def _normalize_date_to_month_end(dt: datetime) -> datetime:
    """Adjust date to valid end of month (handles invalid dates like 30/02)."""
    try:
        return dt.replace(day=1, month=dt.month + 1) - timedelta(days=1)
    except ValueError:
        if dt.month == 12:
            return dt.replace(day=31)
        for day in range(31, 0, -1):
            try:
                return dt.replace(day=day)
            except ValueError:
                continue
        return dt


def _parse_date_safe(date_str: str) -> Optional[datetime]:
    """Parse date string, handling invalid days like 30/02."""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        parts = date_str.split("/")
        if len(parts) == 3:
            try:
                day = int(parts[0])
                month = int(parts[1])
                year = int(parts[2])
                dt = datetime(year, month, 1)
                if month == 12:
                    last_day = 31
                else:
                    last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
                day = min(day, last_day)
                return dt.replace(day=day)
            except Exception:
                pass
        return None


RAIN_COLS_SH = [
    "UBND_xa_Song_Hinh",
    "Xa_Ea_M_doan",
    "Thon_10_Xa_Ea_M_Doal",
    "Cu_Kroa",
    "Dap_Tran",
    "Xa_Ea_Trang",
]

# Sheet Thống kê Sông Hinh (0-based)
COL_DATE_STATS = 0
COL_WATER_STATS = 1
COL_QVE_STATS = 5

_TR = 1e6  # triệu kWh


def _parse_num(s: Any) -> Optional[float]:
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    return parse_float_loose(t)


def _date_from_operational_row(row: List, cols) -> Optional[date]:
    """Parse date from operational sheet: thử cột A (0) rồi B (1), DD/MM/YYYY hoặc YYYY-MM-DD."""
    for col in (0, getattr(cols, "COL_DATE", 1)):
        if col is None or col >= len(row):
            continue
        raw = str(safe_cell(row, col)).strip()
        if not raw:
            continue
        d = parse_dmy_to_date(raw)
        if d:
            return d
        d = normalize_date(raw)
        if d:
            return d
    return None


@dataclass(frozen=True)
class Stats:
    min: float = 0.0
    max: float = 0.0
    avg: float = 0.0
    sum: float = 0.0
    n: int = 0


def calc_stats(rows: List[List], col: int, parser: Callable[[Any], Optional[float]]) -> Stats:
    vals: List[float] = []
    for r in rows:
        v = parser(safe_cell(r, col))
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


def find_data_start_row(all_data: List[List]) -> int:
    """
    Heuristic tìm dòng bắt đầu dữ liệu ngày.
    Ưu tiên parse được ngày thật sự; fallback giữ giống logic cũ (7 hoặc 1).
    """
    for i, row in enumerate(all_data):
        ds = str(safe_cell(row, COL_DATE_STATS)).strip()
        if not ds:
            continue
        if parse_dmy_to_date(ds) or normalize_date(ds):
            return i
    if len(all_data) > 7:
        return 7
    return 1 if len(all_data) > 1 else 0


def filter_stats_rows_by_period(data_rows: List[List], start_d: date, end_d: date) -> List[List]:
    out: List[List] = []
    for row in data_rows:
        if len(row) <= COL_QVE_STATS:
            continue
        d = parse_dmy_to_date(safe_cell(row, COL_DATE_STATS))
        if not d:
            # nếu stats đôi khi có YYYY-MM-DD
            d = normalize_date(str(safe_cell(row, COL_DATE_STATS)).strip())
        if not d:
            continue
        if start_d <= d <= end_d:
            out.append(row)
    return out


def sum_rain_records(rain_records: List[dict], start_d: date, end_d: date, rain_cols: List[str]) -> float:
    total = 0.0
    for rec in rain_records or []:
        ts = rec.get("Thoi_gian") or ""
        if not ts:
            continue
        try:
            t = datetime.strptime(ts[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if not (start_d <= t <= end_d):
            continue

        row_sum = 0.0
        for c in rain_cols:
            v = rec.get(c)
            if v is None:
                continue
            try:
                row_sum += float(v)
            except (TypeError, ValueError):
                pass
        total += row_sum
    return total


class QveAnalysisService:
    """Phân tích Qve: so sánh năm nay vs cùng kỳ năm trước (Sheet ID: 1_y7Bbs9...)."""

    def __init__(self, manager: GoogleSheetsClientManager, cols=None):
        self.mgr = manager
        self.cols = cols or OP_COLS

    def get_qve_analysis(
        self,
        start_date: str,
        end_date: str,
        parameters: Optional[List[str]] = None,
        analysis_focus: str = "qve",  # "qve" | "commercial_output"
    ) -> str:
        if not parameters:
            parameters = ["qve", "water_level", "rainfall", "commercial_output"]

        start_obj = _parse_date_safe(start_date)
        end_obj = _parse_date_safe(end_date)
        if start_obj is None or end_obj is None:
            return f"Lỗi định dạng ngày: Ngày không hợp lệ '{start_date}' hoặc '{end_date}'. Vui lòng dùng DD/MM/YYYY."

        # Adjust end date to last day of month if it was invalid (e.g., 30/02 -> 28/02)
        end_obj = _normalize_date_to_month_end(end_obj)

        start_ly = start_obj.replace(year=start_obj.year - 1)
        end_ly = end_obj.replace(year=end_obj.year - 1)

        # Thêm 2 năm nữa để so sánh (năm -2 và năm -3)
        start_ly2 = start_obj.replace(year=start_obj.year - 2)
        end_ly2 = end_obj.replace(year=end_obj.year - 2)
        start_ly3 = start_obj.replace(year=start_obj.year - 3)
        end_ly3 = end_obj.replace(year=end_obj.year - 3)

        start_d, end_d = start_obj.date(), end_obj.date()
        start_ly_d, end_ly_d = start_ly.date(), end_ly.date()
        start_ly2_d, end_ly2_d = start_ly2.date(), end_ly2.date()
        start_ly3_d, end_ly3_d = start_ly3.date(), end_ly3.date()

        # -------------------------
        # 1) Load stats sheet (Qve/MNH)
        # -------------------------
        spreadsheet = self.mgr.get_write_spreadsheet(GS_CONFIG.stats_export_spreadsheet_id_songhinh)
        if not spreadsheet:
            return (
                "### Lỗi kết nối Google Sheets\n\n"
                "Không thể kết nối Google Sheets thống kê (Phân tích Qve dùng Sheet ID đã cấu hình)."
            )

        worksheets = spreadsheet.worksheets()
        stats_ws = None
        for ws in worksheets:
            if "Thống kê" in ws.title:
                stats_ws = ws
                break
        stats_ws = stats_ws or (worksheets[0] if worksheets else None)
        if not stats_ws:
            return "### Lỗi\n\nKhông tìm thấy worksheet thống kê trong Google Sheets."

        all_data = self.mgr.get_all_values_cached(stats_ws, cache_key="qve_analysis_stats_values")
        if not all_data or len(all_data) < 2:
            return "Không có dữ liệu trong Google Sheets thống kê."

        data_start = find_data_start_row(all_data)
        data_rows = all_data[data_start:] if data_start < len(all_data) else []
        if not data_rows:
            return "Không có dữ liệu sau dòng tiêu đề trong Google Sheets thống kê."

        cur_rows = filter_stats_rows_by_period(data_rows, start_d, end_d)
        ly_rows = filter_stats_rows_by_period(data_rows, start_ly_d, end_ly_d)
        ly2_rows = filter_stats_rows_by_period(data_rows, start_ly2_d, end_ly2_d)
        ly3_rows = filter_stats_rows_by_period(data_rows, start_ly3_d, end_ly3_d)

        if not cur_rows:
            return f"Không tìm thấy dữ liệu vận hành cho khoảng {start_date} đến {end_date}."
        if not ly_rows:
            return (
                "Không tìm thấy dữ liệu cùng kỳ năm trước "
                f"({start_ly.strftime('%d/%m/%Y')} đến {end_ly.strftime('%d/%m/%Y')})."
            )

        # Stats cho 4 năm
        qve_cur = calc_stats(cur_rows, COL_QVE_STATS, _parse_num)
        qve_ly = calc_stats(ly_rows, COL_QVE_STATS, _parse_num)
        qve_ly2 = calc_stats(ly2_rows, COL_QVE_STATS, _parse_num)
        qve_ly3 = calc_stats(ly3_rows, COL_QVE_STATS, _parse_num)
        wl_cur = calc_stats(cur_rows, COL_WATER_STATS, _parse_num)
        wl_ly = calc_stats(ly_rows, COL_WATER_STATS, _parse_num)
        wl_ly2 = calc_stats(ly2_rows, COL_WATER_STATS, _parse_num)
        wl_ly3 = calc_stats(ly3_rows, COL_WATER_STATS, _parse_num)

        qve_up = qve_cur.avg > qve_ly.avg

        # -------------------------
        # 2) Rainfall from Supabase
        # -------------------------
        rain_cur = 0.0
        rain_ly = 0.0
        rain_ly2 = 0.0
        rain_ly3 = 0.0
        has_rain = False

        if "rainfall" in parameters:
            from thuyvan_data_client import query_rainfall_data

            # Lấy dữ liệu từ năm xa nhất (ly3) đến năm hiện tại để đảm bảo đủ dữ liệu cho tất cả các năm
            start_rain_query = f"{start_ly3_d}"
            end_rain_query = f"{end_d}"
            rain_records = query_rainfall_data(start_date=start_rain_query, end_date=end_rain_query, limit=10000) or []
            rain_cur = sum_rain_records(rain_records, start_d, end_d, RAIN_COLS_SH)
            rain_ly = sum_rain_records(rain_records, start_ly_d, end_ly_d, RAIN_COLS_SH)
            rain_ly2 = sum_rain_records(rain_records, start_ly2_d, end_ly2_d, RAIN_COLS_SH)
            rain_ly3 = sum_rain_records(rain_records, start_ly3_d, end_ly3_d, RAIN_COLS_SH)
            has_rain = (rain_cur > 0 or rain_ly > 0 or rain_ly2 > 0 or rain_ly3 > 0)

        rain_up = rain_cur > rain_ly

        # -------------------------
        # 3) Operational output (optional)
        # -------------------------
        # Sản lượng tháng (cột Q, R)
        out_cur_sum = out_ly_sum = out_ly2_sum = out_ly3_sum = 0.0
        out_cur_output = out_ly_output = out_ly2_output = out_ly3_output = 0.0
        # Lũy kế từ đầu năm (cột U, V)
        out_cur_sum_year = out_ly_sum_year = out_ly2_sum_year = out_ly3_sum_year = 0.0
        out_cur_output_year = out_ly_output_year = out_ly2_output_year = out_ly3_output_year = 0.0
        self_use_cur = self_use_ly = self_use_ly2 = self_use_ly3 = 0.0
        operational_latest_date_str = ""
        out_cur_date_str = out_ly_date_str = ""

        if "commercial_output" in parameters:
            ws_op, _ = self.mgr.get_read_worksheets()
            if ws_op:
                op_data = self.mgr.get_all_values_cached(ws_op, cache_key="operational_all_values") or []
                if len(op_data) >= 2:
                    op_rows = op_data[2:] if len(op_data) >= 3 else op_data[1:]

                    all_dates: List[date] = []
                    # collect rows in periods for all 4 years
                    cur_period: List[Tuple[date, List]] = []
                    ly_period: List[Tuple[date, List]] = []
                    ly2_period: List[Tuple[date, List]] = []
                    ly3_period: List[Tuple[date, List]] = []

                    for row in op_rows:
                        if len(row) < 2:
                            continue
                        rd = _date_from_operational_row(row, self.cols)
                        if not rd:
                            continue
                        all_dates.append(rd)

                        if start_d <= rd <= end_d:
                            cur_period.append((rd, row))
                        if start_ly_d <= rd <= end_ly_d:
                            ly_period.append((rd, row))
                        if start_ly2_d <= rd <= end_ly2_d:
                            ly2_period.append((rd, row))
                        if start_ly3_d <= rd <= end_ly3_d:
                            ly3_period.append((rd, row))

                    if all_dates:
                        operational_latest_date_str = max(all_dates).strftime("%d/%m/%Y")

                    full_year = is_full_year_range(start_obj, end_obj)
                    full_month = is_full_month_range(start_obj, end_obj)

                    def add_day(row: List, acc_out: float, acc_tp: float, acc_self: float):
                        vo = _parse_num(safe_cell(row, self.cols.COL_OUTPUT_DAY))
                        vc = _parse_num(safe_cell(row, self.cols.COL_COMMERCIAL_DAY))
                        vs = parse_kwh_integer(safe_cell(row, self.cols.COL_SELF_USE))
                        if vo is not None:
                            acc_out += vo
                        if vc is not None:
                            acc_tp += vc
                        if vs is not None:
                            acc_self += vs
                        return acc_out, acc_tp, acc_self

                    def add_month(row: List, acc_out: float, acc_tp: float):
                        """Lấy sản lượng tháng từ cột Q (COL_OUTPUT_MONTH) và R (COL_COMMERCIAL_MONTH)."""
                        vo = _parse_num(safe_cell(row, self.cols.COL_OUTPUT_MONTH))
                        vc = _parse_num(safe_cell(row, self.cols.COL_COMMERCIAL_MONTH))
                        if vo is not None:
                            acc_out += vo
                        if vc is not None:
                            acc_tp += vc
                        return acc_out, acc_tp

                    def set_year_from_latest(period: List[Tuple[date, List]]):
                        if not period:
                            return None, None, 0.0, 0.0, 0.0
                        max_d = max(d for d, _ in period)
                        latest_row = None
                        for d, r in period:
                            if d == max_d:
                                latest_row = r
                                break
                        if not latest_row:
                            return None, None, 0.0, 0.0, 0.0

                        v_out = _parse_num(safe_cell(latest_row, self.cols.COL_OUTPUT_YEAR))
                        v_tp = _parse_num(safe_cell(latest_row, self.cols.COL_COMMERCIAL_YEAR))
                        out_val = v_out if v_out is not None else 0.0
                        tp_val = v_tp if v_tp is not None else 0.0
                        col_self = self.cols.COL_SELF_USE
                        self_sum = 0.0
                        for _, r in period:
                            if len(r) <= col_self:
                                continue
                            v = parse_kwh_integer(safe_cell(r, col_self))
                            if v is not None:
                                self_sum += v

                        return max_d, latest_row, out_val, tp_val, self_sum

                    if full_year:
                        max_d_cur, _, out_cur_output, out_cur_sum, self_use_cur = set_year_from_latest(cur_period)
                        max_d_ly, _, out_ly_output, out_ly_sum, self_use_ly = set_year_from_latest(ly_period)
                        max_d_ly2, _, out_ly2_output, out_ly2_sum, self_use_ly2 = set_year_from_latest(ly2_period)
                        max_d_ly3, _, out_ly3_output, out_ly3_sum, self_use_ly3 = set_year_from_latest(ly3_period)

                        if max_d_cur:
                            out_cur_date_str = max_d_cur.strftime("%d/%m/%Y")
                        if max_d_ly:
                            out_ly_date_str = max_d_ly.strftime("%d/%m/%Y")
                    elif full_month:
                        # Full month: lấy cột Q/R (tháng) VÀ cột U/V (lũy kế từ đầu năm) tại ngày cuối tháng
                        if cur_period:
                            max_d_cur = max(d for d, _ in cur_period)
                            for d, row in cur_period:
                                if d == max_d_cur:
                                    out_cur_output, out_cur_sum = add_month(row, out_cur_output, out_cur_sum)
                                    vo = _parse_num(safe_cell(row, self.cols.COL_OUTPUT_YEAR))
                                    vc = _parse_num(safe_cell(row, self.cols.COL_COMMERCIAL_YEAR))
                                    if vo is not None:
                                        out_cur_output_year = vo
                                    if vc is not None:
                                        out_cur_sum_year = vc
                            out_cur_date_str = max_d_cur.strftime("%d/%m/%Y")
                        if ly_period:
                            max_d_ly = max(d for d, _ in ly_period)
                            for d, row in ly_period:
                                if d == max_d_ly:
                                    out_ly_output, out_ly_sum = add_month(row, out_ly_output, out_ly_sum)
                                    vo = _parse_num(safe_cell(row, self.cols.COL_OUTPUT_YEAR))
                                    vc = _parse_num(safe_cell(row, self.cols.COL_COMMERCIAL_YEAR))
                                    if vo is not None:
                                        out_ly_output_year = vo
                                    if vc is not None:
                                        out_ly_sum_year = vc
                            out_ly_date_str = max_d_ly.strftime("%d/%m/%Y")
                        if ly2_period:
                            max_d_ly2 = max(d for d, _ in ly2_period)
                            for d, row in ly2_period:
                                if d == max_d_ly2:
                                    out_ly2_output, out_ly2_sum = add_month(row, out_ly2_output, out_ly2_sum)
                                    vo = _parse_num(safe_cell(row, self.cols.COL_OUTPUT_YEAR))
                                    vc = _parse_num(safe_cell(row, self.cols.COL_COMMERCIAL_YEAR))
                                    if vo is not None:
                                        out_ly2_output_year = vo
                                    if vc is not None:
                                        out_ly2_sum_year = vc
                        if ly3_period:
                            max_d_ly3 = max(d for d, _ in ly3_period)
                            for d, row in ly3_period:
                                if d == max_d_ly3:
                                    out_ly3_output, out_ly3_sum = add_month(row, out_ly3_output, out_ly3_sum)
                                    vo = _parse_num(safe_cell(row, self.cols.COL_OUTPUT_YEAR))
                                    vc = _parse_num(safe_cell(row, self.cols.COL_COMMERCIAL_YEAR))
                                    if vo is not None:
                                        out_ly3_output_year = vo
                                    if vc is not None:
                                        out_ly3_sum_year = vc
                    else:
                        for _, row in cur_period:
                            out_cur_output, out_cur_sum, self_use_cur = add_day(row, out_cur_output, out_cur_sum, self_use_cur)
                        for _, row in ly_period:
                            out_ly_output, out_ly_sum, self_use_ly = add_day(row, out_ly_output, out_ly_sum, self_use_ly)
                        for _, row in ly2_period:
                            out_ly2_output, out_ly2_sum, self_use_ly2 = add_day(row, out_ly2_output, out_ly2_sum, self_use_ly2)
                        for _, row in ly3_period:
                            out_ly3_output, out_ly3_sum, self_use_ly3 = add_day(row, out_ly3_output, out_ly3_sum, self_use_ly3)

                        if cur_period:
                            out_cur_date_str = max(d for d, _ in cur_period).strftime("%d/%m/%Y")
                        if ly_period:
                            out_ly_date_str = max(d for d, _ in ly_period).strftime("%d/%m/%Y")

        has_any_output = (out_cur_sum > 0 or out_ly_sum > 0 or out_ly2_sum > 0 or out_ly3_sum > 0 or
                          out_cur_output > 0 or out_ly_output > 0 or out_ly2_output > 0 or out_ly3_output > 0 or
                          out_cur_sum_year > 0 or out_ly_sum_year > 0 or out_ly2_sum_year > 0 or out_ly3_sum_year > 0 or
                          out_cur_output_year > 0 or out_ly_output_year > 0 or out_ly2_output_year > 0 or out_ly3_output_year > 0)

        # -------------------------
        # Build report markdown
        n_cur = len(cur_rows)
        n_ly = len(ly_rows)

        cur_year = start_obj.year
        ly_year = start_obj.year - 1
        years_list = [cur_year, ly_year, ly_year - 1, ly_year - 2]

        rows_md_4yr: List[Tuple[str, List[float], List[str]]] = []

        if has_rain:
            rows_md_4yr.append(("Tổng lượng mưa lưu vực (mm)", [rain_cur, rain_ly, rain_ly2, rain_ly3], ["mm"] * 4))

        if "commercial_output" in parameters and has_any_output:
            loss_pct_cur = (out_cur_output - out_cur_sum) / out_cur_output * 100.0 if out_cur_output and out_cur_output > 0 else 0.0
            loss_pct_ly = (out_ly_output - out_ly_sum) / out_ly_output * 100.0 if out_ly_output and out_ly_output > 0 else 0.0
            loss_pct_ly2 = (out_ly2_output - out_ly2_sum) / out_ly2_output * 100.0 if out_ly2_output and out_ly2_output > 0 else 0.0
            loss_pct_ly3 = (out_ly3_output - out_ly3_sum) / out_ly3_output * 100.0 if out_ly3_output and out_ly3_output > 0 else 0.0

            if full_month:
                # Hiển thị cả tháng và lũy kế từ đầu năm
                rows_md_4yr.extend([
                    ("Sản lượng đầu cực **tháng** (tr kWh)", [out_cur_output / _TR, out_ly_output / _TR, out_ly2_output / _TR, out_ly3_output / _TR], ["tr kWh"] * 4),
                    ("Sản lượng thương phẩm **tháng** (tr kWh)", [out_cur_sum / _TR, out_ly_sum / _TR, out_ly2_sum / _TR, out_ly3_sum / _TR], ["tr kWh"] * 4),
                    ("Sản lượng đầu cực **lũy kế** từ đầu năm (tr kWh)", [out_cur_output_year / _TR, out_ly_output_year / _TR, out_ly2_output_year / _TR, out_ly3_output_year / _TR], ["tr kWh"] * 4),
                    ("Sản lượng thương phẩm **lũy kế** từ đầu năm (tr kWh)", [out_cur_sum_year / _TR, out_ly_sum_year / _TR, out_ly2_sum_year / _TR, out_ly3_sum_year / _TR], ["tr kWh"] * 4),
                ])
            else:
                rows_md_4yr.extend([
                    ("Sản lượng đầu cực năm (tr kWh)", [out_cur_output / _TR, out_ly_output / _TR, out_ly2_output / _TR, out_ly3_output / _TR], ["tr kWh"] * 4),
                    ("Sản lượng thương phẩm năm (tr kWh)", [out_cur_sum / _TR, out_ly_sum / _TR, out_ly2_sum / _TR, out_ly3_sum / _TR], ["tr kWh"] * 4),
                    # ("Tự dùng (tr kWh)", [self_use_cur / _TR, self_use_ly / _TR, self_use_ly2 / _TR, self_use_ly3 / _TR], ["tr kWh"] * 4),
                    # ("Tổn hao (%)", [loss_pct_cur, loss_pct_ly, loss_pct_ly2, loss_pct_ly3], ["%"] * 4),
                ])

        # Format end_date for display
        end_date_display = end_obj.strftime("%d/%m/%Y")

        buf: List[str] = [
            "### Phân tích Qve / MNH / Sản lượng - Thủy điện Sông Hinh",
            "",
            "**Khoảng thời gian:**",
            f"- **{cur_year}:** {start_date} đến {end_date_display} ({n_cur} ngày)",
            f"- **{ly_year}:** {start_ly.strftime('%d/%m/%Y')} đến {end_ly.strftime('%d/%m/%Y')} ({n_ly} ngày)",
            f"- **{ly_year - 1}:** So với {ly_year - 1}",
            f"- **{ly_year - 2}:** So với {ly_year - 2}",
            "",
            "---",
            "",
            "#### Bảng số liệu so sánh",
            "",
        ]

        rows_qve_4yr: List[Tuple[str, List[float], List[str]]] = []
        rows_wl_4yr: List[Tuple[str, List[float], List[str]]] = []

        if "qve" in parameters:
            rows_qve_4yr.extend([
                ("Qve Min (m³/s)", [qve_cur.min, qve_ly.min, qve_ly2.min, qve_ly3.min], ["m³/s"] * 4),
                ("Qve Max (m³/s)", [qve_cur.max, qve_ly.max, qve_ly2.max, qve_ly3.max], ["m³/s"] * 4),
                ("Qve TB (m³/s)", [qve_cur.avg, qve_ly.avg, qve_ly2.avg, qve_ly3.avg], ["m³/s"] * 4),
            ])

        if "water_level" in parameters:
            rows_wl_4yr.extend([
                ("MNH Min (m)", [wl_cur.min, wl_ly.min, wl_ly2.min, wl_ly3.min], ["m"] * 4),
                ("MNH Max (m)", [wl_cur.max, wl_ly.max, wl_ly2.max, wl_ly3.max], ["m"] * 4),
                ("MNH TB (m)", [wl_cur.avg, wl_ly.avg, wl_ly2.avg, wl_ly3.avg], ["m"] * 4),
            ])

        if rows_qve_4yr:
            buf.append("**Lưu lượng về (Qve):**")
            buf.append("")
            buf.append(f"| Chỉ số | {years_list[0]} | {years_list[1]} | {years_list[2]} | {years_list[3]} |")
            buf.append("|-------------|-------------|-------------|-------------|-------------|")
            for name, values, units in rows_qve_4yr:
                formatted_values = [f"{v:.2f}" for v in values]
                buf.append(f"| {name} | {' | '.join(formatted_values)} |")
            buf.append("")

        if rows_wl_4yr:
            buf.append("**Mực nước hồ (MNH):**")
            buf.append("")
            buf.append(f"| Chỉ số | {years_list[0]} | {years_list[1]} | {years_list[2]} | {years_list[3]} |")
            buf.append("|-------------|-------------|-------------|-------------|-------------|")
            for name, values, units in rows_wl_4yr:
                formatted_values = [f"{v:.2f}" for v in values]
                buf.append(f"| {name} | {' | '.join(formatted_values)} |")
            buf.append("")

        if rows_md_4yr:
            buf.append(f"| Chỉ số | {years_list[0]} | {years_list[1]} | {years_list[2]} | {years_list[3]} |")
            buf.append("|-------------|-------------|-------------|-------------|-------------|")
            for name, values, units in rows_md_4yr:
                formatted_values = []
                for v, unit in zip(values, units):
                    if unit == "mm":
                        formatted_values.append(f"{v:.1f}")
                    else:
                        formatted_values.append(f"{v:.2f}")
                buf.append(f"| {name} | {' | '.join(formatted_values)} |")
            buf.append("")

        buf.extend(["", "---", "", "#### Phân tích nguyên nhân", ""])

        if "qve" in parameters:
            if qve_ly.avg <= 0:
                buf.append("- **Qve:** Không đủ dữ liệu cùng kỳ để so sánh.")
            else:
                delta = qve_cur.avg - qve_ly.avg
                pct = safe_pct(delta, qve_ly.avg)
                buf.append(
                    f"- **Qve:** TB {cur_year} **{qve_cur.avg:.2f} m³/s** (min {qve_cur.min:.2f}, max {qve_cur.max:.2f}), "
                    f"{ly_year} **{qve_ly.avg:.2f} m³/s** (min {qve_ly.min:.2f}, max {qve_ly.max:.2f}) → "
                    f"{'cao hơn' if qve_up else 'thấp hơn'} {abs(delta):.2f} m³/s ({pct:+.1f}%)."
                )

        if has_rain:
            buf.append(
                f"- **Lượng mưa:** {cur_year} **{rain_cur:.1f} mm**, {ly_year} **{rain_ly:.1f} mm** → "
                f"{'cao hơn' if rain_up else 'thấp hơn'} {abs(rain_cur - rain_ly):.1f} mm."
            )

        # Thêm phân tích MNH khi có water_level trong parameters
        if "water_level" in parameters:
            if wl_ly.avg <= 0:
                buf.append("- **Mực nước hồ (MNH):** Không có dữ liệu cùng kỳ để so sánh.")
            else:
                wl_delta = wl_cur.avg - wl_ly.avg
                wl_pct = safe_pct(wl_delta, wl_ly.avg)
                wl_up = wl_cur.avg > wl_ly.avg
                buf.append(
                    f"- **Mực nước hồ (MNH):** TB {cur_year} **{wl_cur.avg:.2f} m** (min {wl_cur.min:.2f}, max {wl_cur.max:.2f}), "
                    f"{ly_year} **{wl_ly.avg:.2f} m** (min {wl_ly.min:.2f}, max {wl_ly.max:.2f}) → "
                    f"{'cao hơn' if wl_up else 'thấp hơn'} {abs(wl_delta):.2f} m ({wl_pct:+.1f}%)."
                )

        if "commercial_output" in parameters:
            if has_any_output:
                buf.append(
                    f"- **Sản lượng:** Đầu cực {cur_year} **{out_cur_output / _TR:.2f} tr kWh**, TP **{out_cur_sum / _TR:.2f} tr kWh**; "
                    f"Đầu cực {ly_year} **{out_ly_output / _TR:.2f} tr kWh**, TP **{out_ly_sum / _TR:.2f} tr kWh**. "
                    f"Tự dùng: {self_use_cur / _TR:.2f} / {self_use_ly / _TR:.2f} tr kWh. "
                    f"Tổn hao: {loss_pct_cur:.2f}% / {loss_pct_ly:.2f}%."
                )
            else:
                tail = f" Dữ liệu trong sheet hiện có đến ngày {operational_latest_date_str}." if operational_latest_date_str else ""
                buf.append(f"- **Sản lượng:** Không tìm thấy dữ liệu trong khoảng {start_date}–{end_date} trong sheet vận hành.{tail}")

        buf.append("")

        if analysis_focus == "commercial_output" and has_any_output:
            wl_up = wl_cur.avg > wl_ly.avg
            buf.append("**Phân tích nguyên nhân Sản lượng:** Sản lượng tăng/giảm phụ thuộc vào Qve, mưa và MNH.")
            buf.append("- **Qve:** Nước về nhiều → có thể phát nhiều hơn; Qve thấp → sản lượng có xu hướng giảm.")
            buf.append("- **Mưa:** Mưa nhiều → tăng nước về lưu vực → Qve tăng; mưa ít → ngược lại.")
            buf.append("- **MNH:** MNH cao → trữ nước tốt, vận hành ổn định; MNH thấp → hạn chế phát.")
            if qve_ly.avg > 0:
                buf.append(
                    f" Trong kỳ này: Qve {cur_year} {'cao hơn' if qve_up else 'thấp hơn'} {ly_year}, "
                    f"mưa {'cao hơn' if rain_up else 'thấp hơn'}, MNH {'cao hơn' if wl_up else 'thấp hơn'} "
                    "→ sản lượng biến động phù hợp với nguồn nước về hồ."
                )
        elif qve_ly.avg > 0 and ("qve" in parameters or analysis_focus == "qve"):
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
        if "water_level" in parameters and wl_ly.avg > 0:
            wl_up = wl_cur.avg > wl_ly.avg
            if wl_up:
                buf.append(f"**Kết luận MNH:** Mực nước hồ {cur_year} cao hơn {ly_year}, cho thấy lượng nước tích tụ trong hồ nhiều hơn.")
            else:
                buf.append(f"**Kết luận MNH:** Mực nước hồ {cur_year} thấp hơn {ly_year}, cần theo dõi và điều tiết phù hợp.")

        return "\n".join(buf).strip()
