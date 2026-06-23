from datetime import date
from types import SimpleNamespace
from unittest.mock import ANY, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from thongsothuyvan.models import ThongSoThuyVanThucTe
from thongsothuyvan.tasks import (
    AUTO_SYNC_USER_EMAIL,
    get_missing_thuc_te_sync_range,
    sync_missing_thuy_van_thuc_te_daily_task,
)


class ThuyVanThucTeTaskTests(TestCase):
    databases = {"default"}

    def test_get_missing_sync_range_uses_day_after_latest_record(self):
        ThongSoThuyVanThucTe.objects.create(
            nha_may="songhinh",
            ngay=date(2026, 6, 20),
            muc_nuoc_ho=200.5,
            qve=123.4,
        )

        self.assertEqual(
            get_missing_thuc_te_sync_range("songhinh", date(2026, 6, 22)),
            (date(2026, 6, 21), date(2026, 6, 22)),
        )
        self.assertIsNone(get_missing_thuc_te_sync_range("songhinh", date(2026, 6, 20)))

    @patch("thongsothuyvan.tasks.close_old_connections")
    @patch("thongsothuyvan.tasks.timezone.localdate", return_value=date(2026, 6, 23))
    @patch("thongsothuyvan.tasks.GoogleSheetHydrologyService")
    def test_daily_task_syncs_missing_ranges_with_system_user(self, service_class, _localdate, _close_connections):
        User = get_user_model()
        ThongSoThuyVanThucTe.objects.create(
            nha_may="songhinh",
            ngay=date(2026, 6, 20),
            muc_nuoc_ho=200.5,
            qve=123.4,
        )
        ThongSoThuyVanThucTe.objects.create(
            nha_may="vinhson",
            ngay=date(2026, 6, 22),
            muc_nuoc_ho_a=768.1,
            qve_tong=60,
        )
        service_class.return_value.sync_thuc_te_range.return_value = SimpleNamespace(
            saved_count=2,
            updated_count=0,
            parsed_count=2,
            skipped_count=0,
            source_range="2023!A1:F2",
            warnings=[],
        )

        result = sync_missing_thuy_van_thuc_te_daily_task()

        system_user = User.objects.get(email=AUTO_SYNC_USER_EMAIL)
        self.assertEqual(system_user.username, "system_auto_sync")
        self.assertEqual(result["songhinh"]["start_date"], "2026-06-21")
        self.assertEqual(result["songhinh"]["end_date"], "2026-06-22")
        self.assertTrue(result["vinhson"]["skipped"])
        service_class.return_value.sync_thuc_te_range.assert_called_once_with(
            nhamay="songhinh",
            start_date=date(2026, 6, 21),
            end_date=date(2026, 6, 22),
            user=system_user,
            can_modify=ANY,
        )
