from unittest.mock import patch
from types import SimpleNamespace

from django.test import SimpleTestCase

from ai_tools.data_sources.db_stats import DbBackedSpreadsheet, DbBackedWorksheet
from ai_tools.vinhson_tools.services.forecast_service import (
    ForecastService,
    get_daily_data_for_month_vinhson,
)


def _stats_rows():
    return [
        ["Ngay", "MNH A", "MNH B", "MNH C", "Qve A", "Qve B", "Qve C"],
        ["Date", "Water A", "Water B", "Water C", "Qve A", "Qve B", "Qve C"],
        ["01/04/2023", "", "", "", "10", "20", "30"],
        ["02/04/2023", "", "", "", "12", "22", "32"],
        ["01/03/2023", "", "", "", "9", "19", "29"],
        ["01/03/2024", "", "", "", "11", "21", "31"],
        ["01/03/2025", "", "", "", "13", "23", "33"],
        ["01/04/2024", "", "", "", "14", "24", "34"],
        ["01/04/2025", "", "", "", "16", "26", "36"],
    ]


def _output_rows():
    return [
        [],
        [],
        ["", "01/04/2023", "Vinh Son -A", "", "", "", "", "", "", "", "", "", "100"],
        ["", "01/04/2023", "Vinh Son -B", "", "", "", "", "", "", "", "", "", "200"],
        ["", "01/04/2023", "Vinh Son -C", "", "", "", "", "", "", "", "", "", "300"],
        ["", "02/04/2023", "Vinh Son -A", "", "", "", "", "", "", "", "", "", "400"],
        ["", "01/04/2024", "Vinh Son -A", "", "", "", "", "", "", "", "", "", "500"],
        ["", "01/04/2025", "Vinh Son -A", "", "", "", "", "", "", "", "", "", "600"],
    ]


def _fake_stats_client(spreadsheet_id):
    if spreadsheet_id == "stats":
        return None, DbBackedSpreadsheet(
            "stats",
            [DbBackedWorksheet("Thong ke", _stats_rows)],
        )
    if spreadsheet_id == "operational":
        return None, DbBackedSpreadsheet(
            "operational",
            [DbBackedWorksheet("Sáº£n lÆ°á»£ng", _output_rows)],
        )
    return None, None


FAKE_CONFIG = SimpleNamespace(
    spreadsheet_id="operational",
    stats_export_spreadsheet_id="stats",
)


class VinhsonForecastTests(SimpleTestCase):
    databases = {"default"}

    @patch("ai_tools.vinhson_tools.services.forecast_service.GS_CONFIG", FAKE_CONFIG)
    @patch("ai_tools.vinhson_tools.services.forecast_service.get_stats_export_client", side_effect=_fake_stats_client)
    def test_daily_output_is_summed_across_reservoir_rows(self, _mock_client):
        _qve_by_day, output_by_day = get_daily_data_for_month_vinhson(2023, 4)

        self.assertEqual(output_by_day[1], 600)
        self.assertEqual(output_by_day[2], 400)

    @patch("ai_tools.vinhson_tools.services.forecast_service.GS_CONFIG", FAKE_CONFIG)
    @patch("ai_tools.vinhson_tools.services.forecast_service.get_stats_export_client", side_effect=_fake_stats_client)
    def test_year_forecast_includes_output(self, _mock_client):
        result = ForecastService().forecast_year(2026)

        self.assertIn("SanLuong", result)
        self.assertIn("600", result)
        self.assertIn("```chart", result)
        self.assertIn("QveHoA", result)
        self.assertIn("SanLuong", result)

    @patch("ai_tools.vinhson_tools.services.forecast_service.GS_CONFIG", FAKE_CONFIG)
    @patch("ai_tools.vinhson_tools.services.forecast_service.get_stats_export_client", side_effect=_fake_stats_client)
    def test_month_forecast_includes_qve_and_output_charts(self, _mock_client):
        with patch(
            "ai_tools.water_tools.weather_service.get_initial_levels_and_volumes",
            return_value={
                "Hồ A": (100.0, 1.0),
                "Hồ B": (100.0, 1.0),
                "Hồ C": (100.0, 1.0),
            },
        ), patch(
            "ai_tools.water_tools.weather_service.get_reservoir_max_useful_capacity",
            return_value=999.0,
        ):
            result = ForecastService().forecast_month(4, 2026)

        self.assertIn("```chart", result)
        self.assertIn('"type": "composed"', result)
        self.assertIn("QveHoA", result)
        self.assertIn("QveHoB", result)
        self.assertIn("QveHoC", result)
        self.assertIn("SanLuong", result)
        self.assertIn("```excel", result)
