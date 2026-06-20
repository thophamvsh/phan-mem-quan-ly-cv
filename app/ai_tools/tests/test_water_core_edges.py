import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from ai_tools.water_tools.core.flow import calculate_flow_rate, calculate_level_change, calculate_time_needed
from ai_tools.water_tools.core.interpolation import interpolate_water_level_from_volume
from ai_tools.water_tools.core.volume import (
    calculate_volume_difference,
    get_flood_control_volume,
    get_useful_volume,
    get_water_volume,
)
from ai_tools.water_tools.runtime.handler import handle_tool_calls, handle_water_tool_call


def _volume_result(level, volume, method="exact"):
    return {
        "H": level,
        "V": volume,
        "H1": level - 1,
        "V1": volume - 1,
        "H2": level + 1,
        "V2": volume + 1,
        "method": method,
    }


class WaterVolumeEdgeTests(SimpleTestCase):
    @patch("ai_tools.water_tools.core.volume.interpolate_water_volume")
    def test_water_volume_formats_all_interpolation_methods(self, interpolate):
        for method in ("exact", "interpolated", "nearest"):
            with self.subTest(method=method):
                interpolate.return_value = _volume_result(200, 100, method)
                report = get_water_volume(200)
                self.assertIn("100", report)
                self.assertNotIn("Error querying", report)

    @patch("ai_tools.water_tools.core.volume.interpolate_water_volume", return_value=None)
    def test_water_volume_handles_missing_data(self, _interpolate):
        self.assertIn("database", get_water_volume(200))

    def test_water_volume_handles_invalid_level(self):
        self.assertIn("Error querying", get_water_volume("invalid"))

    @patch("ai_tools.water_tools.core.volume.interpolate_water_volume")
    def test_flood_control_volume_success_and_missing_points(self, interpolate):
        interpolate.side_effect = [{"V": 80}, {"V": 100}]
        self.assertIn("20.000", get_flood_control_volume(208))

        interpolate.side_effect = [None, {"V": 100}]
        self.assertIn("208", get_flood_control_volume(208))

        interpolate.side_effect = [{"V": 80}, None]
        self.assertIn("209.0", get_flood_control_volume(208))

    @patch("ai_tools.water_tools.core.volume.interpolate_water_volume")
    def test_useful_volume_success_and_missing_points(self, interpolate):
        interpolate.side_effect = [{"V": 10}, {"V": 30}]
        self.assertIn("20.000", get_useful_volume())

        interpolate.side_effect = [None, {"V": 30}]
        self.assertIn("196.0", get_useful_volume())

        interpolate.side_effect = [{"V": 10}, None]
        self.assertIn("209.0", get_useful_volume())

    def test_volume_helpers_reject_unknown_reservoir(self):
        self.assertIn("Unknown", get_flood_control_volume(100, "Unknown"))
        self.assertIn("Unknown", get_useful_volume("Unknown"))

    @patch("ai_tools.water_tools.core.volume.interpolate_water_volume")
    def test_volume_difference_covers_increase_decrease_and_missing_data(self, interpolate):
        interpolate.side_effect = [_volume_result(1, 10), _volume_result(2, 13)]
        self.assertIn("3.000", calculate_volume_difference(1, 2))

        interpolate.side_effect = [_volume_result(2, 13), _volume_result(1, 10)]
        self.assertIn("3.000", calculate_volume_difference(2, 1))

        interpolate.side_effect = [None, _volume_result(2, 13)]
        self.assertIn("1.0", calculate_volume_difference(1, 2))

        interpolate.side_effect = [_volume_result(1, 10), None]
        self.assertIn("2.0", calculate_volume_difference(1, 2))

    def test_volume_difference_handles_invalid_input(self):
        self.assertIn("invalid", calculate_volume_difference("invalid", 2))


class WaterFlowEdgeTests(SimpleTestCase):
    @patch("ai_tools.water_tools.core.flow.interpolate_water_volume")
    def test_time_needed_validates_data_flow_and_direction(self, interpolate):
        interpolate.side_effect = [None, None]
        self.assertIn("d", calculate_time_needed(1, 2, 10, 0))

        interpolate.side_effect = [_volume_result(1, 10), _volume_result(2, 12)]
        self.assertIn("0", calculate_time_needed(1, 2, 10, 10))

        interpolate.side_effect = [_volume_result(1, 10), _volume_result(2, 12)]
        self.assertIn("kh", calculate_time_needed(1, 2, 0, 10))

    @patch("ai_tools.water_tools.core.flow.interpolate_water_volume")
    def test_time_needed_formats_hours_and_days(self, interpolate):
        interpolate.side_effect = [_volume_result(1, 10), _volume_result(2, 10.036)]
        self.assertIn("1.0", calculate_time_needed(1, 2, 10, 0))

        interpolate.side_effect = [_volume_result(1, 10), _volume_result(2, 10.864)]
        self.assertIn("1.00", calculate_time_needed(1, 2, 10, 0))

    def test_time_needed_handles_invalid_input(self):
        self.assertIn("invalid", calculate_time_needed("invalid", 2))

    @patch("ai_tools.water_tools.core.flow.interpolate_water_level_from_volume")
    @patch("ai_tools.water_tools.core.flow.interpolate_water_volume")
    def test_level_change_covers_missing_negative_and_unresolvable_volume(self, interpolate, inverse):
        interpolate.return_value = None
        self.assertIn("1.0", calculate_level_change(1, 2, 1, 1))

        interpolate.return_value = {"V": 0.1}
        self.assertIn("m", calculate_level_change(0, 100, 1, 1))

        interpolate.return_value = {"V": 10}
        inverse.return_value = None
        self.assertIn("9.914", calculate_level_change(1, 2, 1, 1))

    @patch("ai_tools.water_tools.core.flow.interpolate_water_level_from_volume")
    @patch("ai_tools.water_tools.core.flow.interpolate_water_volume", return_value={"V": 10})
    def test_level_change_covers_rising_falling_and_unchanged(self, _interpolate, inverse):
        inverse.return_value = 1.5
        self.assertIn("1.50", calculate_level_change(20, 10, 1, 1))

        inverse.return_value = 0.5
        self.assertIn("0.50", calculate_level_change(10, 20, 1, 1))

        inverse.return_value = 1
        self.assertIn("0.00", calculate_level_change(10, 10, 0, 1))

    def test_level_change_handles_invalid_input(self):
        self.assertIn("invalid", calculate_level_change("invalid", 1, 1, 1))

    @patch("ai_tools.water_tools.core.flow.interpolate_water_volume")
    def test_flow_rate_covers_missing_values_increase_decrease_and_discharge(self, interpolate):
        interpolate.side_effect = [None, _volume_result(2, 12)]
        self.assertIn("1.0", calculate_flow_rate(1, 2, 1))
        interpolate.side_effect = [_volume_result(1, 10), None]
        self.assertIn("2.0", calculate_flow_rate(1, 2, 1))
        interpolate.side_effect = [{"V": None}, _volume_result(2, 12)]
        self.assertIn("1.0", calculate_flow_rate(1, 2, 1))
        interpolate.side_effect = [_volume_result(1, 10), {"V": None}]
        self.assertIn("2.0", calculate_flow_rate(1, 2, 1))

        interpolate.side_effect = [_volume_result(1, 10), _volume_result(2, 12)]
        self.assertIn("23.15", calculate_flow_rate(1, 2, 1))
        interpolate.side_effect = [_volume_result(2, 12), _volume_result(1, 10)]
        self.assertIn("23.15", calculate_flow_rate(2, 1, 1))
        interpolate.side_effect = [_volume_result(1, 10), _volume_result(2, 12)]
        self.assertIn("33.15", calculate_flow_rate(1, 2, 1, discharge_rate=10))

    @patch("ai_tools.water_tools.core.flow.interpolate_water_volume", side_effect=[_volume_result(1, 10), _volume_result(2, 12)])
    def test_flow_rate_handles_zero_time_and_invalid_input(self, _interpolate):
        self.assertIn("zero", calculate_flow_rate(1, 2, 0).lower())
        self.assertIn("invalid", calculate_flow_rate("invalid", 2, 1))


class WaterInterpolationEdgeTests(SimpleTestCase):
    @patch("ai_tools.water_tools.core.interpolation.query_nearby_water_levels")
    def test_inverse_interpolation_handles_missing_exact_between_and_exception(self, query):
        query.return_value = []
        self.assertIsNone(interpolate_water_level_from_volume(10))

        query.return_value = [{"Mucnuoc": 100, "Dungtich": 10}]
        self.assertEqual(interpolate_water_level_from_volume(10), 100)

        query.return_value = [
            {"Mucnuoc": 100, "Dungtich": 10},
            {"Mucnuoc": 110, "Dungtich": 30},
        ]
        self.assertEqual(interpolate_water_level_from_volume(20), 105)

        query.side_effect = RuntimeError("offline")
        self.assertIsNone(interpolate_water_level_from_volume(20))


class WaterHandlerEdgeTests(SimpleTestCase):
    @staticmethod
    def _call(name, arguments=None, call_id="call-1"):
        return SimpleNamespace(
            id=call_id,
            function=SimpleNamespace(name=name, arguments=json.dumps(arguments or {})),
        )

    def test_single_handler_handles_unknown_tool(self):
        response = handle_water_tool_call(self._call("missing_tool"))
        self.assertEqual(response["tool_call_id"], "call-1")
        self.assertIn("Unknown water tool", response["content"])

    @patch.dict("ai_tools.water_tools.runtime.handler.TOOL_REGISTRY", {"broken": Mock(side_effect=ValueError("boom"))}, clear=True)
    def test_single_handler_converts_tool_exception_to_response(self):
        response = handle_water_tool_call(self._call("broken"))
        self.assertIn("boom", response["content"])

    @patch.dict("ai_tools.water_tools.runtime.handler.TOOL_REGISTRY", {"echo": Mock(return_value="ok")}, clear=True)
    def test_batch_handler_dispatches_success_unknown_and_error(self):
        message = SimpleNamespace(
            tool_calls=[
                self._call("echo", {"value": 1}, "one"),
                self._call("missing", call_id="two"),
            ]
        )
        responses = handle_tool_calls(message)
        self.assertEqual([item["tool_call_id"] for item in responses], ["one", "two"])
        self.assertIn("ok", responses[0]["content"])
        self.assertIn("Unknown tool", responses[1]["content"])
