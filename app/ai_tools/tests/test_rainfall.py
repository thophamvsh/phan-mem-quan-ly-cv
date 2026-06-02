from unittest.mock import patch
from datetime import datetime, timezone
from django.test import TestCase

from ai_tools.songhinh_tools.services.rainfall_service import RainfallService as RainfallServiceSH
from ai_tools.vinhson_tools.services.rainfall_service import RainfallService as RainfallServiceVS

def _fake_query_rainfall_data(*args, **kwargs):
    # Trả về dữ liệu mưa giả lập cho năm 2025 và 2026 cho cả Sông Hinh và Vĩnh Sơn
    return [
        {
            "Thoi_gian": "2026-04-01",
            "UBND_xa_Song_Hinh": 10.0,
            "Xa_Ea_M_doan": 5.0,
            "Thon_10_Xa_Ea_M_Doal": 1.0,
            "Cu_Kroa": 2.0,
            "Dap_Tran": 3.0,
            "Xa_Ea_Trang": 4.0,
            "Ho_A_TD_Vinh_Son": 20.0,
            "Ho_B_TD_Vinh_Son": 15.0,
            "Ho_C_TD_Vinh_Son": 10.0,
        },
        {
            "Thoi_gian": "2026-04-02",
            "UBND_xa_Song_Hinh": 12.0,
            "Xa_Ea_M_doan": 6.0,
            "Thon_10_Xa_Ea_M_Doal": 0.0,
            "Cu_Kroa": 0.0,
            "Dap_Tran": 5.0,
            "Xa_Ea_Trang": 0.0,
            "Ho_A_TD_Vinh_Son": 22.0,
            "Ho_B_TD_Vinh_Son": 16.0,
            "Ho_C_TD_Vinh_Son": 11.0,
        },
        {
            "Thoi_gian": "2025-04-01",
            "UBND_xa_Song_Hinh": 8.0,
            "Xa_Ea_M_doan": 4.0,
            "Thon_10_Xa_Ea_M_Doal": 0.0,
            "Cu_Kroa": 0.0,
            "Dap_Tran": 4.0,
            "Xa_Ea_Trang": 0.0,
            "Ho_A_TD_Vinh_Son": 18.0,
            "Ho_B_TD_Vinh_Son": 14.0,
            "Ho_C_TD_Vinh_Son": 9.0,
        },
        {
            "Thoi_gian": "2025-04-02",
            "UBND_xa_Song_Hinh": 9.0,
            "Xa_Ea_M_doan": 4.5,
            "Thon_10_Xa_Ea_M_Doal": 0.0,
            "Cu_Kroa": 0.0,
            "Dap_Tran": 4.5,
            "Xa_Ea_Trang": 0.0,
            "Ho_A_TD_Vinh_Son": 19.0,
            "Ho_B_TD_Vinh_Son": 15.0,
            "Ho_C_TD_Vinh_Son": 10.0,
        },
    ]

class RainfallServicesTests(TestCase):
    databases = {"default"}

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_songhinh_rainfall_statistics_year(self, _mock_rain):
        service = RainfallServiceSH()
        report = service.get_rainfall_statistics(
            period_type="year",
            period_value="2026",
            compare_years=2
        )
        self.assertIn("S\u00f4ng Hinh", report)
        self.assertIn("2026", report)
        self.assertIn("2025", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_songhinh_rainfall_statistics_month(self, _mock_rain):
        service = RainfallServiceSH()
        report = service.get_rainfall_statistics(
            period_type="month",
            period_value="4/2026"
        )
        self.assertIn("S\u00f4ng Hinh", report)
        self.assertIn("4/2026", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)
        self.assertIn("B\u1ea3ng so s\u00e1nh c\u00e1c n\u0103m c\u00f9ng k\u1ef3", report)

        from ai_tools.tool_format import make_tool_response
        from ai_tools.songhinh_tools.openai.normalizer import get_normalizer
        resp = make_tool_response("get_songhinh_rainfall_statistics", report, get_normalizer("get_songhinh_rainfall_statistics"))
        self.assertIn("B\u1ea3ng so s\u00e1nh c\u00e1c n\u0103m c\u00f9ng k\u1ef3", resp["table"])
        self.assertNotIn("B\u1ea3ng so s\u00e1nh c\u00e1c n\u0103m c\u00f9ng k\u1ef3", resp["notes"])

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_songhinh_rainfall_statistics_week(self, _mock_rain):
        service = RainfallServiceSH()
        report = service.get_rainfall_statistics(
            period_type="week",
            period_value="1/4/2026"
        )
        self.assertIn("S\u00f4ng Hinh", report)
        self.assertIn("tu\u1ea7n 1", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_songhinh_rainfall_range_statistics(self, _mock_rain):
        service = RainfallServiceSH()
        report = service.get_rainfall_range_statistics(
            start_month=4,
            start_year=2026,
            end_month=4,
            end_year=2026
        )
        self.assertIn("S\u00f4ng Hinh", report)
        self.assertIn("4/2026", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_songhinh_rainfall_daily_statistics(self, _mock_rain):
        service = RainfallServiceSH()
        report = service.get_rainfall_daily_statistics(
            start_date="01/04/2026",
            end_date="02/04/2026"
        )
        self.assertIn("S\u00f4ng Hinh", report)
        self.assertIn("01/04/2026", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)

    # Vĩnh Sơn tests
    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_vinhson_rainfall_statistics_year(self, _mock_rain):
        service = RainfallServiceVS()
        report = service.get_rainfall_statistics(
            period_type="year",
            period_value="2026",
            compare_years=2
        )
        self.assertIn("V\u0129nh S\u01a1n", report)
        self.assertIn("2026", report)
        self.assertIn("2025", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_vinhson_rainfall_statistics_month(self, _mock_rain):
        service = RainfallServiceVS()
        report = service.get_rainfall_statistics(
            period_type="month",
            period_value="4/2026"
        )
        self.assertIn("V\u0129nh S\u01a1n", report)
        self.assertIn("4/2026", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)
        self.assertIn("B\u1ea3ng so s\u00e1nh c\u00e1c n\u0103m c\u00f9ng k\u1ef3", report)

        from ai_tools.tool_format import make_tool_response
        from ai_tools.vinhson_tools.openai.normalizer import get_normalizer
        # Vinh Son monthly uses get_vinhson_rainfall_statistics in tool handler, wait it uses the same as get_vinhson_rainfall_statistics
        resp = make_tool_response("get_vinhson_rainfall_statistics", report, None) # Use None for fallback to test _apply_fallback
        self.assertIn("B\u1ea3ng so s\u00e1nh c\u00e1c n\u0103m c\u00f9ng k\u1ef3", resp["table"])
        self.assertNotIn("B\u1ea3ng so s\u00e1nh c\u00e1c n\u0103m c\u00f9ng k\u1ef3", resp["notes"])

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_vinhson_rainfall_statistics_week(self, _mock_rain):
        service = RainfallServiceVS()
        report = service.get_rainfall_statistics(
            period_type="week",
            period_value="1/4/2026"
        )
        self.assertIn("V\u0129nh S\u01a1n", report)
        self.assertIn("tu\u1ea7n 1", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_vinhson_rainfall_range_statistics(self, _mock_rain):
        service = RainfallServiceVS()
        report = service.get_rainfall_range_statistics(
            start_month=4,
            start_year=2026,
            end_month=4,
            end_year=2026
        )
        self.assertIn("V\u0129nh S\u01a1n", report)
        self.assertIn("4/2026", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)

    @patch("thuyvan_data_client.query_rainfall_data", side_effect=_fake_query_rainfall_data)
    def test_vinhson_rainfall_daily_statistics(self, _mock_rain):
        service = RainfallServiceVS()
        report = service.get_rainfall_daily_statistics(
            start_date="01/04/2026",
            end_date="02/04/2026"
        )
        self.assertIn("V\u0129nh S\u01a1n", report)
        self.assertIn("01/04/2026", report)
        self.assertIn("```chart", report)
        self.assertIn("```excel", report)

    def test_filter_tool_calls_rainfall_both(self):
        from ai_tools.services import _filter_tool_calls

        class MockFunction:
            def __init__(self, name, arguments="{}"):
                self.name = name
                self.arguments = arguments

        class MockToolCall:
            def __init__(self, id, name, arguments="{}"):
                self.id = id
                self.function = MockFunction(name, arguments)

        # 1. Vinh Son: Test when user asks only for rainfall: should filter out get_vinhson_hierarchical_statistics
        calls_vs = [
            MockToolCall("1", "get_vinhson_rainfall_statistics", '{"period_type": "year", "period_value": "2025", "compare_years": 4}'),
            MockToolCall("2", "get_vinhson_hierarchical_statistics", '{"period_type": "year", "period_value": "2025", "compare": true, "compare_years": 4, "parameters": ["qve"]}')
        ]
        filtered_vs = _filter_tool_calls("So sánh lượng mưa hồ Vĩnh Sơn năm 2025 với 4 năm cùng kỳ", calls_vs)
        self.assertEqual(len(filtered_vs), 1)
        self.assertEqual(filtered_vs[0].function.name, "get_vinhson_rainfall_statistics")

        # 2. Vinh Son: Test when user asks for BOTH rainfall and Qve: should NOT filter out get_vinhson_hierarchical_statistics
        filtered_both_vs = _filter_tool_calls("So sánh lượng mưa và Qve hồ Vĩnh Sơn năm 2025 với 4 năm cùng kỳ", calls_vs)
        self.assertEqual(len(filtered_both_vs), 2)

        # 3. Song Hinh: Test when user asks only for rainfall: should filter out get_songhinh_hierarchical_statistics
        calls_sh = [
            MockToolCall("1", "get_songhinh_rainfall_statistics", '{"period_type": "year", "period_value": "2025", "compare_years": 4}'),
            MockToolCall("2", "get_songhinh_hierarchical_statistics", '{"period_type": "year", "period_value": "2025", "compare": true, "compare_years": 4, "parameters": ["qve"]}')
        ]
        filtered_sh = _filter_tool_calls("So sánh lượng mưa hồ Sông Hinh năm 2025 với 4 năm cùng kỳ", calls_sh)
        self.assertEqual(len(filtered_sh), 1)
        self.assertEqual(filtered_sh[0].function.name, "get_songhinh_rainfall_statistics")

        # 4. Song Hinh: Test when user asks for BOTH rainfall and Qve: should NOT filter out get_songhinh_hierarchical_statistics
        filtered_both_sh = _filter_tool_calls("So sánh lượng mưa và Qve hồ Sông Hinh năm 2025 với 4 năm cùng kỳ", calls_sh)
        self.assertEqual(len(filtered_both_sh), 2)
