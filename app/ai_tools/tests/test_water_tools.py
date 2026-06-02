from django.test import SimpleTestCase
from unittest.mock import patch

from ai_tools.water_tools.core.interpolation import interpolate_water_level_from_volume
from ai_tools.water_tools.core.spillway import create_detailed_spillway_schedule
from ai_tools.water_tools.core.flow import calculate_flow_rate

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

