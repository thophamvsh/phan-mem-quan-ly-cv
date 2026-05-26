"""
Hours service - Get hours data for Vĩnh Sơn
"""

from datetime import datetime
from typing import Dict, List
from ..config.columns import COL_HOURS_DATE, COL_HOURS_UNIT, COL_HOURS_OPERATING, COL_HOURS_STOPPED
from ..utils.dates import normalize_date
from ..core.retry import retry_with_backoff


class HoursService:
    """Service for retrieving hours data from Google Sheets"""

    def __init__(self, sheets_client):
        self.sheets_client = sheets_client

    def get_hours_data(self, date_obj: datetime, reservoir: str, worksheet_hours) -> Dict:
        """
        Lấy dữ liệu giờ phát cho 1 ngày cụ thể và 1 hồ cụ thể
        Args:
            date_obj: datetime object của ngày cần lấy
            reservoir: Tên hồ ("Vinh Son -A", "Vinh Son -B", "Vinh Son -C", hoặc "All")
            worksheet_hours: Google Sheets worksheet "Giờ phát"
        Returns:
            dict: {
                'units': [
                    {'unit': 'H1', 'hours_operating': '12.63', 'hours_stopped': '11.37', 'ytd': '284.98'},
                    {'unit': 'H2', 'hours_operating': '0', 'hours_stopped': '24', 'ytd': '288.00'},
                ],
                'total_hours_ytd': Lũy kế giờ phát từ đầu năm (tổng tất cả tổ máy)
            }
        """
        try:
            if not worksheet_hours:
                return {'units': [], 'total_hours_ytd': '-'}

            # Get all data from "Giờ phát" sheet (with retry)
            def fetch_hours_data():
                return worksheet_hours.get_all_values()

            all_data = retry_with_backoff(fetch_hours_data, max_retries=3, initial_delay=1)

            if len(all_data) < 3:
                return {'units': [], 'total_hours_ytd': '-'}

            data_rows = all_data[2:]  # Skip header rows

            # Find data for the specific date
            target_date = date_obj.date()
            year_start = datetime(target_date.year, 1, 1).date()
            year_end = datetime(target_date.year, 12, 31).date()

            units_data = []  # Chi tiết từng tổ máy cho ngày này
            units_ytd = {}   # Lũy kế riêng cho từng tổ máy
            total_hours_ytd = 0
            found_date = False

            # Filter units based on reservoir (case insensitive)
            allowed_units = []
            if reservoir == "Vinh Son -A":
                allowed_units = ['H1', 'H2']
            elif reservoir == "Vinh Son -B":
                allowed_units = ['H3']
            elif reservoir == "Vinh Son -C":
                allowed_units = []
            elif reservoir.lower() == "all":
                allowed_units = ['H1', 'H2', 'H3']
            else:
                allowed_units = ['H1', 'H2']

            allowed_units_upper = [u.upper() for u in allowed_units]

            # Single loop: Accumulate YTD and find target date
            for row in data_rows:
                if len(row) > COL_HOURS_OPERATING:
                    row_date_str = row[COL_HOURS_DATE].strip()
                    if not row_date_str:
                        continue

                    row_date = normalize_date(row_date_str)
                    if not row_date:
                        continue

                    if year_start <= row_date <= year_end:
                        try:
                            unit_name = row[COL_HOURS_UNIT].strip() if len(row) > COL_HOURS_UNIT else ""
                            hours_str = row[COL_HOURS_OPERATING].strip()

                            if allowed_units_upper and unit_name.upper() not in allowed_units_upper:
                                continue

                            if hours_str:
                                hours_val = float(hours_str.replace(',', '.'))

                                if row_date <= target_date:
                                    total_hours_ytd += hours_val
                                    if unit_name:
                                        if unit_name not in units_ytd:
                                            units_ytd[unit_name] = 0
                                        units_ytd[unit_name] += hours_val

                                if row_date == target_date:
                                    hours_operating = hours_str
                                    hours_stopped = row[COL_HOURS_STOPPED].strip() if len(row) > COL_HOURS_STOPPED else ""
                                    unit_ytd = units_ytd.get(unit_name, 0)

                                    units_data.append({
                                        'unit': unit_name,
                                        'hours_operating': hours_operating.replace(',', '.'),
                                        'hours_stopped': hours_stopped.replace(',', '.'),
                                        'ytd': f"{unit_ytd:.2f}"
                                    })
                                    found_date = True

                        except (ValueError, IndexError):
                            pass

            if not found_date:
                return {'units': [], 'total_hours_ytd': '-'}

            return {
                'units': units_data,
                'total_hours_ytd': f"{total_hours_ytd:.2f}"
            }

        except Exception as e:
            print(f"[ERROR] Error getting hours data: {e}", flush=True)
            return {'units': [], 'total_hours_ytd': '-'}
