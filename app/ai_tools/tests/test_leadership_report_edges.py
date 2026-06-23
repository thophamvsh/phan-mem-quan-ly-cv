from datetime import date, datetime, timezone
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from ai_tools.leadership_report import build_leadership_event_report, build_leadership_production_report
from ai_tools.leadership_report.services.report_service import (
    _fetch_weather_forecast,
    _forecast_weekly_limit_status,
    _current_weekly_limit_status,
    _operating_level_by_capacity,
    _weather_forecast_rows,
)
from khovattu.models import Bang_nha_may
from nhatkyvanhanh.models import KhacPhucSuKien, SuKien
from thongsothuyvan.models import ThongSoThuyVanCaiDat, ThongsoSanxuat


class LeadershipWeatherEdgeTests(SimpleTestCase):
    @patch("ai_tools.leadership_report.services.report_service.requests.get")
    def test_fetch_weather_forecast_handles_partial_daily_arrays(self, get):
        response = Mock()
        response.json.return_value = {
            "daily": {
                "time": ["2026-06-14", "2026-06-15"],
                "weather_code": [61],
                "temperature_2m_max": [31.5, 32.0],
                "temperature_2m_min": [],
                "precipitation_sum": [12.0],
            }
        }
        get.return_value = response

        forecasts = _fetch_weather_forecast({"latitude": 1, "longitude": 2})

        response.raise_for_status.assert_called_once_with()
        self.assertEqual(len(forecasts), 2)
        self.assertEqual(forecasts[0]["weather_code"], 61)
        self.assertIsNone(forecasts[0]["temperature_min"])
        self.assertIsNone(forecasts[1]["weather_code"])
        self.assertIsNone(forecasts[1]["precipitation_probability"])

    def test_weather_rows_report_api_error_and_empty_forecast(self):
        locations = (
            {"name": "Error Plant", "latitude": 1, "longitude": 2},
            {"name": "Empty Plant", "latitude": 3, "longitude": 4},
        )
        with (
            patch("ai_tools.leadership_report.services.report_service.LEADERSHIP_WEATHER_LOCATIONS", locations),
            patch(
                "ai_tools.leadership_report.services.report_service._fetch_weather_forecast",
                side_effect=[RuntimeError("network error"), []],
            ),
        ):
            rows = _weather_forecast_rows()

        self.assertIn("Error Plant", rows[0])
        self.assertIn("- | - | - | - |", rows[0])
        self.assertIn("Empty Plant", rows[1])
        self.assertIn("- | - | - | - |", rows[1])

    def test_weekly_status_covers_missing_above_below_and_equal(self):
        self.assertIn("Ch", _current_weekly_limit_status(None, 10))
        self.assertIn("cao", _current_weekly_limit_status(11, 10))
        self.assertIn("th", _current_weekly_limit_status(9, 10))
        self.assertIn("b", _current_weekly_limit_status(10, 10))
        self.assertIn("Ch", _forecast_weekly_limit_status(None, 10))
        self.assertIn("cao", _forecast_weekly_limit_status(11, 10))
        self.assertIn("th", _forecast_weekly_limit_status(9, 10))
        self.assertIn("b", _forecast_weekly_limit_status(10, 10))

    @patch("thongsothuyvan.hydrology_services.get_capacity_by_reservoir_level", return_value=10)
    @patch("thongsothuyvan.hydrology_services.get_capacity_points_for_reservoir")
    def test_operating_level_by_capacity_handles_missing_bounds_and_interpolation(self, points, _capacity):
        points.return_value = []
        self.assertIsNone(_operating_level_by_capacity("lake", 10))

        points.return_value = [(100, 10), (110, 30)]
        self.assertEqual(_operating_level_by_capacity("lake", -5), 100)
        self.assertEqual(_operating_level_by_capacity("lake", 30), 110)
        self.assertEqual(_operating_level_by_capacity("lake", 10), 105)
        self.assertIsNone(_operating_level_by_capacity("lake", None))


class LeadershipProductionFallbackTests(TestCase):
    databases = {"default"}

    def test_production_report_prefers_settings_then_uses_record_fallbacks(self):
        report_date = date(2026, 6, 12)
        report_time = datetime(2026, 6, 12, 7, tzinfo=timezone.utc)
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=6,
            sanluong_kehoach_thang=120,
        )
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
            sanluong_kehoach_nam=1200,
        )
        ThongsoSanxuat.objects.create(
            nha_may="songhinh",
            thoi_gian=report_time,
            cot_n=10,
            cot_l=20,
            cot_r=30,
            sanluong_kh_thang=999,
            cot_p=888,
            cot_v=300,
            cot_w=777,
            cot_t=666,
        )
        ThongsoSanxuat.objects.create(
            nha_may="vinhson",
            thoi_gian=report_time,
            cot_n=5,
            cot_l=10,
            cot_r=25,
            sanluong_kh_thang=50,
            cot_v=100,
            cot_w=None,
            cot_t=400,
        )

        report = build_leadership_production_report(report_date)

        self.assertIn("| S", report)
        self.assertIn("| 10 | 20 | 50.00% | 30 | 120 | 25.00% | 300 | 1.200 | 25.00% |", report)
        self.assertIn("| 5 | 10 | 50.00% | 25 | 50 | 50.00% | 100 | 400 | 25.00% |", report)
        self.assertIn("Kh", report)  # Thuong Kon Tum has no operating record.


class LeadershipEventEdgeTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.plant = Bang_nha_may.objects.create(ma_nha_may="SH", ten_nha_may="Song Hinh")
        self.user = get_user_model().objects.create_user(
            username="event-user",
            email="event-user@example.com",
            password="testpass123",
        )

    def test_empty_event_report_uses_placeholder_row(self):
        report = build_leadership_event_report(date(2026, 6, 13))
        self.assertIn("| - | - | - | - | - | - | - | - |", report)
        self.assertIn("0 s", report)

    def test_old_resolved_event_is_excluded_and_long_pending_text_is_truncated(self):
        SuKien.objects.create(
            nha_may=self.plant,
            thoi_gian_xay_ra=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Old resolved device",
            hien_tuong_dien_bien="Old resolved event",
            trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
            ben_ghi_nhan_su_kien=self.user,
        )
        pending = SuKien.objects.create(
            nha_may=self.plant,
            thoi_gian_xay_ra=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="D" * 40,
            hien_tuong_dien_bien="H" * 60,
            chi_dao="C" * 50,
            trang_thai=SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
        )

        report = build_leadership_event_report(date(2026, 6, 13))

        self.assertNotIn("Old resolved device", report)
        self.assertIn("D" * 27 + "...", report)
        self.assertIn("H" * 47 + "...", report)
        self.assertIn("C" * 37 + "...", report)
        self.assertIn(f"event={pending.id}", report)

    def test_event_report_escapes_pending_markdown_cells(self):
        pending = SuKien.objects.create(
            nha_may=self.plant,
            thoi_gian_xay_ra=datetime(2026, 6, 13, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Pump | Line",
            hien_tuong_dien_bien="Leak | high\nneeds check",
            chi_dao="Check | isolate\r\nthen report",
            trang_thai=SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
        )

        report = build_leadership_event_report(date(2026, 6, 13))

        self.assertIn("Pump \\| Line", report)
        self.assertIn("Leak \\| high needs check", report)
        self.assertIn("Check \\| isolate then report", report)
        self.assertIn(f"event={pending.id}", report)

    def test_resolved_event_stats_use_latest_remediation_time(self):
        event = SuKien.objects.create(
            nha_may=self.plant,
            thoi_gian_xay_ra=datetime(2026, 6, 12, tzinfo=timezone.utc),
            ten_he_thong_thiet_bi="Resolved twice",
            hien_tuong_dien_bien="Resolved event",
            trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
            ben_ghi_nhan_su_kien=self.user,
        )
        KhacPhucSuKien.objects.create(
            su_kien=event,
            thoi_gian_xu_ly=datetime(2026, 6, 12, tzinfo=timezone.utc),
        )
        KhacPhucSuKien.objects.create(
            su_kien=event,
            thoi_gian_xu_ly=datetime(2026, 6, 20, tzinfo=timezone.utc),
        )

        report = build_leadership_event_report(date(2026, 6, 13))

        self.assertIn("0 sự kiện", report)
        self.assertNotIn("Resolved twice", report)
