from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.test import SimpleTestCase

from thongsothuyvan.realtime_services import claim_realtime_snapshot_half_hourly_slot


class RealtimeScheduleTests(SimpleTestCase):
    def test_celery_runs_at_zero_and_thirty(self):
        entries = [
            entry for entry in settings.CELERY_BEAT_SCHEDULE.values()
            if entry["task"] == "thongsothuyvan.tasks.save_all_realtime_snapshots_task"
        ]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["schedule"].minute, {0, 30})
        self.assertEqual(entries[0]["schedule"].hour, set(range(24)))

    def test_fallback_claims_each_half_hour_only_once(self):
        state = SimpleNamespace(last_hourly_slot=None, save=lambda **kwargs: None)
        with (
            patch("thongsothuyvan.realtime_services.transaction.atomic", return_value=nullcontext()),
            patch("thongsothuyvan.realtime_services.RealtimeUpdateState.objects") as objects,
            patch("thongsothuyvan.realtime_services.timezone.localtime") as localtime,
        ):
            objects.select_for_update.return_value.get_or_create.return_value = (state, False)
            for hour, minute, expected in [
                (8, 0, True), (8, 1, False), (8, 29, False),
                (8, 30, True), (8, 31, False), (9, 0, True),
            ]:
                localtime.return_value = datetime(2026, 10, 20, hour, minute, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
                self.assertEqual(claim_realtime_snapshot_half_hourly_slot(), expected)

    def test_fallback_accepts_short_delay_but_not_outside_grace(self):
        state = SimpleNamespace(last_hourly_slot=None, save=lambda **kwargs: None)
        with (
            patch("thongsothuyvan.realtime_services.transaction.atomic", return_value=nullcontext()),
            patch("thongsothuyvan.realtime_services.RealtimeUpdateState.objects") as objects,
            patch("thongsothuyvan.realtime_services.timezone.localtime") as localtime,
        ):
            objects.select_for_update.return_value.get_or_create.return_value = (state, False)
            for minute, expected in [(6, False), (35, True), (36, False)]:
                localtime.return_value = datetime(2026, 10, 20, 8, minute, tzinfo=ZoneInfo("Asia/Ho_Chi_Minh"))
                self.assertEqual(claim_realtime_snapshot_half_hourly_slot(), expected)
