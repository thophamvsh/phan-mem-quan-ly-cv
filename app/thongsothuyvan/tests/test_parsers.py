from datetime import date

from django.test import SimpleTestCase

from ..google_sheet_services import GoogleSheetHydrologyService, get_gio_phat_sheet_row_number, get_san_luong_sheet_row_number
from ..sync_views import (
    get_gio_phat_rows,
    get_san_luong_rows,
    parse_gio_phat_records_with_metadata,
    parse_san_luong_records_with_metadata,
    safe_float,
    safe_float_vinhson_decimal,
    safe_int_vinhson,
)

class ThongSoThuyVanParserTests(SimpleTestCase):
    def test_safe_int_vinhson(self):
        # Kiểm tra chuỗi chứa phân cách dấu chấm
        self.assertEqual(safe_int_vinhson("150.000"), 150000.0)
        self.assertEqual(safe_int_vinhson("1.200.000"), 1200000.0)

        # Kiểm tra chuỗi chứa phân cách dấu phẩy
        self.assertEqual(safe_int_vinhson("150,000"), 150000.0)
        self.assertEqual(safe_int_vinhson("1,200,000"), 1200000.0)

        # Kiểm tra số nguyên dạng chuỗi thông thường
        self.assertEqual(safe_int_vinhson("150"), 150.0)
        self.assertEqual(safe_int_vinhson(" 150 "), 150.0)

        # Kiểm tra kiểu số sẵn có
        self.assertEqual(safe_int_vinhson(150000), 150000.0)
        self.assertEqual(safe_int_vinhson(150000.75), 150000.0)

        # Kiểm tra trường hợp None hoặc rỗng
        self.assertIsNone(safe_int_vinhson(None))
        self.assertIsNone(safe_int_vinhson(""))
        self.assertIsNone(safe_int_vinhson("   "))

        # Kiểm tra chuỗi không hợp lệ
        self.assertIsNone(safe_int_vinhson("abc"))

    def test_safe_float_vinhson_decimal(self):
        # Kiểm tra chuyển đổi số thập phân với dấu phẩy/chấm và làm tròn 2 số sau thập phân
        self.assertEqual(safe_float_vinhson_decimal("150.256"), 150.26)
        self.assertEqual(safe_float_vinhson_decimal("150.254"), 150.25)
        self.assertEqual(safe_float_vinhson_decimal("150,25"), 150.25)
        self.assertEqual(safe_float_vinhson_decimal("150,2"), 150.2)

        # Kiểm tra kiểu số sẵn có
        self.assertEqual(safe_float_vinhson_decimal(150.256), 150.26)
        self.assertEqual(safe_float_vinhson_decimal(150.2), 150.2)

        # Kiểm tra trường hợp None hoặc rỗng
        self.assertIsNone(safe_float_vinhson_decimal(None))
        self.assertIsNone(safe_float_vinhson_decimal(""))

    def test_original_safe_float_retains_behavior(self):
        # Kiểm tra hàm safe_float cũ vẫn hoạt động đúng như trước
        self.assertEqual(safe_float("150.000"), 150.0)
        self.assertEqual(safe_float("150,25"), 150.25)
        self.assertEqual(safe_float("1.234,56"), 1234.56)

    def test_sheet_row_number_helpers(self):
        self.assertEqual(get_san_luong_sheet_row_number(date(2023, 1, 1)), 2)
        self.assertEqual(get_san_luong_sheet_row_number(date(2023, 1, 2)), 3)
        self.assertEqual(get_gio_phat_sheet_row_number(date(2023, 1, 1)), 3)
        self.assertEqual(get_gio_phat_sheet_row_number(date(2023, 1, 2)), 5)

    def test_range_helpers_read_small_ranges_when_filter_date_present(self):
        class Worksheet:
            def __init__(self):
                self.calls = []

            def get(self, range_name):
                self.calls.append(("get", range_name))
                return [["01/01/2023", "H1", "10"]]

            def get_all_values(self):
                self.calls.append(("all", None))
                return [["header"], ["", "01/01/2023"]]

        san_luong_sheet = Worksheet()
        self.assertEqual(get_san_luong_rows(san_luong_sheet, date(2023, 1, 1)), [["", "01/01/2023", "H1", "10"]])
        self.assertEqual(san_luong_sheet.calls, [("get", "B2:X2")])

        gio_phat_sheet = Worksheet()
        self.assertEqual(get_gio_phat_rows(gio_phat_sheet, date(2023, 1, 1)), [["", "01/01/2023", "H1", "10"]])
        self.assertEqual(gio_phat_sheet.calls, [("get", "B3:E6")])

    def test_parsers_return_skipped_rows_metadata(self):
        san_luong = parse_san_luong_records_with_metadata(
            [
                ["", ""],
                ["", "not-a-date"],
                ["", "30/05/2026", "Ho A", "1", "", "2", "3", "4", "5"],
            ],
            "songhinh",
            date(2026, 5, 30),
        )
        self.assertEqual(len(san_luong.data), 1)
        self.assertEqual([row["reason"] for row in san_luong.skipped_rows], ["missing_date", "invalid_date"])

        gio_phat = parse_gio_phat_records_with_metadata(
            [
                ["", "30/05/2026", "bad-unit", "1", "2"],
                ["", "30/05/2026", "H1", "10", "2"],
            ],
            date(2026, 5, 30),
        )
        self.assertEqual(len(gio_phat.data), 1)
        self.assertEqual(gio_phat.skipped_rows[0]["reason"], "invalid_unit")

    def test_preview_service_falls_back_to_full_sheet_when_range_has_no_data(self):
        class Worksheet:
            def __init__(self):
                self.calls = []

            def get(self, range_name):
                self.calls.append(("get", range_name))
                return [["29/05/2026", "Ho A"]]

            def get_all_values(self):
                self.calls.append(("all", None))
                return [
                    ["header"],
                    ["", "30/05/2026", "Ho A", "1", "", "2", "3", "4", "5"],
                ]

        class Spreadsheet:
            def __init__(self, worksheet):
                self._worksheet = worksheet

            def worksheet(self, name):
                return self._worksheet

        class Client:
            def __init__(self, worksheet):
                self._worksheet = worksheet

            def open_by_key(self, sheet_id):
                return Spreadsheet(self._worksheet)

        worksheet = Worksheet()
        service = GoogleSheetHydrologyService(
            client_factory=lambda nhamay: Client(worksheet),
            spreadsheet_id_getter=lambda nhamay: "sheet-id",
        )

        result = service.preview_san_luong("songhinh", date(2026, 5, 30))

        self.assertEqual(len(result.data), 1)
        self.assertEqual(result.source_range, "Sản lượng!all_values")
        self.assertTrue(result.warnings)
        self.assertEqual(worksheet.calls[0][0], "get")
        self.assertEqual(worksheet.calls[1][0], "all")
