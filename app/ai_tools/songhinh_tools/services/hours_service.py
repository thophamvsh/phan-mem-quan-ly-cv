"""
Hours service - Get hours data for Sông Hinh
"""

from datetime import datetime, date
from typing import Dict, List, Any, Optional
import gspread
from ..config.columns import H_COLS
from ..core.sheets_client import GoogleSheetsClientManager
from ..utils.dates import parse_dmy_to_date
from ..utils.numbers import safe_cell, parse_float_loose


class HoursService:
    def __init__(self, manager: GoogleSheetsClientManager, cols=None):
        self.mgr = manager
        self.cols = cols or H_COLS

    def get_hours_data(self, date_obj: datetime, worksheet_hours: Optional[gspread.Worksheet]) -> Dict[str, Any]:
        """
        Return:
        {
          'units': [{'unit': '1','hours_operating':'17','hours_stopped':'7','ytd':'284.98'}, ...],
          'total_hours_ytd': '...'
        }
        """
        if not worksheet_hours:
            return {"units": [], "total_hours_ytd": "-"}

        try:
            all_data = self.mgr.get_all_values_cached(worksheet_hours, cache_key="hours_all_values")
            if len(all_data) < 3:
                return {"units": [], "total_hours_ytd": "-"}

            data_rows = all_data[2:]  # skip header rows
            target = date_obj.date()
            year_start = date(target.year, 1, 1)
            year_end = date(target.year, 12, 31)

            units_ytd: Dict[str, float] = {}
            total_ytd = 0.0

            # Pass 1: accumulate YTD up to target date
            for row in data_rows:
                row_date = parse_dmy_to_date(safe_cell(row, self.cols.COL_HOURS_DATE))
                if not row_date:
                    continue
                if not (year_start <= row_date <= year_end):
                    continue
                if row_date > target:
                    continue

                unit_name = safe_cell(row, self.cols.COL_HOURS_UNIT)
                hours_val = parse_float_loose(safe_cell(row, self.cols.COL_HOURS_OPERATING))
                if hours_val is None:
                    continue

                total_ytd += hours_val
                if unit_name:
                    units_ytd[unit_name] = units_ytd.get(unit_name, 0.0) + hours_val

            # Pass 2: extract target-day rows (unit details)
            units_data: List[Dict[str, str]] = []
            for row in data_rows:
                row_date = parse_dmy_to_date(safe_cell(row, self.cols.COL_HOURS_DATE))
                if row_date != target:
                    continue

                unit_name = safe_cell(row, self.cols.COL_HOURS_UNIT)
                hours_operating = safe_cell(row, self.cols.COL_HOURS_OPERATING, "-")
                hours_stopped = safe_cell(row, self.cols.COL_HOURS_STOPPED, "-")
                unit_ytd = units_ytd.get(unit_name, 0.0)

                units_data.append(
                    {
                        "unit": unit_name,
                        "hours_operating": hours_operating or "-",
                        "hours_stopped": hours_stopped or "-",
                        "ytd": f"{unit_ytd:.2f}",
                    }
                )

            if not units_data:
                return {"units": [], "total_hours_ytd": "-"}

            return {"units": units_data, "total_hours_ytd": f"{total_ytd:.2f}"}

        except Exception as e:
            print(f"[ERROR] Error getting hours data: {e}", flush=True)
            return {"units": [], "total_hours_ytd": "-"}
