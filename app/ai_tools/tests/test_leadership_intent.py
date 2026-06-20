from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase

from ai_tools.leadership_report import (
    expand_leadership_menu_choice,
    get_three_plant_production_report_date,
    has_leadership_event_menu_context,
    has_leadership_production_menu_context,
    has_leadership_rainfall_weather_menu_context,
    has_leadership_weekly_limit_menu_context,
    is_leadership_title,
    is_three_plant_yesterday_production_request,
    is_weekly_limit_report_request,
)
from ai_tools.leadership_report.services.intent_service import LEADERSHIP_REPORT_INDICATORS
from ai_tools.leadership_report.utils.text import normalize_text


class LeadershipIntentTests(SimpleTestCase):
    def setUp(self):
        self.history = [{"role": "assistant", "content": LEADERSHIP_REPORT_INDICATORS[0]}]

    def test_leadership_title_accepts_alias_and_prefixed_scope(self):
        self.assertTrue(is_leadership_title("PTGD"))
        self.assertTrue(is_leadership_title("Tong giam doc khoi san xuat"))
        self.assertFalse(is_leadership_title("Giam doc"))
        self.assertFalse(is_leadership_title(None))

    def test_menu_choices_accept_supported_variants_with_context(self):
        checks = (
            (has_leadership_production_menu_context, ("1", "01", "muc 1", "lua chon 1", "bao cao 1")),
            (has_leadership_rainfall_weather_menu_context, ("2", "02", "muc 2", "lua chon 2", "bao cao 2")),
            (has_leadership_weekly_limit_menu_context, ("3", "03", "muc 3", "lua chon 3", "bao cao 3")),
            (
                has_leadership_event_menu_context,
                ("4", "04", "muc 4", "lua chon 4", "bao cao 4", "thiet bi su kien"),
            ),
        )
        for checker, choices in checks:
            for choice in choices:
                with self.subTest(checker=checker.__name__, choice=choice):
                    self.assertTrue(checker(choice, self.history))

    def test_menu_choice_requires_matching_choice_and_assistant_context(self):
        user_only_history = [{"role": "user", "content": LEADERSHIP_REPORT_INDICATORS[0]}]
        self.assertFalse(has_leadership_production_menu_context("1", []))
        self.assertFalse(has_leadership_production_menu_context("1", user_only_history))
        self.assertFalse(has_leadership_production_menu_context("2", self.history))
        self.assertEqual(expand_leadership_menu_choice("1", []), "1")

    @patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 6, 13))
    def test_expand_production_choice_uses_yesterday(self, _localdate):
        expanded = expand_leadership_menu_choice("1", self.history)
        self.assertIn("12/06/2026", expanded)
        self.assertIn("Song Hinh", normalize_text(expanded).title())

    @patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 6, 13))
    def test_production_date_parser_supports_relative_short_and_two_digit_years(self, _localdate):
        cases = (
            ("bao cao san xuat 3 nha may ngay hom qua", date(2026, 6, 12)),
            ("bao cao san xuat 3 nha may ngay 11/6", date(2026, 6, 11)),
            ("bao cao san xuat 3 nha may ngay 11-6-26", date(2026, 6, 11)),
            ("bao cao san xuat Song Hinh Vinh Son Thuong Kon Tum ngay 10/6/2026", date(2026, 6, 10)),
        )
        for content, expected in cases:
            with self.subTest(content=content):
                self.assertEqual(get_three_plant_production_report_date(content), expected)
                self.assertTrue(is_three_plant_yesterday_production_request(content))

    def test_production_date_parser_rejects_invalid_or_incomplete_requests(self):
        for content in ("", "bao cao san xuat ngay 11/6/2026", "bao cao 3 nha may ngay 11/6/2026", "bao cao san xuat 3 nha may ngay 31/2/2026"):
            with self.subTest(content=content):
                self.assertIsNone(get_three_plant_production_report_date(content) or None)
                self.assertFalse(is_three_plant_yesterday_production_request(content))

    def test_weekly_limit_intent_accepts_synonyms_and_rejects_partial_text(self):
        for content in (
            "bao cao muc nuoc gioi han tuan",
            "phan tich MNGH tuan",
            "danh gia gioi han tuan muc nuoc",
        ):
            with self.subTest(content=content):
                self.assertTrue(is_weekly_limit_report_request(content))

        for content in ("", "muc nuoc gioi han tuan", "bao cao muc nuoc"):
            with self.subTest(content=content):
                self.assertFalse(is_weekly_limit_report_request(content))
