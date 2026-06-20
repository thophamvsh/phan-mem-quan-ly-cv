from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase

from ai_tools.songhinh_tools.config.columns import OP_COLS
from ai_tools.songhinh_tools.services.forecast_service import (
    ForecastServiceSH,
    find_data_start_row,
    get_daily_data_for_month,
    get_month_data,
    get_output_month,
)
from ai_tools.songhinh_tools.services.hierarchical_service import HierarchicalStatisticsService as SongHinhHierarchy
from ai_tools.vinhson_tools.services.hierarchical_service import HierarchicalStatisticsService as VinhSonHierarchy


class SongHinhForecastHelperTests(SimpleTestCase):
    def test_find_data_start_and_month_average_handle_valid_and_missing_rows(self):
        rows = [["header", "x"], [], ["01/05/2026", "", "", "", "", "10"], ["02/05/2026", "", "", "", "", "20"], ["bad", "", "", "", "", "30"]]
        self.assertEqual(find_data_start_row(rows), 2)
        self.assertEqual(get_month_data(rows, 2026, 5, 5), 15)
        self.assertIsNone(get_month_data(rows, 2025, 5, 5))
        self.assertEqual(find_data_start_row([["header", "x"]] * 8), 7)
        self.assertEqual(find_data_start_row([["header", "x"]]), 1)

    def test_output_month_selects_latest_day_and_handles_failures(self):
        size = OP_COLS.COL_COMMERCIAL_MONTH + 1
        early = [""] * size
        early[OP_COLS.COL_DATE] = "01/05/2026"
        early[OP_COLS.COL_COMMERCIAL_MONTH] = "100"
        late = [""] * size
        late[OP_COLS.COL_DATE] = "31/05/2026"
        late[OP_COLS.COL_COMMERCIAL_MONTH] = "300"
        worksheet = Mock(title="production")
        worksheet.get_all_values.return_value = [["header", "x"], early, late]
        spreadsheet = Mock()
        spreadsheet.worksheets.return_value = [worksheet]
        manager = Mock()
        manager.get_write_spreadsheet.return_value = spreadsheet
        self.assertEqual(get_output_month(manager, 2026, 5), 300)

        manager.get_write_spreadsheet.return_value = None
        self.assertIsNone(get_output_month(manager, 2026, 5))
        manager.get_write_spreadsheet.side_effect = RuntimeError("offline")
        self.assertIsNone(get_output_month(manager, 2026, 5))

    def test_daily_data_combines_stats_and_production_sheets(self):
        stats_row = ["01/05/2026", "", "", "", "", "12"]
        size = max(OP_COLS.COL_COMMERCIAL_DAY, OP_COLS.COL_DATE) + 1
        production_row = [""] * size
        production_row[OP_COLS.COL_DATE] = "01/05/2026"
        production_row[OP_COLS.COL_COMMERCIAL_DAY] = "1,200"
        stats_ws = Mock(title="stats")
        stats_ws.get_all_values.return_value = [["header", "x"], stats_row]
        prod_ws = Mock(title="production")
        prod_ws.get_all_values.return_value = [["header", "x"], production_row]
        stats_sheet = Mock()
        stats_sheet.worksheets.return_value = [stats_ws]
        prod_sheet = Mock()
        prod_sheet.worksheets.return_value = [prod_ws]
        manager = Mock()
        manager.get_write_spreadsheet.side_effect = [stats_sheet, prod_sheet]

        qve, output = get_daily_data_for_month(manager, 2026, 5)

        self.assertEqual(qve, [(1, 12)])
        self.assertEqual(output, [(1, 1200)])


class SongHinhForecastServiceTests(SimpleTestCase):
    @patch("ai_tools.songhinh_tools.services.forecast_service.get_daily_data_for_month")
    @patch("ai_tools.songhinh_tools.services.forecast_service.get_output_month")
    @patch("ai_tools.songhinh_tools.services.forecast_service.get_month_data")
    @patch("ai_tools.songhinh_tools.services.forecast_service._get_manager")
    def test_month_forecast_builds_daily_report_charts_and_excel(self, get_manager, month_data, output_month, daily_data):
        worksheet = Mock(title="stats")
        spreadsheet = Mock()
        spreadsheet.worksheets.return_value = [worksheet]
        manager = Mock()
        manager.get_write_spreadsheet.return_value = spreadsheet
        manager.get_all_values_cached.return_value = [["header", "x"], ["01/05/2025", "x"]]
        get_manager.return_value = manager
        month_data.side_effect = lambda rows, year, month, col: {2025: 10, 2024: 20, 2023: 30, 2026: 12}.get(year)
        output_month.side_effect = lambda manager, year, month: {2025: 100, 2024: 200, 2023: 300}.get(year)
        daily_data.return_value = ([(1, 10), (2, 10), (3, 10), (4, 10)], [(1, 100), (2, 100), (3, 100), (4, 100)])

        with (
            patch("ai_tools.water_tools.weather_service.get_rainfall_forecast", return_value={"2026-06-01": 40, "2026-06-02": 20, "2026-06-03": 10, "2026-06-04": 0}),
            patch("ai_tools.water_tools.weather_service.get_initial_levels_and_volumes", return_value={"songhinh": (205, 100)}),
            patch("ai_tools.water_tools.weather_service.get_monthly_rainfall", side_effect=[100, 50]),
            patch("ai_tools.water_tools.weather_service.get_daily_rainfall_history", return_value={1: 1, 2: 2, 3: 3, 4: 4}),
            patch("ai_tools.water_tools.weather_service.get_reservoir_max_useful_capacity", return_value=999),
        ):
            report = ForecastServiceSH().forecast_month(6, 2026)

        self.assertIn("Qve", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)
        self.assertIn("bao-cao-du-bao-song-hinh-06-2026.xlsx", report)

    @patch("ai_tools.songhinh_tools.services.forecast_service._get_manager")
    def test_month_and_year_forecast_report_connection_failure(self, get_manager):
        manager = Mock()
        manager.get_write_spreadsheet.return_value = None
        get_manager.return_value = manager
        self.assertIn("Google Sheets", ForecastServiceSH().forecast_month(1, 2026))
        self.assertIn("Google Sheets", ForecastServiceSH().forecast_year(2026))

    @patch("ai_tools.songhinh_tools.services.forecast_service._get_manager")
    def test_month_forecast_reports_missing_worksheet_and_data(self, get_manager):
        manager = Mock()
        spreadsheet = Mock()
        spreadsheet.worksheets.return_value = []
        manager.get_write_spreadsheet.return_value = spreadsheet
        get_manager.return_value = manager
        self.assertIn("worksheet", ForecastServiceSH().forecast_month(6, 2026))

        spreadsheet.worksheets.return_value = [Mock(title="stats")]
        manager.get_all_values_cached.return_value = []
        self.assertIn("d", ForecastServiceSH().forecast_month(6, 2026))


class HierarchicalEdgeTests(SimpleTestCase):
    def test_songhinh_hierarchy_handles_connection_worksheet_and_short_data_errors(self):
        service = SongHinhHierarchy.__new__(SongHinhHierarchy)
        service.manager = Mock()
        service.manager.get_write_spreadsheet.return_value = None
        self.assertIn("CSDL", service.get_hierarchical_statistics("year", "2026"))

        spreadsheet = Mock()
        spreadsheet.worksheets.side_effect = RuntimeError("offline")
        service.manager.get_write_spreadsheet.return_value = spreadsheet
        self.assertIn("offline", service.get_hierarchical_statistics("year", "2026"))

        spreadsheet.worksheets.side_effect = None
        spreadsheet.worksheets.return_value = [Mock(title="stats")]
        service.manager.get_all_values_cached.return_value = [["header"]]
        self.assertIn("d", service.get_hierarchical_statistics("year", "2026"))

    def test_vinhson_root_wrapper_renders_accumulated_sections_and_subcall_returns_raw(self):
        service = VinhSonHierarchy()

        def fake_impl(**kwargs):
            acc = kwargs["_accumulators"]
            acc["charts"].append({"type": "line", "data": []})
            acc["excel_sheets"].append({"name": "Data", "rows": []})
            acc["conclusions"].append("Conclusion")
            return "BODY"

        with patch.object(service, "_get_hierarchical_statistics_impl", side_effect=fake_impl):
            report = service.get_hierarchical_statistics("week", "2/6/2026")
            self.assertIn("BODY", report)
            self.assertIn("```chart", report)
            self.assertIn("```excel", report)
            self.assertIn("Conclusion", report)

            accumulators = {"charts": [], "excel_sheets": [], "conclusions": []}
            raw = service.get_hierarchical_statistics("year", "2026", _is_subcall=True, _accumulators=accumulators)
            self.assertEqual(raw, "BODY")

    def test_vinhson_impl_routes_all_reservoir_aggregations_and_date_ranges(self):
        service = VinhSonHierarchy()
        with (
            patch.object(service, "_get_date_range_statistics_combined", return_value="combined") as combined,
            patch.object(service, "_get_date_range_statistics", return_value="single") as single,
            patch.object(service, "_get_all_reservoirs_year_stats", return_value="year") as year_stats,
            patch.object(service, "_get_month_all_reservoirs", return_value="month") as month_stats,
        ):
            self.assertEqual(service._get_hierarchical_statistics_impl("range", reservoir="All", start_date="1/1/2026", end_date="2/1/2026"), "combined")
            self.assertEqual(service._get_hierarchical_statistics_impl("range", reservoir="Vinh Son -A", start_date="1/1/2026", end_date="2/1/2026"), "single")
            self.assertEqual(service._get_hierarchical_statistics_impl("year", "2026", reservoir="All"), "year")
            self.assertEqual(service._get_hierarchical_statistics_impl("month", "1/2026", reservoir="All"), "month")
            combined.assert_called_once()
            single.assert_called_once()
            year_stats.assert_called_once()
            month_stats.assert_called_once()
