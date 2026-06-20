import json
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from ai_tools.songhinh_tools.config.columns import H_COLS
from ai_tools.songhinh_tools.core.retry import retry_with_backoff as retry_songhinh
from ai_tools.songhinh_tools.services.hours_service import HoursService as SongHinhHoursService
from ai_tools.vinhson_tools import config as _vs_config
from ai_tools.vinhson_tools.config.columns import (
    COL_HOURS_DATE,
    COL_HOURS_OPERATING,
    COL_HOURS_STOPPED,
    COL_HOURS_UNIT,
)
from ai_tools.vinhson_tools.core.retry import retry_with_backoff as retry_vinhson
from ai_tools.vinhson_tools.services.hours_service import HoursService as VinhSonHoursService


def _tool_call(name, arguments=None):
    return SimpleNamespace(
        id=f"call-{name}",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments or {})),
    )


class RetryTests(SimpleTestCase):
    @patch("ai_tools.songhinh_tools.core.retry.time.sleep")
    def test_songhinh_retry_uses_exponential_backoff_then_succeeds(self, sleep):
        func = Mock(side_effect=[RuntimeError("one"), RuntimeError("two"), "ok"])
        self.assertEqual(retry_songhinh(func, max_retries=3, initial_delay=0.5), "ok")
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])

    @patch("ai_tools.vinhson_tools.core.retry.time.sleep")
    def test_vinhson_retry_raises_last_error(self, sleep):
        func = Mock(side_effect=RuntimeError("failed"))
        with self.assertRaisesRegex(RuntimeError, "failed"):
            retry_vinhson(func, max_retries=3, initial_delay=0.25)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.25, 0.5])


class HoursServiceTests(SimpleTestCase):
    @staticmethod
    def _row(size, mapping):
        row = [""] * size
        for index, value in mapping.items():
            row[index] = value
        return row

    def test_songhinh_hours_accumulates_ytd_and_ignores_bad_rows(self):
        rows = [
            ["header"],
            ["header"],
            self._row(12, {H_COLS.COL_HOURS_DATE: "01/01/2026", H_COLS.COL_HOURS_UNIT: "H1", H_COLS.COL_HOURS_OPERATING: "2"}),
            self._row(12, {H_COLS.COL_HOURS_DATE: "12/06/2026", H_COLS.COL_HOURS_UNIT: "H1", H_COLS.COL_HOURS_OPERATING: "3.5", H_COLS.COL_HOURS_STOPPED: "20.5"}),
            self._row(12, {H_COLS.COL_HOURS_DATE: "13/06/2026", H_COLS.COL_HOURS_UNIT: "H1", H_COLS.COL_HOURS_OPERATING: "9"}),
            self._row(12, {H_COLS.COL_HOURS_DATE: "invalid", H_COLS.COL_HOURS_UNIT: "H2", H_COLS.COL_HOURS_OPERATING: "bad"}),
        ]
        manager = Mock()
        manager.get_all_values_cached.return_value = rows
        service = SongHinhHoursService(manager)

        result = service.get_hours_data(datetime(2026, 6, 12), object())

        self.assertEqual(result["total_hours_ytd"], "5.50")
        self.assertEqual(result["units"][0]["ytd"], "5.50")
        self.assertEqual(result["units"][0]["hours_stopped"], "20.5")

    def test_songhinh_hours_handles_empty_short_missing_and_exception(self):
        service = SongHinhHoursService(Mock())
        self.assertEqual(service.get_hours_data(datetime(2026, 1, 1), None)["units"], [])
        service.mgr.get_all_values_cached.return_value = [["header"]]
        self.assertEqual(service.get_hours_data(datetime(2026, 1, 1), object())["units"], [])
        service.mgr.get_all_values_cached.side_effect = RuntimeError("offline")
        self.assertEqual(service.get_hours_data(datetime(2026, 1, 1), object())["units"], [])

    def test_vinhson_hours_filters_units_and_accumulates_ytd(self):
        size = max(COL_HOURS_DATE, COL_HOURS_UNIT, COL_HOURS_OPERATING, COL_HOURS_STOPPED) + 1
        rows = [
            ["header"],
            ["header"],
            self._row(size, {COL_HOURS_DATE: "01/01/2026", COL_HOURS_UNIT: "H1", COL_HOURS_OPERATING: "2"}),
            self._row(size, {COL_HOURS_DATE: "12/06/2026", COL_HOURS_UNIT: "H1", COL_HOURS_OPERATING: "3,5", COL_HOURS_STOPPED: "20,5"}),
            self._row(size, {COL_HOURS_DATE: "12/06/2026", COL_HOURS_UNIT: "H3", COL_HOURS_OPERATING: "7", COL_HOURS_STOPPED: "17"}),
            self._row(size, {COL_HOURS_DATE: "invalid", COL_HOURS_UNIT: "H2", COL_HOURS_OPERATING: "bad"}),
        ]
        worksheet = Mock()
        worksheet.get_all_values.return_value = rows
        service = VinhSonHoursService(Mock())

        result = service.get_hours_data(datetime(2026, 6, 12), "Vinh Son -A", worksheet)

        self.assertEqual(result["total_hours_ytd"], "5.50")
        self.assertEqual([unit["unit"] for unit in result["units"]], ["H1"])

    def test_vinhson_hours_handles_reservoir_variants_and_errors(self):
        size = max(COL_HOURS_DATE, COL_HOURS_UNIT, COL_HOURS_OPERATING, COL_HOURS_STOPPED) + 1
        row = self._row(size, {COL_HOURS_DATE: "12/06/2026", COL_HOURS_UNIT: "H3", COL_HOURS_OPERATING: "1", COL_HOURS_STOPPED: "23"})
        worksheet = Mock()
        worksheet.get_all_values.return_value = [["h"], ["h"], row]
        service = VinhSonHoursService(Mock())
        self.assertEqual(service.get_hours_data(datetime(2026, 6, 12), "Vinh Son -B", worksheet)["units"][0]["unit"], "H3")
        self.assertEqual(service.get_hours_data(datetime(2026, 6, 12), "Vinh Son -C", worksheet)["units"][0]["unit"], "H3")
        self.assertEqual(service.get_hours_data(datetime(2026, 6, 12), "All", worksheet)["units"][0]["unit"], "H3")
        self.assertEqual(service.get_hours_data(datetime(2026, 6, 12), "unknown", worksheet)["units"], [])
        self.assertEqual(service.get_hours_data(datetime(2026, 6, 12), "All", None)["units"], [])
        worksheet.get_all_values.side_effect = RuntimeError("offline")
        self.assertEqual(service.get_hours_data(datetime(2026, 6, 12), "All", worksheet)["units"], [])


class PlantToolHandlerTests(SimpleTestCase):
    def test_songhinh_handler_dispatches_every_tool_and_unknown(self):
        from ai_tools.songhinh_tools.openai import tool_handler as handler

        patches = {
            "_operational_service": Mock(get_operational_data=Mock(return_value="ok")),
            "_comparative_service": Mock(get_comparative_analysis=Mock(return_value="ok")),
            "_qve_analysis_service": Mock(get_qve_analysis=Mock(return_value="ok")),
            "_hierarchical_service": Mock(get_hierarchical_statistics=Mock(return_value="ok")),
            "_rainfall_service": Mock(
                get_rainfall_statistics=Mock(return_value="ok"),
                get_rainfall_range_statistics=Mock(return_value="ok"),
                get_rainfall_daily_statistics=Mock(return_value="ok"),
            ),
            "_forecast_service": Mock(forecast_month=Mock(return_value="ok")),
        }
        calls = (
            ("get_songinh_operational_data", {}),
            ("get_songhinh_comparative_analysis", {}),
            ("get_songhinh_qve_analysis", {}),
            ("get_songhinh_hierarchical_statistics", {}),
            ("get_songhinh_rainfall_statistics", {}),
            ("get_songhinh_rainfall_range_statistics", {}),
            ("get_songhinh_rainfall_daily_statistics", {}),
            ("get_songhinh_forecast", {"target_month": 6, "target_year": 2026}),
            ("get_songhinh_forecast", {"target_year": 2026}),
            ("unknown", {}),
        )
        with patch.multiple(handler, **patches):
            for name, arguments in calls:
                with self.subTest(name=name, arguments=arguments):
                    response = handler.handle_songhinh_tool_calls(_tool_call(name, arguments))
                    self.assertEqual(response["role"], "tool")
                    self.assertEqual(response["tool_call_id"], f"call-{name}")

    def test_vinhson_handler_dispatches_every_tool_and_unknown(self):
        from ai_tools.vinhson_tools.openai import tool_handler as handler

        patches = {
            "_operational_service": Mock(get_operational_data=Mock(return_value="ok")),
            "_comparative_service": Mock(get_comparative_analysis=Mock(return_value="ok")),
            "_qve_analysis_service": Mock(get_qve_analysis=Mock(return_value="ok")),
            "_hierarchical_service": Mock(get_hierarchical_statistics=Mock(return_value="ok")),
            "_rainfall_service": Mock(
                get_rainfall_statistics=Mock(return_value="ok"),
                get_rainfall_range_statistics=Mock(return_value="ok"),
                get_rainfall_daily_statistics=Mock(return_value="ok"),
            ),
            "_forecast_service": Mock(forecast_month=Mock(return_value="ok"), forecast_year=Mock(return_value="ok")),
        }
        calls = (
            ("get_vinhson_operational_data", {}),
            ("get_vinhson_comparative_analysis", {}),
            ("get_vinhson_qve_analysis", {}),
            ("get_vinhson_hierarchical_statistics", {}),
            ("get_vinhson_rainfall_statistics", {}),
            ("get_vinhson_rainfall_range_statistics", {}),
            ("get_vinhson_rainfall_daily_statistics", {}),
            ("get_vinhson_forecast", {"target_month": 6, "target_year": 2026}),
            ("get_vinhson_forecast", {"target_year": 2026}),
            ("unknown", {}),
        )
        with patch.multiple(handler, **patches):
            for name, arguments in calls:
                with self.subTest(name=name, arguments=arguments):
                    response = handler.handle_vinhson_tool_calls(_tool_call(name, arguments))
                    self.assertEqual(response["role"], "tool")
                    self.assertEqual(response["tool_call_id"], f"call-{name}")
