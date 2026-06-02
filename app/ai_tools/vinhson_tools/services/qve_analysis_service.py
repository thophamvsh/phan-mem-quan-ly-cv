"""
Qve analysis service - Phân tích nguyên nhân Qve (so sánh năm hiện tại và cùng kỳ) cho Vĩnh Sơn.

Nguồn:
- Qve + MNH: Google Sheets stats_export (sheet "Thống kê")
- Sản lượng: Google Sheets vận hành
- Lượng mưa: dữ liệu mưa nội bộ từ app thongsothuyvan
"""

from __future__ import annotations

import json
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
    COL_TURBINE,
    COL_SPILLWAY,
)
from ..core.stats_export_client import get_stats_export_client
from ..core.sheets_client import SheetsClient
from ..core.retry import retry_with_backoff
from ..utils.dates import normalize_date
from ..utils.numbers import parse_number, parse_number_for_mnh, parse_number_for_qve


# Internal rainfall columns (3 trạm)
RAIN_COLS_VS = ["Ho_A_TD_Vinh_Son", "Ho_B_TD_Vinh_Son", "Ho_C_TD_Vinh_Son"]

# Sheet Thống kê (0-based)
COL_DATE_STATS = 0
COL_WATER_A, COL_WATER_B, COL_WATER_C = 1, 2, 3
COL_QVE_A, COL_QVE_B, COL_QVE_C = 4, 5, 6

RES_MAP = {"Vinh Son -A": 0, "Vinh Son -B": 1, "Vinh Son -C": 2}

_TR = 1e6  # triệu kWh


def _local_date(dt) -> Optional[date]:
    if not dt:
        return None
    try:
        from django.utils import timezone

        return timezone.localtime(dt).date()
    except Exception:
        return dt.date()


def load_vinhson_stats_rows_from_db(start_d: date, end_d: date) -> List[List]:
    """Load Qve/MNH from thongsothuyvan.ThongsoSanxuat instead of stats sheet."""
    try:
        from thongsothuyvan.models import ThongsoSanxuat
    except Exception:
        return []

    rows: List[List] = []
    qs = (
        ThongsoSanxuat.objects.filter(
            nha_may="vinhson",
            thoi_gian__date__gte=start_d,
            thoi_gian__date__lte=end_d,
        )
        .order_by("thoi_gian")
    )
    for obj in qs:
        d = _local_date(obj.thoi_gian)
        if not d:
            continue
        rows.append([
            d.strftime("%d/%m/%Y"),
            obj.cot_g,
            obj.mucnuoc_thuongluu_ho_b,
            obj.mucnuoc_thuongluu_ho_c,
            obj.cot_i,
            obj.luuluong_ve_ho_b,
            obj.luuluong_ve_ho_c,
        ])
    return rows


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


def to_operational_res_name(name: str) -> str:
    if name == "Hồ A":
        return "Vinh Son -A"
    if name == "Hồ B":
        return "Vinh Son -B"
    if name == "Hồ C":
        return "Vinh Son -C"
    return name


def sum_rain_records(rain_records: List[dict], start_d: date, end_d: date, cols: List[str]) -> float:
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
        for c in cols:
            v = rec.get(c)
            if v is not None:
                try:
                    row_sum += float(v)
                except (TypeError, ValueError):
                    pass
        total += row_sum
    return total


def calc_yield_index(avg_qve: float, num_days: int, total_rain: float) -> float:
    total_V_in = avg_qve * 86400 * num_days / 1000000.0
    return total_V_in / total_rain if total_rain > 0 else 0.0


def get_discharge_stats(period: List[Tuple[date, str, list]], col_qcm: int, col_qxl: int, res_name: str = None) -> Tuple[float, float]:
    qcm_vals = []
    qxl_vals = []
    for _, name, row in period:
        name_clean = name.strip()
        # Đối với Vĩnh Sơn, các dòng lưu lượng phát điện (Qcm) trong CSDL cục bộ được lưu dưới tên 'vinhson'.
        # Thực tế, lưu lượng phát điện Qcm này chỉ dành cho Hồ A (Vinh Son -A).
        # Do đó, nếu đang tìm Hồ A, ta chấp nhận cả tên 'Vinh Son -A' và 'vinhson'.
        is_match = False
        if res_name:
            if name_clean.lower() == res_name.lower():
                is_match = True
            elif res_name == "Vinh Son -A" and name_clean.lower() == "vinhson":
                is_match = True
        else:
            is_match = True

        if not is_match:
            continue

        qcm = _parse_num(_cell(row, col_qcm))
        qxl = _parse_num(_cell(row, col_qxl))
        if qcm is not None:
            qcm_vals.append(qcm)
        if qxl is not None:
            qxl_vals.append(qxl)
    qcm_avg = sum(qcm_vals) / len(qcm_vals) if qcm_vals else 0.0
    qxl_avg = sum(qxl_vals) / len(qxl_vals) if qxl_vals else 0.0
    return qcm_avg, qxl_avg


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

        # Standardize reservoir input
        if reservoir in ("Hồ A", "vinhson", "Vinh Son", "Vinh Son -A"):
            reservoir = "Vinh Son -A"
        elif reservoir in ("Hồ B", "Vinh Son -B"):
            reservoir = "Vinh Son -B"
        elif reservoir in ("Hồ C", "Vinh Son -C"):
            reservoir = "Vinh Son -C"

        use_all = reservoir in (None, "All", "")
        res_idx = RES_MAP.get(reservoir, 0)

        # -------------------------
        # 1) Load stats sheet (Qve/MNH)
        # -------------------------
        data_rows = load_vinhson_stats_rows_from_db(start_ly3_d, end_d)
        if not data_rows:
            _, spreadsheet = get_stats_export_client(GS_CONFIG.stats_export_spreadsheet_id)
            if not spreadsheet:
                return (
                    "### Lỗi kết nối dữ liệu\n\n"
                    "Không thể kết nối nguồn dữ liệu thống kê."
                )

            stats_ws = pick_stats_worksheet(spreadsheet)
            if not stats_ws:
                return "### Lỗi\n\nKhông tìm thấy bảng dữ liệu thống kê."

            all_data = retry_with_backoff(stats_ws.get_all_values, max_retries=3, initial_delay=1)
            if not all_data or len(all_data) < 2:
                return "Không có dữ liệu thống kê."

            data_start = find_data_start_row(all_data)
            data_rows = all_data[data_start:] if data_start < len(all_data) else []
        if not data_rows:
            return "Không có dữ liệu sau khi lọc nguồn dữ liệu thống kê."

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
        # 2) Rainfall from internal hydrological data
        # -------------------------
        rain_cur = rain_ly = rain_ly2 = rain_ly3 = 0.0
        has_rain = False

        for rd in reservoirs_data:
            rd["rain_cur"] = 0.0
            rd["rain_ly"] = 0.0
            rd["rain_ly2"] = 0.0
            rd["rain_ly3"] = 0.0

        if "rainfall" in parameters:
            from thuyvan_data_client import query_rainfall_data

            start_rain_query = f"{start_ly3_d}"
            end_rain_query = f"{end_d}"
            rain_records = query_rainfall_data(start_date=start_rain_query, end_date=end_rain_query, limit=10000) or []

            def get_rain_cols_for_reservoir(res_name: str) -> List[str]:
                if res_name in ("Vinh Son -A", "Hồ A"):
                    return ["Ho_A_TD_Vinh_Son"]
                if res_name in ("Vinh Son -B", "Hồ B"):
                    return ["Ho_B_TD_Vinh_Son"]
                if res_name in ("Vinh Son -C", "Hồ C"):
                    return ["Ho_C_TD_Vinh_Son"]
                return RAIN_COLS_VS

            rain_cols_to_sum = RAIN_COLS_VS if use_all else get_rain_cols_for_reservoir(reservoir)
            rain_cur = sum_rain_records(rain_records, start_d, end_d, rain_cols_to_sum)
            rain_ly = sum_rain_records(rain_records, start_ly_d, end_ly_d, rain_cols_to_sum)
            rain_ly2 = sum_rain_records(rain_records, start_ly2_d, end_ly2_d, rain_cols_to_sum)
            rain_ly3 = sum_rain_records(rain_records, start_ly3_d, end_ly3_d, rain_cols_to_sum)

            has_rain = (rain_cur > 0 or rain_ly > 0 or rain_ly2 > 0 or rain_ly3 > 0)

            for rd in reservoirs_data:
                res_rain_cols = get_rain_cols_for_reservoir(rd["name"])
                rd["rain_cur"] = sum_rain_records(rain_records, start_d, end_d, res_rain_cols)
                rd["rain_ly"] = sum_rain_records(rain_records, start_ly_d, end_ly_d, res_rain_cols)
                rd["rain_ly2"] = sum_rain_records(rain_records, start_ly2_d, end_ly2_d, res_rain_cols)
                rd["rain_ly3"] = sum_rain_records(rain_records, start_ly3_d, end_ly3_d, res_rain_cols)

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

        cur_period: List[Tuple[date, str, list]] = []
        ly_period: List[Tuple[date, str, list]] = []
        ly2_period: List[Tuple[date, str, list]] = []
        ly3_period: List[Tuple[date, str, list]] = []

        if "commercial_output" in parameters or "water_level" in parameters:
            _, op_ws, _ = SheetsClient().get_client()
            if op_ws:
                op_data = retry_with_backoff(op_ws.get_all_values, max_retries=3, initial_delay=1) or []
                if len(op_data) >= 2:
                    op_rows = op_data[2:] if len(op_data) >= 3 else op_data[1:]

                    all_dates: List[date] = []
                    for row in op_rows:
                        rd = _date_from_operational_row(row)
                        if not rd:
                            continue
                        all_dates.append(rd)

                        res_name = str(_cell(row, COL_RESERVOIR)).strip()
                        
                        is_res_match = False
                        if not use_all:
                            if res_name.lower() == reservoir.lower():
                                is_res_match = True
                            elif reservoir == "Vinh Son -A" and res_name.lower() == "vinhson":
                                is_res_match = True
                        else:
                            is_res_match = True
                            
                        if not is_res_match:
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
        years_list = [cur_year, ly_year, ly_year - 1, ly_year - 2]
        has_any_output = (out_cur_sum > 0 or out_ly_sum > 0 or out_ly2_sum > 0 or out_ly3_sum > 0 or
                          out_cur_output > 0 or out_ly_output > 0 or out_ly2_output > 0 or out_ly3_output > 0 or
                          out_cur_sum_year > 0 or out_ly_sum_year > 0 or out_ly2_sum_year > 0 or out_ly3_sum_year > 0 or
                          out_cur_output_year > 0 or out_ly_output_year > 0 or out_ly2_output_year > 0 or out_ly3_output_year > 0)

        # Tính toán Qcm, Qxl cho từng hồ chứa
        for rd in reservoirs_data:
            res_op_name = to_operational_res_name(rd["name"])
            qcm_cur = qxl_cur = qcm_ly = qxl_ly = 0.0
            if cur_period:
                qcm_cur, qxl_cur = get_discharge_stats(cur_period, COL_TURBINE, COL_SPILLWAY, res_op_name)
            if ly_period:
                qcm_ly, qxl_ly = get_discharge_stats(ly_period, COL_TURBINE, COL_SPILLWAY, res_op_name)
            rd["qcm_cur"] = qcm_cur
            rd["qxl_cur"] = qxl_cur
            rd["qcm_ly"] = qcm_ly
            rd["qxl_ly"] = qxl_ly

        buf: List[str] = []
        buf.append(f"### Phân tích Qve / MNH / Sản lượng - Thủy điện Vĩnh Sơn ({res_label})")
        buf.append("")
        buf.append("**Khoảng thời gian:**")
        buf.append(f"- **{cur_year}:** {start_date} đến {end_date} ({n_cur} bản ghi)")
        buf.append(f"- **{ly_year}:** {start_ly.strftime('%d/%m/%Y')} đến {end_ly.strftime('%d/%m/%Y')} ({n_ly} bản ghi)")
        buf.append(f"- **{ly_year - 1}:** So với {ly_year - 1}")
        buf.append(f"- **{ly_year - 2}:** So với {ly_year - 2}")
        chart_sections = []
        chart_years = [
            (years_list[3], "ly3"),
            (years_list[2], "ly2"),
            (years_list[1], "ly"),
            (years_list[0], "cur"),
        ]
        qve_key_map = {"Hồ A": "QveHoA", "Hồ B": "QveHoB", "Hồ C": "QveHoC"}
        wl_key_map = {"Hồ A": "MNHHoA", "Hồ B": "MNHHoB", "Hồ C": "MNHHoC"}

        if "qve" in parameters or "rainfall" in parameters:
            rain_by_year = {
                years_list[3]: round(rain_ly3, 1),
                years_list[2]: round(rain_ly2, 1),
                years_list[1]: round(rain_ly, 1),
                years_list[0]: round(rain_cur, 1),
            }
            chart_data_qve = []
            for year, suffix in chart_years:
                item = {"Nam": str(year), "LuongMua": rain_by_year[year]}
                for rd in reservoirs_data:
                    key = qve_key_map.get(rd["name"], "Qve")
                    item[key] = round(rd[f"qve_{suffix}"].avg, 2)
                chart_data_qve.append(item)

            chart_qve_json = {
                "type": "composed",
                "title": "So sánh Qve TB (m³/s) & lượng mưa (mm) qua 4 năm",
                "data": chart_data_qve,
                "xKey": "Nam",
                "barKeys": ["LuongMua"] if has_rain else [],
                "lineKeys": [qve_key_map.get(rd["name"], "Qve") for rd in reservoirs_data],
                "barColors": ["#3b82f6"],
                "lineColors": ["#10b981", "#f59e0b", "#ef4444"],
                "barUnit": " mm",
                "lineUnit": " m³/s",
            }
            import json
            chart_sections.append(f"\n\n```chart\n{json.dumps(chart_qve_json, ensure_ascii=False, indent=2)}\n```\n")

        if "water_level" in parameters:
            chart_data_wl = []
            for year, suffix in chart_years:
                item = {"Nam": str(year)}
                for rd in reservoirs_data:
                    key = wl_key_map.get(rd["name"], "MNH")
                    item[key] = round(rd[f"wl_{suffix}"].avg, 2)
                chart_data_wl.append(item)

            chart_wl_json = {
                "type": "line",
                "title": "So sánh MNH trung bình (m) qua 4 năm",
                "data": chart_data_wl,
                "xKey": "Nam",
                "yKeys": [wl_key_map.get(rd["name"], "MNH") for rd in reservoirs_data],
                "colors": ["#06b6d4", "#8b5cf6", "#ef4444"],
                "unit": " m",
            }
            import json
            chart_sections.append(f"\n\n```chart\n{json.dumps(chart_wl_json, ensure_ascii=False, indent=2)}\n```\n")

        if has_any_output:
            chart_out_json = {
                "type": "bar",
                "title": "So sánh sản lượng thương phẩm (triệu kWh) qua 4 năm",
                "data": [
                    {"Nam": str(years_list[3]), "SanLuong": round(out_ly3_sum / _TR, 2)},
                    {"Nam": str(years_list[2]), "SanLuong": round(out_ly2_sum / _TR, 2)},
                    {"Nam": str(years_list[1]), "SanLuong": round(out_ly_sum / _TR, 2)},
                    {"Nam": str(years_list[0]), "SanLuong": round(out_cur_sum / _TR, 2)},
                ],
                "xKey": "Nam",
                "yKeys": ["SanLuong"],
                "colors": ["#f59e0b"],
                "unit": " tr kWh",
            }
            import json
            chart_sections.append(f"\n\n```chart\n{json.dumps(chart_out_json, ensure_ascii=False, indent=2)}\n```\n")

        buf.extend(chart_sections)
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
        buf.append("#### Phân tích nguyên nhân & Cân bằng nước chuyên sâu")
        buf.append("")

        # 1. Phân tích tương quan Mưa - Dòng chảy (Rainfall-Runoff Relation)
        if "qve" in parameters:
            buf.append("**1. Phân tích tương quan Mưa - Dòng chảy (Rainfall-Runoff Relation):**")
            if has_rain:
                for rd in reservoirs_data:
                    name = rd["name"]
                    rain_c = rd["rain_cur"]
                    rain_l = rd["rain_ly"]
                    qve_c = rd["qve_cur"].avg
                    qve_l = rd["qve_ly"].avg

                    yield_c = calc_yield_index(qve_c, n_cur, rain_c) if rain_c > 0 else 0.0
                    yield_l = calc_yield_index(qve_l, n_ly, rain_l) if rain_l > 0 else 0.0

                    V_c = qve_c * 86400 * n_cur / 1e6
                    V_l = qve_l * 86400 * n_ly / 1e6

                    buf.append(f"- **{name}:**")
                    buf.append(
                        f"  - Năm {cur_year}: Tổng nước về **{V_c:.2f} tr m³**, lượng mưa **{rain_c:.1f} mm** → Chỉ số sinh dòng chảy $R_{{yield}}$: **{yield_c:.3f} tr m³/mm**."
                    )
                    buf.append(
                        f"  - Cùng kỳ năm trước ({ly_year}): Tổng nước về **{V_l:.2f} tr m³**, lượng mưa **{rain_l:.1f} mm** → Chỉ số sinh dòng chảy $R_{{yield}}$: **{yield_l:.3f} tr m³/mm**."
                    )

                    if yield_c > 0 and yield_l > 0:
                        if yield_c > yield_l * 1.05:
                            pct = safe_pct(yield_c - yield_l, yield_l)
                            buf.append(
                                f"  - *Nhận xét*: Chỉ số sinh dòng chảy năm {cur_year} cao hơn cùng kỳ **{pct:+.1f}%**. "
                                "Điều này cho thấy hiệu suất sinh dòng chảy của lưu vực tăng cao, có thể do lưu vực đã đạt trạng thái bão hòa nước từ trước "
                                "(độ ẩm đất cao, tổn thất thấm giảm) hoặc có sự bổ cập dòng chảy ngầm tốt hơn."
                            )
                        elif yield_c < yield_l * 0.95:
                            pct = safe_pct(yield_c - yield_l, yield_l)
                            buf.append(
                                f"  - *Nhận xét*: Chỉ số sinh dòng chảy năm {cur_year} thấp hơn cùng kỳ **{pct:.1f}%**. "
                                "Cho thấy tổn thất lưu vực năm nay lớn hơn (thấm, bốc hơi mạnh hoặc lượng mưa rơi xuống bị hấp thụ để bù đắp "
                                "cho độ ẩm đất bị khô hạn kéo dài trước đó), làm giảm hiệu quả sinh dòng chảy bề mặt."
                            )
                        else:
                            buf.append("  - *Nhận xét*: Hiệu suất sinh dòng chảy giữa hai năm tương đương nhau, dòng chảy về hồ biến động tuyến tính theo lượng mưa.")
                    else:
                        buf.append("  - *Nhận xét*: Chưa đủ dữ liệu mưa trạm tương ứng để phân tích hiệu suất dòng chảy.")
            else:
                buf.append("- Không đủ số liệu lượng mưa đo trạm để tính toán hiệu suất sinh dòng chảy lưu vực.")
            buf.append("")

        # 2. Phân tích Cân bằng nước vật lý (Physical Water Balance)
        if "water_level" in parameters:
            buf.append("**2. Phân tích Cân bằng nước vật lý (Physical Water Balance):**")

            for rd in reservoirs_data:
                name = rd["name"]
                wl_c = rd["wl_cur"].avg
                wl_l = rd["wl_ly"].avg
                wl_delta = wl_c - wl_l

                qve_c = rd["qve_cur"].avg
                qve_l = rd["qve_ly"].avg

                qcm_c = rd.get("qcm_cur", 0.0)
                qxl_c = rd.get("qxl_cur", 0.0)
                qcm_l = rd.get("qcm_ly", 0.0)
                qxl_l = rd.get("qxl_ly", 0.0)

                buf.append(f"- **{name}:**")
                buf.append(
                    f"  - Mực nước trung bình: Năm {cur_year} (**{wl_c:.2f} m**), cùng kỳ năm {ly_year} (**{wl_l:.2f} m**) → "
                    f"{'cao hơn' if wl_delta > 0 else 'thấp hơn'} so với cùng kỳ năm {ly_year} là **{abs(wl_delta):.2f} m**."
                )

                if cur_period:
                    buf.append(
                        f"  - Cân bằng lưu lượng năm {cur_year}: Qve trung bình **{qve_c:.2f} m³/s** đối trọng với tổng lưu lượng xả "
                        f"**{(qcm_c + qxl_c):.2f} m³/s** (phát điện Qcm: **{qcm_c:.2f} m³/s**, xả tràn Qxl: **{qxl_c:.2f} m³/s**)."
                    )
                    buf.append(
                        f"  - Cân bằng lưu lượng năm {ly_year}: Qve trung bình **{qve_l:.2f} m³/s** đối trọng với tổng lưu lượng xả "
                        f"**{(qcm_l + qxl_l):.2f} m³/s** (phát điện Qcm: **{qcm_l:.2f} m³/s**, xả tràn Qxl: **{qxl_l:.2f} m³/s**)."
                    )

                    # Giải thích hiện tượng dựa trên mối quan hệ vật lý
                    if wl_delta > 0 and qve_c < qve_l:
                        buf.append(
                            f"  - *Giải thích hiện tượng*: Mặc dù lưu lượng nước về hồ (Qve) năm nay thấp hơn cùng kỳ, nhưng MNH vẫn cao hơn "
                            f"là do nhà máy đã chủ động điều tiết giảm lưu lượng phát điện (Qcm giảm **{abs(qcm_c - qcm_l):.2f} m³/s**). "
                            "Đây là chiến lược trữ nước hợp lý để bảo dưỡng cột nước vận hành tối ưu."
                        )
                    elif wl_delta < 0 and qve_c > qve_l:
                        buf.append(
                            f"  - *Giải thích hiện tượng*: Mặc dù Qve năm nay cao hơn cùng kỳ, nhưng MNH lại thấp hơn "
                            f"là do nhà máy tăng cường phát điện (Qcm tăng **{abs(qcm_c - qcm_l):.2f} m³/s**) "
                            "hoặc phát sinh xả tràn để đáp ứng phương thức huy động của hệ thống."
                        )
                    elif wl_delta > 0:
                        buf.append(
                            "  - *Giải thích hiện tượng*: Mực nước hồ tăng cao phù hợp với nguồn nước về hồ dồi dào, lượng nước về lớn hơn "
                            "lượng nước xả phát điện giúp hồ chủ động tích nước lên mực nước cao."
                        )
                    else:
                        buf.append(
                            "  - *Giải thích hiện tượng*: Mực nước hồ giảm do lưu lượng nước về không đủ bù đắp lượng nước phát điện phục vụ "
                            "phụ tải hệ thống."
                        )
                else:
                    buf.append("  - *Giải thích hiện tượng*: Thiếu dữ liệu lưu lượng xả qua máy (Qcm) để lập bảng cân bằng nước chi tiết.")
            buf.append("")

        # 3. Tương quan liên hồ chứa trong bậc thang thủy điện Vĩnh Sơn
        if use_all:
            buf.append("**3. Tương quan liên hồ chứa trong bậc thang thủy điện Vĩnh Sơn:**")
            buf.append(
                "- Sơ đồ vận hành liên hồ chứa cho thấy mối liên kết thủy văn giữa Hồ A, B và C. Sự điều tiết mực nước tại Hồ A (hồ chứa thượng nguồn lớn nhất) "
                "và lượng xả qua máy phát điện có ảnh hưởng trực tiếp đến lưu lượng bổ cấp và khả năng trữ nước của các hồ chứa phía hạ du trong bậc thang."
            )
            buf.append("")

        buf.append("---")
        buf.append("")

        excel_summary_rows = [
            ["Nhom", "Ho", "Chi so", "Don vi", str(years_list[0]), str(years_list[1]), str(years_list[2]), str(years_list[3])]
        ]
        stat_suffixes = ["cur", "ly", "ly2", "ly3"]

        def stat_excel_values(rd: Dict[str, Any], prefix: str, field: str) -> List[float]:
            values: List[float] = []
            for suffix in stat_suffixes:
                stat = rd.get(f"{prefix}_{suffix}") or Stats()
                values.append(round(float(getattr(stat, field, 0.0) or 0.0), 2))
            return values

        if "qve" in parameters:
            for rd in reservoirs_data:
                lake_name = rd["name"]
                excel_summary_rows.append(["Qve", lake_name, "Qve Min", "m3/s", *stat_excel_values(rd, "qve", "min")])
                excel_summary_rows.append(["Qve", lake_name, "Qve Max", "m3/s", *stat_excel_values(rd, "qve", "max")])
                excel_summary_rows.append(["Qve", lake_name, "Qve TB", "m3/s", *stat_excel_values(rd, "qve", "avg")])

        if "water_level" in parameters:
            for rd in reservoirs_data:
                lake_name = rd["name"]
                excel_summary_rows.append(["MNH", lake_name, "MNH Min", "m", *stat_excel_values(rd, "wl", "min")])
                excel_summary_rows.append(["MNH", lake_name, "MNH Max", "m", *stat_excel_values(rd, "wl", "max")])
                excel_summary_rows.append(["MNH", lake_name, "MNH TB", "m", *stat_excel_values(rd, "wl", "avg")])

        if has_rain:
            excel_summary_rows.append([
                "Mua",
                "Luu vuc",
                "Tong luong mua",
                "mm",
                round(rain_cur, 1),
                round(rain_ly, 1),
                round(rain_ly2, 1),
                round(rain_ly3, 1),
            ])

        if "commercial_output" in parameters and has_any_output:
            excel_summary_rows.append([
                "San luong",
                "Nha may",
                "San luong dau cuc",
                "tr kWh",
                round(out_cur_output / _TR, 2),
                round(out_ly_output / _TR, 2),
                round(out_ly2_output / _TR, 2),
                round(out_ly3_output / _TR, 2),
            ])
            excel_summary_rows.append([
                "San luong",
                "Nha may",
                "San luong thuong pham",
                "tr kWh",
                round(out_cur_sum / _TR, 2),
                round(out_ly_sum / _TR, 2),
                round(out_ly2_sum / _TR, 2),
                round(out_ly3_sum / _TR, 2),
            ])
            if full_month:
                excel_summary_rows.append([
                    "San luong",
                    "Nha may",
                    "San luong dau cuc luy ke",
                    "tr kWh",
                    round(out_cur_output_year / _TR, 2),
                    round(out_ly_output_year / _TR, 2),
                    round(out_ly2_output_year / _TR, 2),
                    round(out_ly3_output_year / _TR, 2),
                ])
                excel_summary_rows.append([
                    "San luong",
                    "Nha may",
                    "San luong thuong pham luy ke",
                    "tr kWh",
                    round(out_cur_sum_year / _TR, 2),
                    round(out_ly_sum_year / _TR, 2),
                    round(out_ly2_sum_year / _TR, 2),
                    round(out_ly3_sum_year / _TR, 2),
                ])

        excel_chart_header = ["Nam", "Luong mua (mm)", "San luong thuong pham (tr kWh)"]
        for rd in reservoirs_data:
            excel_chart_header.extend([f"{rd['name']} Qve TB (m3/s)", f"{rd['name']} MNH TB (m)"])
        excel_chart_rows = [excel_chart_header]

        rain_values = {
            years_list[3]: rain_ly3,
            years_list[2]: rain_ly2,
            years_list[1]: rain_ly,
            years_list[0]: rain_cur,
        }
        output_values = {
            years_list[3]: out_ly3_sum / _TR if has_any_output else None,
            years_list[2]: out_ly2_sum / _TR if has_any_output else None,
            years_list[1]: out_ly_sum / _TR if has_any_output else None,
            years_list[0]: out_cur_sum / _TR if has_any_output else None,
        }
        for year, suffix in [(years_list[3], "ly3"), (years_list[2], "ly2"), (years_list[1], "ly"), (years_list[0], "cur")]:
            output_value = output_values[year]
            row = [
                str(year),
                round(rain_values[year], 1),
                round(output_value, 2) if output_value is not None else None,
            ]
            for rd in reservoirs_data:
                row.extend([
                    round(float((rd.get(f"qve_{suffix}") or Stats()).avg or 0.0), 2),
                    round(float((rd.get(f"wl_{suffix}") or Stats()).avg or 0.0), 2),
                ])
            excel_chart_rows.append(row)

        excel_report_json = {
            "title": f"Bao cao phan tich Qve Vinh Son {start_obj.strftime('%d%m%Y')}-{end_obj.strftime('%d%m%Y')}",
            "fileName": f"bao-cao-phan-tich-qve-vinh-son-{start_obj.strftime('%Y%m%d')}-{end_obj.strftime('%Y%m%d')}.xlsx",
            "prompt": "Bạn có cần xuất file Excel để báo cáo không?",
            "sheets": [
                {"name": "Tong hop", "rows": excel_summary_rows},
                {"name": "Du lieu bieu do", "rows": excel_chart_rows},
            ],
        }
        buf.append(f"\n\n```excel\n{json.dumps(excel_report_json, ensure_ascii=False, indent=2)}\n```\n")

        return "\n".join(buf).strip()
