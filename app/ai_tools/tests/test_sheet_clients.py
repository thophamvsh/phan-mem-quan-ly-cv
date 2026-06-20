from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from ai_tools.songhinh_tools.core.sheets_client import GoogleSheetsClientManager, TTLCache
from ai_tools.vinhson_tools.core import sheets_client as vs_sheets


class SongHinhSheetClientTests(SimpleTestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            service_account_file="missing.json",
            worksheet_operational="Operational",
            worksheet_hours="Hours",
            spreadsheet_id="operational-id",
            stats_export_spreadsheet_id_songhinh="stats-id",
            scopes_write=["scope"],
        )

    @patch("ai_tools.songhinh_tools.core.sheets_client.time.time")
    def test_ttl_cache_hit_expiry_and_clear(self, now):
        cache = TTLCache(ttl_seconds=10)
        now.return_value = 100
        cache.set("key", [["value"]])
        self.assertEqual(cache.get("key"), [["value"]])
        now.return_value = 111
        self.assertIsNone(cache.get("key"))
        cache.set("key", [])
        cache.clear()
        self.assertIsNone(cache.get("key"))

    def test_manager_reset_dummy_worksheets_and_missing_credentials(self):
        manager = GoogleSheetsClientManager(self.config)
        manager._write_client["x"] = Mock()
        manager._write_spreadsheet["x"] = Mock()
        manager.cache.set("x", [])
        manager.reset()
        self.assertEqual(manager._write_client, {})
        self.assertIsNone(manager._authorize(["scope"]))
        operational, hours = manager.get_read_worksheets()
        self.assertEqual(operational.title, "Operational")
        self.assertEqual(hours.title, "Hours")

    @patch("ai_tools.songhinh_tools.core.sheets_client.retry_with_backoff")
    def test_open_spreadsheet_handles_success_and_errors(self, retry):
        manager = GoogleSheetsClientManager(self.config)
        spreadsheet = Mock()
        retry.return_value = spreadsheet
        self.assertIs(manager._open_spreadsheet(Mock(), "id"), spreadsheet)
        retry.side_effect = RuntimeError("offline")
        self.assertIsNone(manager._open_spreadsheet(Mock(), "id"))

    def test_cached_values_route_operational_hours_real_sheet_and_cache(self):
        manager = GoogleSheetsClientManager(self.config)
        operational = Mock(title="Operational")
        hours = Mock(title="Hours")
        stats = Mock(title="Stats")
        stats.get_all_values.return_value = [["stats"]]
        with (
            patch.object(manager, "_fetch_operational_from_db", return_value=[["op"]]) as fetch_op,
            patch.object(manager, "_fetch_hours_from_db", return_value=[["hours"]]) as fetch_hours,
        ):
            self.assertEqual(manager.get_all_values_cached(operational, "op"), [["op"]])
            self.assertEqual(manager.get_all_values_cached(hours, "hours"), [["hours"]])
            self.assertEqual(manager.get_all_values_cached(stats, "stats"), [["stats"]])
            self.assertEqual(manager.get_all_values_cached(operational, "op"), [["op"]])
            fetch_op.assert_called_once()
            fetch_hours.assert_called_once()


class VinhSonSheetClientTests(SimpleTestCase):
    def tearDown(self):
        vs_sheets.reset_google_sheets_client()

    @patch("ai_tools.vinhson_tools.core.sheets_client._fetch_vinhson_hours", return_value=[["hours"]])
    @patch("ai_tools.vinhson_tools.core.sheets_client._fetch_vinhson_operational", return_value=[["op"]])
    def test_wrapper_and_dummy_client_route_database_data(self, fetch_op, fetch_hours):
        real = Mock()
        real.get_all_values.return_value = [["real"]]
        self.assertEqual(vs_sheets.WorksheetWrapper(real, "vinhson_operational").get_all_values(), [["op"]])
        self.assertEqual(vs_sheets.WorksheetWrapper(real, "vinhson_hours").get_all_values(), [["hours"]])
        self.assertEqual(vs_sheets.WorksheetWrapper(real, "other").get_all_values(), [["real"]])

        client, operational, hours = vs_sheets.SheetsClient.get_client()
        self.assertIsNone(client.open_by_key("id"))
        self.assertEqual(operational.get_all_values(), [["op"]])
        self.assertEqual(hours.get_all_values(), [["hours"]])

    def test_reset_clears_global_clients_and_data_caches(self):
        vs_sheets._gs_client = object()
        vs_sheets._gs_worksheet = object()
        vs_sheets._gs_worksheet_hours = object()
        vs_sheets._cached_operational = [["cached"]]
        vs_sheets._cached_hours = [["cached"]]
        vs_sheets.reset_google_sheets_client()
        self.assertIsNone(vs_sheets._gs_client)
        self.assertIsNone(vs_sheets._gs_worksheet)
        self.assertIsNone(vs_sheets._gs_worksheet_hours)
        self.assertIsNone(vs_sheets._cached_operational)
        self.assertIsNone(vs_sheets._cached_hours)
