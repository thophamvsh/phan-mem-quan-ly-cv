from datetime import date
from unittest.mock import patch

from gspread.exceptions import WorksheetNotFound
from django.test import SimpleTestCase

from ..google_sheet_services import (
    GoogleSheetHydrologyService,
    get_gio_phat_sheet_row_number,
    get_san_luong_sheet_row_number,
    get_thuc_te_sheet_row_number,
)
from ..sync_views import (
    get_gio_phat_rows,
    get_san_luong_rows,
    parse_gio_phat_records_with_metadata,
    parse_san_luong_records_with_metadata,
    parse_thuc_te_records_with_metadata,
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
        self.assertEqual(get_thuc_te_sheet_row_number("songhinh", date(2023, 1, 1)), 8)
        self.assertEqual(get_thuc_te_sheet_row_number("vinhson", date(2023, 1, 1)), 6)
        self.assertEqual(get_thuc_te_sheet_row_number("songhinh", date(2023, 1, 2)), 9)
        self.assertEqual(get_thuc_te_sheet_row_number("vinhson", date(2023, 1, 2)), 7)

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

    def test_thuc_te_parser_maps_song_hinh_and_vinh_son_columns(self):
        song_hinh = parse_thuc_te_records_with_metadata(
            [["30/05/2026", "200,567", "", "", "", "123,456"]],
            "songhinh",
            date(2026, 5, 30),
        )
        self.assertEqual(song_hinh.data[0]["ngay"], "2026-05-30")
        self.assertEqual(song_hinh.data[0]["muc_nuoc_ho"], 200.567)
        self.assertEqual(song_hinh.data[0]["qve"], 123.456)
        self.assertIsNone(song_hinh.data[0]["qve_tong"])

        vinh_son = parse_thuc_te_records_with_metadata(
            [["30/05/2026", "768,123", "819,234", "976,345", "10,111", "20,222", "30,333", "60,666"]],
            "vinhson",
            date(2026, 5, 30),
        )
        self.assertEqual(vinh_son.data[0]["muc_nuoc_ho_a"], 768.123)
        self.assertEqual(vinh_son.data[0]["muc_nuoc_ho_b"], 819.234)
        self.assertEqual(vinh_son.data[0]["muc_nuoc_ho_c"], 976.345)
        self.assertEqual(vinh_son.data[0]["qve_ho_a"], 10.111)
        self.assertEqual(vinh_son.data[0]["qve_ho_b"], 20.222)
        self.assertEqual(vinh_son.data[0]["qve_ho_c"], 30.333)
        self.assertEqual(vinh_son.data[0]["qve_tong"], 60.666)
        self.assertIsNone(vinh_son.data[0]["muc_nuoc_ho"])

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

    @patch("thongsothuyvan.google_sheet_services.get_stats_export_spreadsheet_id", return_value="sheet-id")
    def test_preview_thuc_te_reads_expected_sheet_range(self, _sheet_id):
        class Worksheet:
            def __init__(self):
                self.calls = []

            def get(self, range_name):
                self.calls.append(("get", range_name))
                return [["01/01/2023", "200,5", "", "", "", "123,4"]]

            def get_all_values(self):
                self.calls.append(("all", None))
                return []

        class Spreadsheet:
            def __init__(self, worksheet):
                self._worksheet = worksheet
                self.sheet_names = []

            def worksheet(self, name):
                self.sheet_names.append(name)
                return self._worksheet

        class Client:
            def __init__(self, spreadsheet):
                self._spreadsheet = spreadsheet

            def open_by_key(self, sheet_id):
                return self._spreadsheet

        worksheet = Worksheet()
        spreadsheet = Spreadsheet(worksheet)
        service = GoogleSheetHydrologyService(client_factory=lambda nhamay: Client(spreadsheet))

        result = service.preview_thuc_te("songhinh", date(2023, 1, 1))

        self.assertEqual(spreadsheet.sheet_names, ["2023"])
        self.assertEqual(worksheet.calls, [("get", "A8:F8")])
        self.assertEqual(result.source_range, "2023!A8:F8")
        self.assertEqual(result.data[0]["muc_nuoc_ho"], 200.5)
        self.assertEqual(result.data[0]["qve"], 123.4)

    @patch("thongsothuyvan.google_sheet_services.get_stats_export_spreadsheet_id", return_value="sheet-id")
    def test_preview_thuc_te_range_reads_one_google_range(self, _sheet_id):
        class Worksheet:
            def __init__(self):
                self.calls = []

            def get(self, range_name):
                self.calls.append(("get", range_name))
                return [
                    ["01/01/2023", "768,1", "819,2", "976,3", "10", "20", "30", "60"],
                    ["02/01/2023", "768,2", "819,3", "976,4", "11", "21", "31", "63"],
                ]

            def get_all_values(self):
                self.calls.append(("all", None))
                return []

        class Spreadsheet:
            def __init__(self, worksheet):
                self._worksheet = worksheet
                self.sheet_names = []

            def worksheet(self, name):
                self.sheet_names.append(name)
                return self._worksheet

        class Client:
            def __init__(self, spreadsheet):
                self._spreadsheet = spreadsheet

            def open_by_key(self, sheet_id):
                return self._spreadsheet

        worksheet = Worksheet()
        spreadsheet = Spreadsheet(worksheet)
        service = GoogleSheetHydrologyService(client_factory=lambda nhamay: Client(spreadsheet))

        result = service.preview_thuc_te_range("vinhson", date(2023, 1, 1), date(2023, 1, 2))

        self.assertEqual(spreadsheet.sheet_names, ["2023 ngày"])
        self.assertEqual(worksheet.calls, [("get", "A6:H7")])
        self.assertEqual(result.source_range, "2023 ngày!A6:H7")
        self.assertEqual(len(result.data), 2)
        self.assertEqual(result.data[1]["qve_tong"], 63.0)

    @patch("thongsothuyvan.google_sheet_services.get_stats_export_spreadsheet_id", return_value="sheet-id")
    def test_preview_thuc_te_range_falls_back_when_sheet_rows_are_shifted(self, _sheet_id):
        class Worksheet:
            def __init__(self):
                self.calls = []

            def get(self, range_name):
                self.calls.append(("get", range_name))
                return [
                    ["18/06/2026", "203,505", "56", "33,361", "0,0", "14,840"],
                    ["19/06/2026", "203,44", "55", "36,473", "0,0", "14,865"],
                    ["20/06/2026", "203,368", "56", "32,163", "0,0", "10,555"],
                ]

            def get_all_values(self):
                self.calls.append(("all", None))
                return [
                    ["header"],
                    [],
                    [],
                    ["header"],
                    [],
                    ["header"],
                    [],
                    ["21/06/2026", "203,276", "56", "32,253", "0,0", "7,559"],
                    ["22/06/2026", "203,225", "56", "27,674", "0,0", "12,240"],
                    ["23/06/2026", "203,174", "55,5", "27,967", "0,0", "9,446"],
                ]

        class Spreadsheet:
            def __init__(self, worksheet):
                self._worksheet = worksheet

            def worksheet(self, name):
                return self._worksheet

        class Client:
            def __init__(self, spreadsheet):
                self._spreadsheet = spreadsheet

            def open_by_key(self, sheet_id):
                return self._spreadsheet

        worksheet = Worksheet()
        spreadsheet = Spreadsheet(worksheet)
        service = GoogleSheetHydrologyService(client_factory=lambda nhamay: Client(spreadsheet))

        result = service.preview_thuc_te_range("songhinh", date(2026, 6, 21), date(2026, 6, 23))

        self.assertEqual(worksheet.calls, [("get", "A1275:F1277"), ("all", None)])
        self.assertEqual(result.source_range, "2023!all_values")
        self.assertEqual([item["ngay"] for item in result.data], ["2026-06-21", "2026-06-22", "2026-06-23"])
        self.assertEqual(result.data[2]["qve"], 9.446)
        self.assertTrue(result.warnings)

    @patch("thongsothuyvan.google_sheet_services.get_stats_export_spreadsheet_id", return_value="sheet-id")
    def test_preview_thuc_te_accepts_sheet_title_with_different_spacing(self, _sheet_id):
        class Worksheet:
            title = "2023  ngày"

            def __init__(self):
                self.calls = []

            def get(self, range_name):
                self.calls.append(("get", range_name))
                return [["01/01/2023", "768,1", "819,2", "976,3", "10", "20", "30", "60"]]

            def get_all_values(self):
                self.calls.append(("all", None))
                return []

        class Spreadsheet:
            def __init__(self, worksheet):
                self._worksheet = worksheet
                self.requested_titles = []

            def worksheet(self, name):
                self.requested_titles.append(name)
                if name == self._worksheet.title:
                    return self._worksheet
                raise WorksheetNotFound(name)

            def worksheets(self):
                return [self._worksheet]

        class Client:
            def __init__(self, spreadsheet):
                self._spreadsheet = spreadsheet

            def open_by_key(self, sheet_id):
                return self._spreadsheet

        worksheet = Worksheet()
        spreadsheet = Spreadsheet(worksheet)
        service = GoogleSheetHydrologyService(client_factory=lambda nhamay: Client(spreadsheet))

        result = service.preview_thuc_te_range("vinhson", date(2023, 1, 1), date(2023, 1, 1))

        self.assertEqual(spreadsheet.requested_titles, ["2023 ngày"])
        self.assertEqual(worksheet.calls, [("get", "A6:H6")])
        self.assertEqual(result.source_range, "2023  ngày!A6:H6")
        self.assertEqual(result.data[0]["qve_tong"], 60.0)
