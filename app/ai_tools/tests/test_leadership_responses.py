from datetime import date
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from ai_tools.leadership_report.services import response_service


class LeadershipResponseTests(SimpleTestCase):
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
