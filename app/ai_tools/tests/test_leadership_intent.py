from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase

from ai_tools.leadership_report import (
    expand_leadership_menu_choice,
    get_actual_water_level_request,
    get_event_statistics_request,
    get_monthly_production_plan_request,
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

    @patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 7, 10))
    def test_monthly_production_plan_request_extracts_current_or_explicit_month(self, _localdate):
        current_month = get_monthly_production_plan_request("Sản lượng kế hoạch Qkh và Qc tháng này bao nhiêu?")
        self.assertEqual(current_month.year, 2026)
        self.assertEqual(current_month.month, 7)
        self.assertIsNone(current_month.plant_codes)
        self.assertFalse(current_month.needs_time_clarification)

        explicit_month = get_monthly_production_plan_request("Cho biết QKH và QC sản lượng Vĩnh Sơn tháng 6/2026")
        self.assertEqual(explicit_month.year, 2026)
        self.assertEqual(explicit_month.month, 6)
        self.assertEqual(explicit_month.plant_codes, ("vinhson",))
        self.assertFalse(explicit_month.needs_time_clarification)

        no_production_word = get_monthly_production_plan_request("Qkh và Qc tháng này của Sông Hinh?")
        self.assertEqual(no_production_word.year, 2026)
        self.assertEqual(no_production_word.month, 7)
        self.assertEqual(no_production_word.period, "month")
        self.assertEqual(no_production_word.plant_codes, ("songhinh",))
        self.assertFalse(no_production_word.needs_time_clarification)

        yearly = get_monthly_production_plan_request("Qc và Qkh năm 2026 của Sông Hinh?")
        self.assertEqual(yearly.year, 2026)
        self.assertEqual(yearly.month, 7)
        self.assertEqual(yearly.period, "year_to_date")
        self.assertEqual(yearly.plant_codes, ("songhinh",))

        ytd = get_monthly_production_plan_request("Qc, Qkh từ đầu năm đến giờ")
        self.assertEqual(ytd.year, 2026)
        self.assertEqual(ytd.month, 7)
        self.assertEqual(ytd.period, "year_to_date")

        missing_month = get_monthly_production_plan_request("Sản lượng kế hoạch Qkh và Qc bao nhiêu?")
        self.assertTrue(missing_month.needs_time_clarification)

    def test_monthly_production_plan_request_rejects_unrelated_production_questions(self):
        self.assertIsNone(get_monthly_production_plan_request("Báo cáo sản lượng hôm qua"))

    @patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 6, 24))
    def test_actual_water_level_request_requires_or_extracts_time(self, _localdate):
        missing_time = get_actual_water_level_request("bao cao muc nuoc ho thuc te")
        self.assertIsNone(missing_time.start_date)
        self.assertTrue(missing_time.needs_time_clarification)

        day_request = get_actual_water_level_request("phan tich chenh lech MNH thuc te va MNH bao cao ngay 23/6")
        self.assertEqual(day_request.start_date, date(2026, 6, 23))
        self.assertEqual(day_request.end_date, date(2026, 6, 23))
        self.assertTrue(day_request.compare_reported)
        self.assertFalse(day_request.needs_time_clarification)

        range_request = get_actual_water_level_request("thong ke muc nuoc thuc te 7 ngay gan nhat")
        self.assertEqual(range_request.start_date, date(2026, 6, 18))
        self.assertEqual(range_request.end_date, date(2026, 6, 24))
        self.assertFalse(range_request.compare_reported)
        self.assertFalse(range_request.needs_time_clarification)

        direct_request = get_actual_water_level_request(
            "Muc nuoc va Qve thuc te cua Song Hinh tu ngay 1/6 den 23/6/2026"
        )
        self.assertEqual(direct_request.start_date, date(2026, 6, 1))
        self.assertEqual(direct_request.end_date, date(2026, 6, 23))
        self.assertEqual(direct_request.plant_codes, ("songhinh",))
        self.assertFalse(direct_request.compare_reported)
        self.assertFalse(direct_request.needs_time_clarification)

        vietnamese_request = get_actual_water_level_request(
            "Thống kê Mực nước và Qve thực tế của Sông Hinh từ ngày 1/6 đến 23/6/2026"
        )
        self.assertEqual(vietnamese_request.start_date, date(2026, 6, 1))
        self.assertEqual(vietnamese_request.end_date, date(2026, 6, 23))
        self.assertEqual(vietnamese_request.plant_codes, ("songhinh",))
        self.assertFalse(vietnamese_request.compare_reported)
        self.assertFalse(vietnamese_request.needs_time_clarification)

        compare_request = get_actual_water_level_request(
            "So sanh Qve va MNH thuc te va bao cao cua Song Hinh tu ngay 1/6 den 23/6/2026"
        )
        self.assertEqual(compare_request.start_date, date(2026, 6, 1))
        self.assertEqual(compare_request.end_date, date(2026, 6, 23))
        self.assertEqual(compare_request.plant_codes, ("songhinh",))
        self.assertTrue(compare_request.compare_reported)

        no_actual_keyword = get_actual_water_level_request(
            "Muc nuoc va Qve cua Song Hinh tu ngay 1/6 den 23/6/2026"
        )
        self.assertIsNone(no_actual_keyword)

    def test_actual_water_level_request_uses_clarification_context(self):
        history = [
            {
                "role": "assistant",
                "content": (
                    "Anh/chị muốn phân tích mực nước hồ thực tế "
                    "và chênh lệch MNH báo cáo ngày nào hoặc trong khoảng thời gian nào?"
                ),
            }
        ]

        request = get_actual_water_level_request("ngay 23/6/2026", history)

        self.assertEqual(request.start_date, date(2026, 6, 23))
        self.assertEqual(request.end_date, date(2026, 6, 23))
        self.assertFalse(request.needs_time_clarification)

    @patch("ai_tools.leadership_report.services.intent_service.timezone.localdate", return_value=date(2026, 6, 13))
    def test_event_statistics_request_requires_or_extracts_time(self, _localdate):
        request = get_event_statistics_request("thong ke su kien Song Hinh thang 6/2026")
        self.assertEqual(request.plant_code, "SH")
        self.assertEqual(request.start_date, date(2026, 6, 1))
        self.assertEqual(request.end_date, date(2026, 6, 30))
        self.assertFalse(request.needs_time_clarification)

        missing_time = get_event_statistics_request("thong ke su kien Vinh Son")
        self.assertEqual(missing_time.plant_code, "VS")
        self.assertTrue(missing_time.needs_time_clarification)

    def test_event_statistics_request_uses_clarification_context_for_all_time(self):
        history = [
            {
                "role": "assistant",
                "content": "Anh/chị muốn thống kê sự kiện của Sông Hinh trong khoảng thời gian nào, hay muốn hiển thị tất cả?",
            }
        ]

        request = get_event_statistics_request("tat ca", history)

        self.assertEqual(request.plant_code, "SH")
        self.assertTrue(request.all_time)
        self.assertFalse(request.needs_time_clarification)
