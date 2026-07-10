from django.test import SimpleTestCase

from ai_tools.songhinh_tools.config.columns import OP_COLS
from ai_tools.songhinh_tools.services.operational_service import (
    OperationalService as SongHinhOperationalService,
)
from ai_tools.vinhson_tools.config import columns as vs_cols
from ai_tools.vinhson_tools.services.operational_service import (
    OperationalService as VinhSonOperationalService,
)


class FakeWorksheet:
    def __init__(self, values):
        self.values = values

    def get_all_values(self):
        return self.values


class FakeSongHinhManager:
    def __init__(self, values):
        self.values = values

    def get_read_worksheets(self):
        return FakeWorksheet(self.values), object()

    def get_all_values_cached(self, worksheet, cache_key=None):
        return worksheet.get_all_values()


class FakeSongHinhHours:
    def get_hours_data(self, date_obj, worksheet):
        return {
            "units": [
                {"unit": "1", "hours_operating": "10", "hours_stopped": "14", "ytd": "1000"},
                {"unit": "2", "hours_operating": "11", "hours_stopped": "13", "ytd": "1100"},
            ]
        }


class FakeVinhSonSheetsClient:
    def __init__(self, values):
        self.values = values

    def get_client(self):
        return object(), FakeWorksheet(self.values), object()


class FakeVinhSonHours:
    def get_hours_data(self, date_obj, reservoir_name, worksheet):
        return {
            "units": [
                {"unit": "H1", "hours_operating": "9", "hours_stopped": "15", "ytd": "900"},
                {"unit": "H2", "hours_operating": "8", "hours_stopped": "16", "ytd": "800"},
            ]
        }


def _row(size=24):
    return [""] * size


class OperationalSingleDayReportTests(SimpleTestCase):
    def test_songhinh_specific_date_reports_current_production_without_comparison(self):
        row = _row()
        row[OP_COLS.COL_DATE] = "12/06/2026"
        row[OP_COLS.COL_WATER_LEVEL] = "208.50"
        row[OP_COLS.COL_VOLUME] = "120"
        row[OP_COLS.COL_INFLOW] = "30"
        row[OP_COLS.COL_TURBINE] = "25"
        row[OP_COLS.COL_SPILLWAY] = "0"
        row[OP_COLS.COL_QC_DAY] = "100"
        row[OP_COLS.COL_OUTPUT_DAY] = "95"
        row[OP_COLS.COL_COMMERCIAL_DAY] = "90"
        row[OP_COLS.COL_QC_MONTH_ACC] = "1000"
        row[OP_COLS.COL_OUTPUT_MONTH] = "950"
        row[OP_COLS.COL_COMMERCIAL_MONTH] = "900"
        row[OP_COLS.COL_QC_YEAR_ACC] = "10000"
        row[OP_COLS.COL_OUTPUT_YEAR] = "9500"
        row[OP_COLS.COL_COMMERCIAL_YEAR] = "9000"
        row[OP_COLS.COL_PLAN_YEAR] = "12000"
        row[OP_COLS.COL_SELF_USE] = "5"

        service = SongHinhOperationalService(
            FakeSongHinhManager([["header"], ["header"], row]),
            hours_service=FakeSongHinhHours(),
        )

        report = service.get_operational_data(date_str="2026-06-12")

        self.assertIn("**Ngày báo cáo:** 12/06/2026", report)
        self.assertNotIn("**So sánh:**", report)
        self.assertIn("| Ngày | 95 | 90 | 100 | 90.00% |", report)
        self.assertIn("| Tháng | 950 | 900 | 1.000 | 90.00% |", report)
        self.assertIn("| Năm | 9.500 | 9.000 | 12.000 | 75.00% |", report)

    def test_vinhson_specific_date_reports_current_production_without_comparison(self):
        row = _row()
        row[vs_cols.COL_DATE] = "12/06/2026"
        row[vs_cols.COL_RESERVOIR] = "Vinh Son -A"
        row[vs_cols.COL_WATER_LEVEL] = "775.10"
        row[vs_cols.COL_VOLUME] = "20"
        row[vs_cols.COL_INFLOW] = "12"
        row[vs_cols.COL_TURBINE] = "10"
        row[vs_cols.COL_SPILLWAY] = "0"
        row[vs_cols.COL_QC_DAY] = "100"
        row[vs_cols.COL_OUTPUT_DAY] = "95"
        row[vs_cols.COL_COMMERCIAL_DAY] = "90"
        row[vs_cols.COL_QC_MONTH_ACC] = "1000"
        row[vs_cols.COL_OUTPUT_MONTH] = "950"
        row[vs_cols.COL_COMMERCIAL_MONTH] = "900"
        row[vs_cols.COL_QC_YEAR_ACC] = "10000"
        row[vs_cols.COL_OUTPUT_YEAR] = "9500"
        row[vs_cols.COL_COMMERCIAL_YEAR] = "9000"
        row[vs_cols.COL_PLAN_YEAR] = "12000"
        row[vs_cols.COL_SELF_USE] = "5"

        service = VinhSonOperationalService()
        service.sheets_client = FakeVinhSonSheetsClient([["header"], ["header"], row])
        service.hours_service = FakeVinhSonHours()

        report = service.get_operational_data(date="2026-06-12", reservoir="All")

        self.assertIn("**Ngày báo cáo:** 12/06/2026", report)
        self.assertNotIn("**So sánh:**", report)
        self.assertIn("| Ngày | 95 | 90 | 100 | 90.00% |", report)
        self.assertIn("| Tháng | 950 | 900 | 1.000 | 90.00% |", report)
        self.assertIn("| Năm | 9.500 | 9.000 | 12.000 | 75.00% |", report)
