from types import SimpleNamespace

from django.test import SimpleTestCase

from ai_tools.leadership_report.utils.formatting import (
    add_report_totals,
    as_float,
    escape_markdown_cell,
    fmt_report_decimal,
    fmt_report_direct_pct,
    fmt_report_number,
    fmt_report_pct,
    record_value,
    sum_record_field,
)
from ai_tools.leadership_report.utils.text import normalize_text, normalize_title


class LeadershipFormattingTests(SimpleTestCase):
    def test_sum_record_field_ignores_missing_values(self):
        records = [SimpleNamespace(value=1.25), SimpleNamespace(value=None), SimpleNamespace(value="2.75")]
        self.assertEqual(sum_record_field(records, "value"), 4.0)
        self.assertIsNone(sum_record_field(records, "missing"))

    def test_number_and_decimal_formatting(self):
        self.assertEqual(fmt_report_number(None), "-")
        self.assertEqual(fmt_report_number(1234), "1.234")
        self.assertEqual(fmt_report_number(1234.5), "1.234,50")
        self.assertEqual(fmt_report_decimal(None), "-")
        self.assertEqual(fmt_report_decimal(1234.567, 2), "1.234,57")

    def test_percentage_formatting_handles_invalid_plans(self):
        self.assertEqual(fmt_report_pct(50, 100), "50.00%")
        self.assertEqual(fmt_report_pct(50, 0), "-")
        self.assertEqual(fmt_report_pct(None, 100), "-")
        self.assertEqual(fmt_report_direct_pct(12.34), "12,3%")
        self.assertEqual(fmt_report_direct_pct(None), "-")

    def test_escape_markdown_cell_keeps_table_cells_valid(self):
        self.assertEqual(escape_markdown_cell(None), "-")
        self.assertEqual(escape_markdown_cell(""), "-")
        self.assertEqual(escape_markdown_cell("A | B\r\nC"), r"A \| B C")

    def test_totals_and_safe_record_conversion(self):
        totals = {"a": None, "b": 2.0}
        add_report_totals(totals, {"a": 1.5, "b": 3.0, "c": None})
        self.assertEqual(totals, {"a": 1.5, "b": 5.0})
        self.assertEqual(as_float("1.25"), 1.25)
        self.assertIsNone(as_float("invalid"))
        self.assertIsNone(as_float(None))
        self.assertEqual(record_value(SimpleNamespace(value="2.5"), "value"), 2.5)
        self.assertIsNone(record_value(None, "value"))
        self.assertIsNone(record_value(SimpleNamespace(value=1), None))

    def test_text_normalization_is_case_and_accent_insensitive(self):
        self.assertEqual(normalize_text("BÁO CÁO"), "bao cao")
        self.assertEqual(normalize_title("  Phó   Tổng Giám Đốc  "), "pho tong giam doc")
        self.assertEqual(normalize_text(None), "")
