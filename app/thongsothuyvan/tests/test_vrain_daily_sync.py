from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytz
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from thongsothuyvan.models import TramDoMuaVrain
from thongsothuyvan.tasks import sync_vrain_daily_rainfall_task
from thongsothuyvan.vrain_services import (
    get_vrain_realtime_24h,
    get_vrain_since_19,
    get_vrain_since_19_window,
    sync_vrain_daily_rainfall,
)
from thongsothuyvan.vrain_views import VrainSince19APIView


VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")
NOW = VN_TZ.localize(datetime(2026, 10, 9, 7, 12, 34))


def vrain_response(depth):
    return {"Data": [{"station_id": "036604", "value": [{"depth": depth}]}]}


class VrainDailySyncTests(TestCase):
    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    @patch("thongsothuyvan.vrain_services._vn_now", return_value=NOW)
    def test_today_is_provisional_and_ends_at_current_second(self, _now, fetch):
        fetch.return_value = vrain_response(2.5)

        result = sync_vrain_daily_rainfall()

        fetch.assert_called_once_with("2026-10-09 00:00:00", "2026-10-09 07:12:34")
        record = TramDoMuaVrain.objects.get()
        self.assertEqual(record.Thoi_gian, VN_TZ.localize(datetime(2026, 10, 9)))
        self.assertEqual(record.Dap_Tran, 2.5)
        self.assertEqual(record.sync_status, TramDoMuaVrain.SyncStatus.PROVISIONAL)
        self.assertIsNotNone(record.synced_at)
        self.assertEqual(result["sync_status"], "provisional")

    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    @patch("thongsothuyvan.vrain_services._vn_now", return_value=NOW)
    def test_yesterday_is_finalized_and_resync_updates_same_record(self, _now, fetch):
        fetch.return_value = vrain_response(3)
        result = sync_vrain_daily_rainfall(date(2026, 10, 8))
        first_id = TramDoMuaVrain.objects.get().pk

        fetch.return_value = vrain_response(4)
        again = sync_vrain_daily_rainfall("2026-10-08")

        self.assertEqual(
            fetch.call_args.args,
            ("2026-10-08 00:00:00", "2026-10-08 23:59:59"),
        )
        self.assertEqual(TramDoMuaVrain.objects.count(), 1)
        record = TramDoMuaVrain.objects.get()
        self.assertEqual(record.pk, first_id)
        self.assertEqual(record.Dap_Tran, 4)
        self.assertEqual(record.sync_status, TramDoMuaVrain.SyncStatus.FINALIZED)
        self.assertTrue(result["created"])
        self.assertFalse(again["created"])

    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    @patch("thongsothuyvan.vrain_services._vn_now", return_value=NOW)
    def test_provisional_record_becomes_finalized_next_day(self, _now, fetch):
        record = TramDoMuaVrain.objects.create(
            Thoi_gian=VN_TZ.localize(datetime(2026, 10, 8)),
            Dap_Tran=1,
            sync_status=TramDoMuaVrain.SyncStatus.PROVISIONAL,
        )
        fetch.return_value = vrain_response(5)

        sync_vrain_daily_rainfall(date(2026, 10, 8))

        record.refresh_from_db()
        self.assertEqual(record.Dap_Tran, 5)
        self.assertEqual(record.sync_status, TramDoMuaVrain.SyncStatus.FINALIZED)
        self.assertIsNotNone(record.synced_at)

    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    @patch("thongsothuyvan.vrain_services._vn_now", return_value=NOW)
    def test_failed_vrain_request_does_not_change_existing_record(self, _now, fetch):
        record = TramDoMuaVrain.objects.create(
            Thoi_gian=VN_TZ.localize(datetime(2026, 10, 8)),
            Dap_Tran=1,
            sync_status=TramDoMuaVrain.SyncStatus.UNKNOWN,
        )
        fetch.side_effect = RuntimeError("VRAIN unavailable")

        with self.assertRaisesMessage(RuntimeError, "VRAIN unavailable"):
            sync_vrain_daily_rainfall(date(2026, 10, 8))

        record.refresh_from_db()
        self.assertEqual(record.Dap_Tran, 1)
        self.assertEqual(record.sync_status, TramDoMuaVrain.SyncStatus.UNKNOWN)

    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    @patch("thongsothuyvan.vrain_services._vn_now", return_value=NOW)
    def test_future_date_is_rejected_without_calling_vrain(self, _now, fetch):
        with self.assertRaisesMessage(ValueError, "ngày tương lai"):
            sync_vrain_daily_rainfall(date(2026, 10, 10))
        fetch.assert_not_called()
        self.assertFalse(TramDoMuaVrain.objects.exists())

    @patch("thongsothuyvan.tasks.close_old_connections")
    @patch("thongsothuyvan.tasks.timezone.localdate", return_value=date(2026, 10, 9))
    @patch("thongsothuyvan.vrain_services.sync_vrain_daily_rainfall")
    def test_scheduled_task_finalizes_yesterday(self, sync, _localdate, _close):
        sync_vrain_daily_rainfall_task()
        sync.assert_called_once_with(date(2026, 10, 8))

    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    @patch("thongsothuyvan.vrain_services._vn_now", return_value=NOW)
    def test_realtime_remains_a_rolling_24_hour_window(self, _now, fetch):
        fetch.return_value = vrain_response(1)

        result = get_vrain_realtime_24h()

        expected_start = (NOW - timedelta(hours=23, minutes=59, seconds=59)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        fetch.assert_called_once_with(expected_start, "2026-10-09 07:12:34")
        self.assertEqual(result["data"]["Dap_Tran"], 1)

    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    def test_since_19_uses_previous_evening_before_19(self, fetch):
        fetch.return_value = vrain_response(2)
        window = get_vrain_since_19_window(NOW)

        result = get_vrain_since_19(window)

        fetch.assert_called_once_with("2026-10-08 19:00:00", "2026-10-09 07:12:34")
        self.assertEqual(result["start_time"], "2026-10-08 19:00:00")
        self.assertEqual(result["data"]["Dap_Tran"], 2)

    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    def test_since_19_uses_today_after_19(self, fetch):
        fetch.return_value = vrain_response(3)
        evening = VN_TZ.localize(datetime(2026, 10, 9, 20, 15, 0))

        get_vrain_since_19(get_vrain_since_19_window(evening))

        fetch.assert_called_once_with("2026-10-09 19:00:00", "2026-10-09 20:15:00")

    @patch("thongsothuyvan.vrain_services._fetch_station_stats")
    def test_since_19_rolls_over_exactly_at_19(self, fetch):
        fetch.return_value = vrain_response(0)
        evening = VN_TZ.localize(datetime(2026, 10, 9, 19, 0, 0))

        get_vrain_since_19(get_vrain_since_19_window(evening))

        fetch.assert_called_once_with("2026-10-09 19:00:00", "2026-10-09 19:00:00")

    @patch("thongsothuyvan.vrain_views.get_vrain_since_19")
    @patch("thongsothuyvan.vrain_views.get_vrain_since_19_window")
    def test_since_19_endpoint_separates_cache_at_19(self, window, get_data):
        cache.clear()
        user = get_user_model().objects.create_user(
            email="vrain-test@example.com",
            username="vrain-test",
            password="test-password",
        )
        request = APIRequestFactory().get("/api/v1/thongsothuyvan/vrain-since-19/")
        force_authenticate(request, user=user)
        view = VrainSince19APIView.as_view()
        before = VN_TZ.localize(datetime(2026, 10, 9, 18, 59, 59))
        after = VN_TZ.localize(datetime(2026, 10, 9, 19, 0, 0))
        window.side_effect = [
            get_vrain_since_19_window(before),
            get_vrain_since_19_window(before),
            get_vrain_since_19_window(after),
        ]
        get_data.side_effect = [
            {"ok": True, "data": {"Dap_Tran": 2}},
            {"ok": True, "data": {"Dap_Tran": 0}},
        ]

        first = view(request)
        second = view(request)
        third = view(request)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.data["data"]["Dap_Tran"], 2)
        self.assertEqual(third.data["data"]["Dap_Tran"], 0)
        self.assertEqual(get_data.call_count, 2)
