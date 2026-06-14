import json
from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase
from unittest.mock import patch

from ai_tools.water_tools.core.interpolation import interpolate_water_level_from_volume
from ai_tools.water_tools.core.spillway import create_detailed_spillway_schedule
from ai_tools.water_tools.core.flow import calculate_flow_rate
from ai_tools.water_tools.core.weekly_limit import get_weekly_limit_levels
from ai_tools.water_tools.runtime.handler import handle_water_tool_call
from ai_tools.water_tools.tooldefs.registry import TOOL_REGISTRY
from ai_tools.water_tools.tooldefs.schemas import TOOLS
from thongsothuyvan.models import ThongSoThuyVanCaiDat

class WaterToolsTests(SimpleTestCase):
    databases = {"default"}

    @patch("ai_tools.water_tools.core.interpolation.query_nearby_water_levels")
    def test_interpolate_water_level_dynamic_slope(self, mock_query):
        # Setup candidates list where all elements are below target_volume=25.0 to trigger fallback estimation
        mock_query.return_value = [
            {"Mucnuoc": 768.0, "Dungtich": 20.0},
            {"Mucnuoc": 767.0, "Dungtich": 15.0},
        ]
        
        # Closest is (H=768.0, V=20.0)
        # dh = 1.0, dv = 5.0 -> slope = 5.0
        # volume_diff = 25.0 - 20.0 = 5.0
        # estimated_h = 768.0 + 5.0 / 5.0 = 769.0
        res = interpolate_water_level_from_volume(25.0, reservoir="Vĩnh Sơn A")
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res, 769.0)

    @patch("ai_tools.water_tools.core.interpolation.query_nearby_water_levels")
    def test_interpolate_water_level_fallback_default_vinhson(self, mock_query):
        # Test fallback to default when len(candidates) < 2
        mock_query.return_value = [
            {"Mucnuoc": 768.0, "Dungtich": 20.0},
        ]
        # closest = (768.0, 20.0)
        # len(candidates) = 1 -> slope defaults to 2.5 for Vĩnh Sơn
        # estimated_h = 768.0 + (25.0 - 20.0) / 2.5 = 770.0
        res = interpolate_water_level_from_volume(25.0, reservoir="Vĩnh Sơn A")
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res, 770.0)

    @patch("ai_tools.water_tools.core.spillway.interpolate_water_volume")
    def test_create_detailed_spillway_schedule_ramping_down(self, mock_interpolate):
        # Mock volumes for Sông Hinh levels
        mock_interpolate.side_effect = lambda level, res: (
            {"V": 300.0} if level == 209.0 else {"V": 277.0}
        )
        
        # Test detailed schedule for ramping down from 500 to 100
        # Check that Qxa decreases gradually (e.g. from 500 to 400 to 300 ...)
        # instead of jumping directly to 100
        report = create_detailed_spillway_schedule(
            start_discharge=500.0,
            end_discharge=100.0,
            time_days=1.0,
            cycle_hours=6.0,
            step_size=100.0,
            inflow_rate=100.0,
            turbine_discharge=50.0,
            start_level=209.0,
            end_level=208.0,
            reservoir="Sông Hinh"
        )
        
        # There should be 4 steps in 24 hours (cycle_hours=6)
        # Qxa step values: 500, 400, 300, 200
        self.assertIn("500", report)
        self.assertIn("400", report)
        self.assertIn("300", report)
        self.assertIn("200", report)
        self.assertIn("```chart", report)
        self.assertIn("Biểu đồ tiến trình lưu lượng vận hành qua các bước", report)
        self.assertIn("Biểu đồ tiến trình mực nước hồ dự kiến qua các bước", report)

    @patch("ai_tools.water_tools.core.flow.interpolate_water_volume")
    def test_calculate_flow_rate_physically_impossible(self, mock_interpolate):
        # Mock V(209) = 300, V(208) = 277
        mock_interpolate.side_effect = lambda level, res: (
            {"V": 300.0, "method": "exact"} if level == 209.0 else {"V": 277.0, "method": "exact"}
        )
        
        report = calculate_flow_rate(
            start_level=209.0,
            end_level=208.0,
            time_days=1.0,
            discharge_rate=10.0,
            reservoir="Sông Hinh"
        )
        
        # Should return warning message about physically impossible scenario
        self.assertIn("Không khả thi", report)
        self.assertIn("lưu lượng xả hiện tại (10.00 m³/s) là quá nhỏ", report)

    @patch("ai_tools.water_tools.core.spillway.interpolate_water_volume")
    def test_calculate_spillway_discharge_charts(self, mock_interpolate):
        mock_interpolate.side_effect = lambda level, res: (
            {"V": 300.0} if level == 209.0 else {"V": 277.0}
        )
        from ai_tools.water_tools.core.spillway import calculate_spillway_discharge
        report = calculate_spillway_discharge(
            start_level=209.0,
            end_level=208.0,
            time_days=1.0,
            inflow_rate=100.0,
            turbine_discharge=50.0,
            reservoir="Sông Hinh"
        )
        self.assertIn("```chart", report)
        self.assertIn("Cân bằng lưu lượng dự kiến", report)

    @patch("ai_tools.water_tools.core.spillway.interpolate_water_volume")
    def test_calculate_spillway_ramping_charts(self, mock_interpolate):
        mock_interpolate.side_effect = lambda level, res: (
            {"V": 300.0} if level == 209.0 else {"V": 277.0}
        )
        from ai_tools.water_tools.core.spillway import calculate_spillway_ramping
        report = calculate_spillway_ramping(
            start_level=209.0,
            end_level=208.0,
            time_days=1.0,
            inflow_rate=100.0,
            turbine_discharge=50.0,
            max_discharge=2000.0,
            reservoir="Sông Hinh"
        )
        self.assertIn("```chart", report)
        self.assertIn("So sánh lưu lượng xả giữa các phương án đề xuất", report)


class WeeklyLimitLevelsToolTests(TestCase):
    databases = {"default"}

    def setUp(self):
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=24,
            tuan_bat_dau=date(2026, 6, 8),
            tuan_ket_thuc=date(2026, 6, 14),
            mucnuoc_gioihan_tuan=205.5,
        )
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="vinhson",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=24,
            tuan_bat_dau=date(2026, 6, 8),
            tuan_ket_thuc=date(2026, 6, 14),
            mucnuoc_gioihan_tuan_ho_a=768.6,
            mucnuoc_gioihan_tuan_ho_b=822.0,
        )
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="thuongkontum",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=24,
            tuan_bat_dau=date(2026, 6, 8),
            tuan_ket_thuc=date(2026, 6, 14),
            mucnuoc_gioihan_tuan=1144.15,
        )
        ThongSoThuyVanCaiDat.objects.create(
            nha_may="songhinh",
            nam=2026,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan=25,
            tuan_bat_dau=date(2026, 6, 15),
            tuan_ket_thuc=date(2026, 6, 21),
            mucnuoc_gioihan_tuan=206.0,
        )

    def test_get_weekly_limit_levels_current_week_by_target_date(self):
        report = get_weekly_limit_levels(
            week_selector="current",
            reservoir="Sông Hinh",
            target_date="2026-06-13",
        )

        self.assertIn("**Kỳ tra cứu:** tuần này - tuần 24/2026", report)
        self.assertIn("| Sông Hinh | 24/2026 | 08/06/2026 - 14/06/2026 | 205,50 |", report)

    def test_get_weekly_limit_levels_next_week(self):
        report = get_weekly_limit_levels(
            week_selector="next",
            reservoir="Sông Hinh",
            target_date="2026-06-13",
        )

        self.assertIn("**Kỳ tra cứu:** tuần sau - tuần 25/2026", report)
        self.assertIn("| Sông Hinh | 25/2026 | 15/06/2026 - 21/06/2026 | 206,00 |", report)

    def test_get_weekly_limit_levels_specific_week_for_vinhson_returns_a_and_b_only(self):
        report = get_weekly_limit_levels(
            week_selector="specific",
            reservoir="Vĩnh Sơn",
            week_number=24,
            year=2026,
        )

        self.assertIn("| Vĩnh Sơn A | 24/2026 | 08/06/2026 - 14/06/2026 | 768,60 |", report)
        self.assertIn("| Vĩnh Sơn B | 24/2026 | 08/06/2026 - 14/06/2026 | 822,00 |", report)
        self.assertNotIn("Vĩnh Sơn C", report.split("**Ghi chú:**")[0])

    def test_weekly_limit_tool_registered_and_schema_exposed(self):
        self.assertIn("get_weekly_limit_levels", TOOL_REGISTRY)
        self.assertIn(
            "get_weekly_limit_levels",
            [tool["function"]["name"] for tool in TOOLS],
        )

    def test_handle_weekly_limit_tool_call(self):
        tool_call = SimpleNamespace(
            id="call_weekly_limit",
            function=SimpleNamespace(
                name="get_weekly_limit_levels",
                arguments=json.dumps(
                    {
                        "week_selector": "specific",
                        "reservoir": "TKT",
                        "week_number": 24,
                        "year": 2026,
                    },
                    ensure_ascii=False,
                ),
            ),
        )

        response = handle_water_tool_call(tool_call)

        self.assertEqual(response["role"], "tool")
        self.assertEqual(response["tool_call_id"], "call_weekly_limit")
        self.assertIn("| Thượng Kon Tum | 24/2026 | 08/06/2026 - 14/06/2026 | 1.144,15 |", response["content"])
