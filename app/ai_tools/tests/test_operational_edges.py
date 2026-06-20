from unittest.mock import Mock

from django.test import SimpleTestCase

from ai_tools.songhinh_tools.services.operational_service import OperationalService as SongHinhOperational
from ai_tools.vinhson_tools.services.operational_service import OperationalService as VinhSonOperational


class SongHinhOperationalEdgeTests(SimpleTestCase):
    def test_connection_short_data_invalid_dates_and_missing_rows(self):
        manager = Mock()
        manager.get_read_worksheets.return_value = (None, None)
        service = SongHinhOperational(manager)
        self.assertIn("CSDL", service.get_operational_data())

        worksheet = object()
        manager.get_read_worksheets.return_value = (worksheet, None)
        manager.get_all_values_cached.return_value = [["header"]]
        self.assertIn("d", service.get_operational_data())

        manager.get_all_values_cached.return_value = [["header"], ["header"], ["01/01/2026"]]
        self.assertIn("format", service.get_operational_data(date_str="invalid"))
        self.assertIn("format", service.get_operational_data(start_date_str="invalid", end_date_str="02/01/2026"))
        self.assertIn("02/01/2026", service.get_operational_data(date_str="02/01/2026"))
        self.assertIn("03/01/2026", service.get_operational_data(start_date_str="02/01/2026", end_date_str="03/01/2026"))


class VinhSonOperationalEdgeTests(SimpleTestCase):
    def setUp(self):
        self.service = VinhSonOperational()
        self.service.sheets_client = Mock()
        self.service.hours_service = Mock()

    def test_connection_short_data_invalid_dates_missing_rows_and_exception(self):
        self.service.sheets_client.get_client.return_value = (None, None, None)
        self.assertIn("CSDL", self.service.get_operational_data())

        worksheet = Mock()
        worksheet.get_all_values.return_value = [["header"]]
        self.service.sheets_client.get_client.return_value = (Mock(), worksheet, None)
        self.assertIn("d", self.service.get_operational_data())

        worksheet.get_all_values.return_value = [["header"], ["header"], ["", "01/01/2026", "Vinh Son -A"]]
        self.assertIn("format", self.service.get_operational_data(date="invalid"))
        self.assertIn("format", self.service.get_operational_data(start_date="invalid", end_date="02/01/2026"))
        self.assertIn("02/01/2026", self.service.get_operational_data(date="02/01/2026", reservoir="Vinh Son -A"))
        self.assertEqual(self.service.get_operational_data(date="02/01/2026", reservoir="Vinh Son -B"), "")
        self.assertIn("03/01/2026", self.service.get_operational_data(start_date="02/01/2026", end_date="03/01/2026", reservoir="All"))

        self.service.sheets_client.get_client.side_effect = RuntimeError("offline")
        self.assertIn("offline", self.service.get_operational_data())
