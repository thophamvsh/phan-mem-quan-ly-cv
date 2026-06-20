from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from ai_tools.songhinh_tools.utils import dates as sh_dates
from ai_tools.songhinh_tools.utils import numbers as sh_numbers
from ai_tools.vinhson_tools.utils import dates as vs_dates
from ai_tools.vinhson_tools.utils import numbers as vs_numbers
from ai_tools.water_tools.weather_service import (
    generate_deterministic_daily_rain,
    get_daily_rainfall_history,
    get_initial_levels_and_volumes,
    get_monthly_rainfall,
    get_rainfall_forecast,
    get_reservoir_max_useful_capacity,
    get_reservoir_useful_capacity,
)
from thongsothuyvan.models import ThongsoSanxuat, TramDoMuaVrain


class DateUtilityTests(SimpleTestCase):
    def test_songhinh_date_parsers_cover_supported_and_invalid_formats(self):
        self.assertEqual(sh_dates.parse_dmy_to_date("1/2/2026"), date(2026, 2, 1))
        for value in (None, "", "2026-02-01", "31/2/2026"):
            self.assertIsNone(sh_dates.parse_dmy_to_date(value))

        self.assertEqual(sh_dates.normalize_date("1/2/2026"), date(2026, 2, 1))
        self.assertEqual(sh_dates.normalize_date("2026-02-01"), date(2026, 2, 1))
        self.assertIsNone(sh_dates.normalize_date("invalid"))

        self.assertEqual(sh_dates.parse_date("1/2/26"), datetime(2026, 2, 1))
        self.assertEqual(sh_dates.parse_date("1/2/76"), datetime(1976, 2, 1))
        self.assertEqual(sh_dates.parse_date("2026-02-01"), datetime(2026, 2, 1))
        self.assertIsNone(sh_dates.parse_date("invalid"))

    def test_vinhson_date_parsers_cover_supported_and_invalid_formats(self):
        self.assertEqual(vs_dates.normalize_date("1/2/2026"), date(2026, 2, 1))
        self.assertEqual(vs_dates.normalize_date("2026-02-01"), date(2026, 2, 1))
        self.assertIsNone(vs_dates.normalize_date("31/2/2026"))
        self.assertEqual(vs_dates.parse_date("1/2/26"), datetime(2026, 2, 1))
        self.assertEqual(vs_dates.parse_date("1/2/76"), datetime(1976, 2, 1))
        self.assertEqual(vs_dates.parse_date("2026-02-01"), datetime(2026, 2, 1))
        self.assertIsNone(vs_dates.parse_date(None))
        self.assertIsNone(vs_dates.parse_date("invalid"))


class NumberUtilityTests(SimpleTestCase):
    def test_songhinh_number_parsing_handles_locales_and_invalid_values(self):
        cases = {
            "1,234.56": 1234.56,
            "1.234,56": 1234.56,
            "470,000,000": 470000000.0,
            "208,957": 208.957,
            "12.5": 12.5,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(sh_numbers.parse_float_loose(raw), expected)
        for raw in (None, "", "-", "invalid"):
            self.assertIsNone(sh_numbers.parse_float_loose(raw))

        self.assertEqual(sh_numbers.parse_kwh_integer("4,710"), 4710)
        self.assertIsNone(sh_numbers.parse_kwh_integer("invalid"))
        self.assertEqual(sh_numbers.normalize_mnh_value(208957), 208.957)
        self.assertEqual(sh_numbers.normalize_mnh_value(999), 999)
        self.assertIsNone(sh_numbers.normalize_mnh_value(None))
        self.assertEqual(sh_numbers.fmt_pct(12.345), "12.35%")
        self.assertEqual(sh_numbers.safe_cell([" a "], 0), "a")
        self.assertEqual(sh_numbers.safe_cell([], 0, "missing"), "missing")

    def test_vinhson_number_parsing_handles_locales_stats_and_invalid_values(self):
        cases = {
            "1,234.56": 1234.56,
            "1.234,56": 1234.56,
            "470,000,000": 470000000.0,
            "340.000.000": 340000000.0,
            "12,34": 12.34,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(vs_numbers.parse_number(raw), expected)
        for raw in (None, "", "-", "invalid"):
            self.assertIsNone(vs_numbers.parse_number(raw))

        self.assertEqual(vs_numbers.parse_number_for_mnh("77.337"), 773.37)
        self.assertEqual(vs_numbers.parse_number_for_mnh(77337), 773.37)
        self.assertEqual(vs_numbers.parse_number_for_qve("12,34"), 12.34)
        self.assertEqual(vs_numbers.parse_kwh_integer("1.843"), 1843)
        self.assertIsNone(vs_numbers.parse_kwh_integer("invalid"))
        self.assertEqual(vs_numbers.safe_cell([" a "], 0), "a")
        self.assertEqual(vs_numbers.safe_cell([], -1, "missing"), "missing")


class WeatherUtilityTests(SimpleTestCase):
    @patch("ai_tools.water_tools.weather_service.requests.get")
    def test_rainfall_forecast_handles_success_http_error_and_exception(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {
            "daily": {"time": ["2026-06-01", "2026-06-02"], "precipitation_sum": [1.5, None]}
        }
        get.return_value = response
        self.assertEqual(get_rainfall_forecast(1, 2), {"2026-06-01": 1.5, "2026-06-02": 0.0})

        get.return_value = Mock(status_code=500)
        self.assertEqual(get_rainfall_forecast(1, 2), {})

        get.side_effect = RuntimeError("offline")
        self.assertEqual(get_rainfall_forecast(1, 2), {})

    @patch("thongsothuyvan.hydrology_services.get_capacity_by_reservoir_level")
    def test_useful_capacity_prefers_database_and_clamps_fallback(self, capacity):
        capacity.side_effect = [30, 10]
        self.assertEqual(get_reservoir_useful_capacity("songhinh", 200), 20)

        capacity.side_effect = [None, None]
        self.assertEqual(get_reservoir_useful_capacity("songhinh", 100), 0)
        capacity.side_effect = [None, None]
        self.assertEqual(get_reservoir_useful_capacity("songhinh", 999), 323)
        capacity.side_effect = [None, None]
        self.assertEqual(get_reservoir_useful_capacity("unknown", 1), 0)

    @patch("thongsothuyvan.hydrology_services.get_operating_capacity_range_for_reservoir")
    def test_max_useful_capacity_prefers_database_and_has_fallback(self, capacity_range):
        capacity_range.return_value = {"max": 12.5}
        self.assertEqual(get_reservoir_max_useful_capacity("vinhson_b"), 12.5)
        capacity_range.return_value = None
        self.assertEqual(get_reservoir_max_useful_capacity("vinhson_b"), 10)
        self.assertEqual(get_reservoir_max_useful_capacity("unknown"), 10)

    def test_deterministic_rain_is_stable_and_bounded(self):
        first = generate_deterministic_daily_rain(2026, 6, 1)
        self.assertEqual(first, generate_deterministic_daily_rain(2026, 6, 1))
        self.assertGreaterEqual(first, 0)
        self.assertLessEqual(first, 50)


class WeatherDatabaseTests(TestCase):
    databases = {"default"}

    @patch("ai_tools.water_tools.weather_service.get_reservoir_useful_capacity", side_effect=lambda key, level: level)
    def test_initial_levels_use_latest_prior_record_and_defaults(self, _capacity):
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=datetime(2026, 5, 31, tzinfo=timezone.utc),
            cot_g=771,
            mucnuoc_thuongluu_ho_b=821,
            mucnuoc_thuongluu_ho_c=None,
        )
        result = get_initial_levels_and_volumes("vinhson", 2026, 6)
        self.assertEqual(result["vinhson_a"], (771, 771))
        self.assertEqual(result["vinhson_b"], (821, 821))
        self.assertEqual(result["vinhson_c"], (976.0, 976.0))

        self.assertEqual(get_initial_levels_and_volumes("songhinh", 2026, 1)["songhinh"][0], 204.85)
        self.assertEqual(get_initial_levels_and_volumes("unknown", 2026, 1), {})

    @patch("ai_tools.water_tools.weather_service.generate_deterministic_daily_rain", return_value=1.0)
    def test_daily_and_monthly_rainfall_mix_database_with_fallback(self, generated):
        TramDoMuaVrain.objects.create(
            Thoi_gian=datetime(2026, 2, 1, tzinfo=timezone.utc),
            Xa_Ea_M_doan=2,
            UBND_xa_Song_Hinh=4,
        )
        daily = get_daily_rainfall_history("songhinh", 2026, 2)
        self.assertEqual(daily[1], 3)
        self.assertEqual(daily[2], 1)
        self.assertEqual(len(daily), 28)
        self.assertEqual(get_monthly_rainfall("songhinh", 2026, 2), 30)
        self.assertTrue(generated.called)
