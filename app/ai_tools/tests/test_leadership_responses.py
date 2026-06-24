from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from ai_tools.leadership_report.services import response_service


class LeadershipResponseTests(SimpleTestCase):
    def test_services_package_exports_event_report_api(self):
        from ai_tools.leadership_report import services

        self.assertIs(services.event_report_response, response_service.event_report_response)
        self.assertTrue(callable(services.build_leadership_event_report))
        self.assertTrue(callable(services.has_leadership_event_menu_context))
        self.assertIs(services.actual_water_level_report_response, response_service.actual_water_level_report_response)
        self.assertTrue(callable(services.build_leadership_actual_water_level_report))

    def _assert_response_contract(self, function, builder_name, choice, source_key, **extra):
        user = Mock(name="user")
        report_date = extra.get("report_date")
        with (
            patch.object(response_service, builder_name, return_value="REPORT") as builder,
            patch.object(response_service, "save_exchange") as save_exchange,
            patch.object(response_service.time, "time", return_value=100.125),
        ):
            response = function(
                user=user,
                session_id="session-1",
                content="request",
                provider="openai",
                selected_model="model-x",
                start_time=100.0,
                source="menu",
                **extra,
            )

        if report_date is None:
            builder.assert_called_once_with()
        else:
            builder.assert_called_once_with(report_date)
        self.assertEqual(
            response,
            {
                "session_id": "session-1",
                "response": "REPORT",
                "provider": "openai",
                "model": "model-x",
                "total_tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": 125,
                "tools_called": 0,
            },
        )
        saved = save_exchange.call_args.kwargs
        self.assertIs(saved["user"], user)
        self.assertEqual(saved["assistant_message"], "REPORT")
        self.assertEqual(saved["latency_ms"], 125)
        self.assertEqual(saved["meta"]["leadership_menu_choice"], choice)
        self.assertEqual(saved["meta"][source_key], "menu")
        self.assertEqual(saved["meta"]["provider"], "openai")
        return saved

    def test_production_response_persists_report_date_metadata(self):
        report_date = date(2026, 6, 12)
        saved = self._assert_response_contract(
            response_service.production_report_response,
            "build_leadership_production_report",
            "production_report",
            "production_report_source",
            report_date=report_date,
        )
        self.assertEqual(saved["meta"]["report_date"], "2026-06-12")

    def test_rainfall_weather_response_contract(self):
        self._assert_response_contract(
            response_service.rainfall_weather_report_response,
            "build_leadership_rainfall_weather_report",
            "rainfall_weather_report",
            "rainfall_weather_report_source",
        )

    def test_weekly_limit_response_contract(self):
        self._assert_response_contract(
            response_service.weekly_limit_report_response,
            "build_leadership_weekly_limit_report",
            "weekly_limit_report",
            "weekly_limit_report_source",
        )

    def test_event_response_contract(self):
        self._assert_response_contract(
            response_service.event_report_response,
            "build_leadership_event_report",
            "event_report",
            "event_report_source",
        )

    def test_event_statistics_response_asks_for_time_when_missing(self):
        user = Mock(name="user")
        request = SimpleNamespace(
            plant_code="SH",
            plant_name="Sông Hinh",
            start_date=None,
            end_date=None,
            all_time=False,
            include_details=False,
            needs_time_clarification=True,
        )
        with (
            patch.object(response_service, "build_leadership_event_statistics_report") as builder,
            patch.object(response_service, "save_exchange") as save_exchange,
            patch.object(response_service.time, "time", return_value=100.125),
        ):
            response = response_service.event_statistics_response(
                user=user,
                session_id="session-1",
                content="thong ke su kien Song Hinh",
                provider="openai",
                selected_model="model-x",
                start_time=100.0,
                source="direct",
                request=request,
            )

        builder.assert_not_called()
        self.assertIn("Sông Hinh", response["response"])
        self.assertIn("thời gian nào", response["response"])
        self.assertIn("tất cả", response["response"])
        saved = save_exchange.call_args.kwargs
        self.assertEqual(saved["assistant_message"], response["response"])
        self.assertEqual(saved["meta"]["leadership_menu_choice"], "event_statistics")
        self.assertEqual(saved["meta"]["plant_code"], "SH")
        self.assertTrue(saved["meta"]["needs_time_clarification"])

    def test_event_statistics_response_builds_report_when_time_is_present(self):
        user = Mock(name="user")
        request = SimpleNamespace(
            plant_code="VS",
            plant_name="Vĩnh Sơn",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            all_time=False,
            include_details=True,
            needs_time_clarification=False,
        )
        with (
            patch.object(response_service, "build_leadership_event_statistics_report", return_value="REPORT") as builder,
            patch.object(response_service, "save_exchange") as save_exchange,
            patch.object(response_service.time, "time", return_value=100.125),
        ):
            response = response_service.event_statistics_response(
                user=user,
                session_id="session-1",
                content="thong ke su kien Vinh Son thang 6/2026 xem chi tiet",
                provider="openai",
                selected_model="model-x",
                start_time=100.0,
                source="direct",
                request=request,
            )

        builder.assert_called_once_with(
            plant_code="VS",
            plant_name="Vĩnh Sơn",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            all_time=False,
            include_details=True,
        )
        self.assertEqual(response["response"], "REPORT")
        saved = save_exchange.call_args.kwargs
        self.assertEqual(saved["meta"]["leadership_menu_choice"], "event_statistics")
        self.assertEqual(saved["meta"]["event_statistics_source"], "direct")
        self.assertEqual(saved["meta"]["plant_code"], "VS")
        self.assertEqual(saved["meta"]["start_date"], "2026-06-01")
        self.assertEqual(saved["meta"]["end_date"], "2026-06-30")
        self.assertFalse(saved["meta"]["all_time"])

    def test_actual_water_level_response_asks_for_time_when_missing(self):
        user = Mock(name="user")
        request = SimpleNamespace(
            start_date=None,
            end_date=None,
            needs_time_clarification=True,
        )
        with (
            patch.object(response_service, "build_leadership_actual_water_level_report") as builder,
            patch.object(response_service, "save_exchange") as save_exchange,
            patch.object(response_service.time, "time", return_value=100.125),
        ):
            response = response_service.actual_water_level_report_response(
                user=user,
                session_id="session-1",
                content="bao cao muc nuoc ho thuc te",
                provider="openai",
                selected_model="model-x",
                start_time=100.0,
                source="direct",
                request=request,
            )

        builder.assert_not_called()
        self.assertIn("mực nước/Qve thực tế", response["response"])
        self.assertIn("khoảng thời gian nào", response["response"])
        saved = save_exchange.call_args.kwargs
        self.assertEqual(saved["meta"]["leadership_menu_choice"], "actual_water_level_report")
        self.assertTrue(saved["meta"]["needs_time_clarification"])

    def test_actual_water_level_response_builds_report_when_time_is_present(self):
        user = Mock(name="user")
        request = SimpleNamespace(
            start_date=date(2026, 6, 23),
            end_date=date(2026, 6, 23),
            plant_codes=("songhinh",),
            needs_time_clarification=False,
        )
        with (
            patch.object(response_service, "build_leadership_actual_water_level_report", return_value="REPORT") as builder,
            patch.object(response_service, "save_exchange") as save_exchange,
            patch.object(response_service.time, "time", return_value=100.125),
        ):
            response = response_service.actual_water_level_report_response(
                user=user,
                session_id="session-1",
                content="phan tich chenh lech MNH ngay 23/6/2026",
                provider="openai",
                selected_model="model-x",
                start_time=100.0,
                source="direct",
                request=request,
            )

        builder.assert_called_once_with(
            date(2026, 6, 23),
            date(2026, 6, 23),
            plant_codes=("songhinh",),
            compare_reported=False,
        )
        self.assertEqual(response["response"], "REPORT")
        saved = save_exchange.call_args.kwargs
        self.assertEqual(saved["meta"]["actual_water_level_source"], "direct")
        self.assertEqual(saved["meta"]["start_date"], "2026-06-23")
        self.assertEqual(saved["meta"]["end_date"], "2026-06-23")
        self.assertEqual(saved["meta"]["plant_codes"], "songhinh")
        self.assertFalse(saved["meta"]["compare_reported"])
