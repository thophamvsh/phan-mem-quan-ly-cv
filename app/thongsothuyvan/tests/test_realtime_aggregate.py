from datetime import datetime, timedelta, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from core.models import UserProfile
from tochuc.models import NhaMay
from thongsothuyvan.models import ThongsoSanxuat


class RealtimeAggregateAccessTests(APITestCase):
    def setUp(self):
        sh = NhaMay.objects.create(ma_nha_may="SH", ten_nha_may="Sông Hinh")
        vs = NhaMay.objects.create(ma_nha_may="VS", ten_nha_may="Vĩnh Sơn")
        tkt = NhaMay.objects.create(ma_nha_may="TKT", ten_nha_may="Thượng Kon Tum")
        user_model = get_user_model()
        self.sh_user = user_model.objects.create_user(username="realtime_sh", email="realtime_sh@example.com", password="pass12345678")
        self.vs_user = user_model.objects.create_user(username="realtime_vs", email="realtime_vs@example.com", password="pass12345678")
        self.tkt_user = user_model.objects.create_user(username="realtime_tkt", email="realtime_tkt@example.com", password="pass12345678")
        self.admin = user_model.objects.create_superuser(username="realtime_admin", email="realtime_admin@example.com", password="pass12345678")
        for user, plant in ((self.sh_user, sh), (self.vs_user, vs), (self.tkt_user, tkt)):
            UserProfile.objects.create(user=user, ho_ten=user.username, nha_may=plant, can_view_realtime_hydrology=True)

    @patch("thongsothuyvan.views.views_realtime.fetch_realtime_payload_data")
    @patch("thongsothuyvan.views.views_realtime.enrich_songhinh_payload")
    def test_realtime_checks_plant_before_upstream(self, enrich, fetch):
        enrich.return_value = {"time_stamp": "2026-10-04 09:00:00"}
        self.client.force_authenticate(user=self.vs_user)
        self.assertEqual(self.client.get("/api/v1/thongsothuyvan/realtime/songhinh/").status_code, 403)
        fetch.assert_not_called()
        self.client.force_authenticate(user=self.sh_user)
        self.assertEqual(self.client.get("/api/v1/thongsothuyvan/realtime/songhinh/").status_code, 200)

    def test_snapshot_list_and_write_are_plant_scoped(self):
        self.assertEqual(self.client.get("/api/v1/thongsothuyvan/realtime-vinhson-snapshots/").status_code, 401)
        self.client.force_authenticate(user=self.sh_user)
        self.assertEqual(self.client.get("/api/v1/thongsothuyvan/realtime-vinhson-snapshots/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/thongsothuyvan/realtime-vinhson-snapshots/999/").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/thongsothuyvan/realtime-vinhson-snapshots/", {}, format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/thongsothuyvan/realtime-songhinh-snapshots/").status_code, 200)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get("/api/v1/thongsothuyvan/realtime-vinhson-snapshots/").status_code, 200)

    @patch("thongsothuyvan.views.views_realtime.save_all_realtime_snapshots")
    def test_manual_save_cannot_write_another_plant(self, save_snapshots):
        self.sh_user.profile.can_update_realtime_hydrology = True
        self.sh_user.profile.save(update_fields=["can_update_realtime_hydrology"])
        self.client.force_authenticate(user=self.sh_user)
        response = self.client.post("/api/v1/thongsothuyvan/realtime/manual-save/", {"plant": "vinhson"}, format="json")
        self.assertEqual(response.status_code, 403)
        save_snapshots.assert_not_called()
        response = self.client.patch("/api/v1/thongsothuyvan/realtime/state/", {"auto_update_enabled": True}, format="json")
        self.assertEqual(response.status_code, 403)

    @patch("thongsothuyvan.views.views_realtime.get_operating_capacity_by_level", return_value=140.25)
    def test_tkt_latest_daily_is_scoped_and_not_from_future(self, capacity_lookup):
        today = timezone.localdate()
        today_at_noon = timezone.make_aware(datetime.combine(today, time(12)))
        tomorrow_at_noon = today_at_noon + timedelta(days=1)
        ThongsoSanxuat.objects.create(nha_may="thuongkontum", thoi_gian=today_at_noon, cot_g=1140.5)
        ThongsoSanxuat.objects.create(nha_may="thuongkontum", thoi_gian=tomorrow_at_noon, cot_g=9999)
        url = "/api/v1/thongsothuyvan/latest-daily-hydrology/thuongkontum/"
        self.client.force_authenticate(user=self.sh_user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(user=self.tkt_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["recordDate"], today.isoformat())
        self.assertEqual(response.data["waterLevelM"], 1140.5)
        self.assertEqual(response.data["capacityMcm"], 140.25)
        capacity_lookup.assert_called_once_with("thuongkontum", 1140.5)
        self.client.force_authenticate(user=self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_tkt_empty_record_has_explicit_nulls(self):
        self.client.force_authenticate(user=self.tkt_user)
        response = self.client.get("/api/v1/thongsothuyvan/latest-daily-hydrology/thuongkontum/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"recordDate": None, "waterLevelM": None, "capacityMcm": None})
