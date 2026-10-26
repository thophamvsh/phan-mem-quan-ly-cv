from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch, Mock
from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate
from thongsothuyvan.vrain_history_provider import VN, sanitize, rainfall, fetch_history, VrainHistoryError
from thongsothuyvan.vrain_history_models import VrainStation, VrainSourceSample, VrainRainfallRevision, VrainRainfallInterval, VrainSyncRun, VrainSyncLease, VrainBackfillJob
from thongsothuyvan.vrain_history_services import sync_history, source_as_of, advance_backfill
from thongsothuyvan.vrain_history_views import VrainHistoryAPIView, VrainSummaryAPIView, VrainSyncStatusAPIView, VrainSourceSamplesAPIView


class ProviderTests(SimpleTestCase):
    def test_command_rejects_incomplete_or_naive_window(self):
        from django.core.management import call_command, CommandError
        with self.assertRaises(CommandError):
            call_command("sync_vrain_history", start="2026-01-01T00:00:00+07:00")
        with self.assertRaises(CommandError):
            call_command("sync_vrain_history", start="2026-01-01T00:00:00", end="2026-01-01T00:10:00")

    def test_numeric_quality_and_secret_allowlist(self):
        for value in [None, True, -1, "NaN", "Infinity", "bad", "0.00001"]:
            self.assertIsNone(rainfall(value))
        self.assertEqual(rainfall(0), 0)
        data=sanitize({"token":"secret", "Data":[{"station_id":"036606","number":"private", "value":[{"time_point":"2026-01-01 00:00:00","depth":0,"key":"secret"}]}]})
        self.assertNotIn("secret",str(data))
        self.assertNotIn("private",str(data))
        self.assertEqual(data["Data"][0]["station_id"], "036606")

    @override_settings(VRAIN_HISTORY_BASE_URL="https://attacker.example")
    def test_bad_host_never_called(self):
        with patch("thongsothuyvan.vrain_history_provider.requests.get") as get:
            with self.assertRaises(VrainHistoryError):
                fetch_history(timezone.now()-timedelta(hours=1),timezone.now())
            get.assert_not_called()

    @patch("thongsothuyvan.vrain_history_provider._get_api_key", return_value="test-only")
    @patch("thongsothuyvan.vrain_history_provider.time.sleep")
    @patch("thongsothuyvan.vrain_history_provider.requests.get")
    def test_retry_and_no_retry_auth(self,get,sleep,key):
        get.return_value=Mock(status_code=401)
        with self.assertRaisesRegex(VrainHistoryError,"http_401"):
            fetch_history(timezone.now()-timedelta(hours=1),timezone.now())
        self.assertEqual(get.call_count,1)
        get.reset_mock()
        get.return_value=Mock(status_code=429,headers={"Retry-After":"120"})
        with self.assertRaisesRegex(VrainHistoryError,"retry_deferred"):
            fetch_history(timezone.now()-timedelta(hours=1),timezone.now())
        self.assertEqual(get.call_count,1)
        sleep.assert_not_called()


@override_settings(VRAIN_HISTORY_ENABLED=True,VRAIN_INTERVAL_CONTRACT_VERIFIED=False)
class HistoryTests(TestCase):
    def setUp(self):
        VrainStation.objects.update(enabled=False)
        self.station=VrainStation.objects.update_or_create(source_station_code="036604", defaults={"name":"SH","plant":"songhinh","enabled":True})[0]
        self.start=datetime(2026,1,1,18,50,tzinfo=VN)
        self.end=self.start+timedelta(minutes=30)
        self.payload={"Data":[{"station_id":"036604","value":[{"time_point":(self.start+timedelta(minutes=10*i)).strftime("%Y-%m-%d %H:%M:%S"),"depth":value} for i,value in [(1,0),(2,1.2),(3,2.4)]]}]}

    def sync(self):
        with patch("thongsothuyvan.vrain_history_services.fetch_history",return_value=self.payload):
            return sync_history(self.start,self.end)

    def request(self,view,plant="songhinh",**params):
        user=SimpleNamespace(is_authenticated=True,is_superuser=False,profile=SimpleNamespace(can_view_realtime_hydrology=True,is_all_factories=False,nha_may=SimpleNamespace(ma_nha_may="SH")))
        req=APIRequestFactory().get("/",{"plant":plant,**params})
        force_authenticate(req,user=user)
        return view.as_view()(req)

    def test_unverified_capture_no_intervals_and_gate(self):
        self.assertEqual(self.sync()["status"],"captured_unverified")
        self.assertEqual(VrainSourceSample.objects.count(),3)
        self.assertFalse(VrainRainfallInterval.objects.exists())
        self.assertEqual(self.request(VrainSummaryAPIView).status_code,409)
        self.assertEqual(self.request(VrainSyncStatusAPIView).status_code,200)

    def test_idempotency_revision_and_as_of(self):
        self.sync()
        known=timezone.now()
        self.sync()
        self.assertEqual(VrainRainfallRevision.objects.count(),3)
        sample=VrainSourceSample.objects.order_by("source_timestamp").first()
        first_received=sample.first_received_at
        self.payload["Data"][0]["value"][0]["depth"]=5
        self.sync()
        sample.refresh_from_db()
        self.assertEqual(sample.first_received_at,first_received)
        self.assertEqual(VrainRainfallRevision.objects.count(),4)
        self.assertEqual(source_as_of(self.station,sample.source_timestamp,known).data["depth"],0)
        self.assertEqual(source_as_of(self.station,sample.source_timestamp,timezone.now()).data["depth"],5)

    @override_settings(VRAIN_INTERVAL_CONTRACT_VERIFIED=True)
    def test_verified_intervals_summary_and_missing(self):
        self.assertEqual(self.sync()["status"],"success")
        response=self.request(VrainSummaryAPIView,start=self.start.isoformat(),end=self.end.isoformat())
        summary=response.data["stations"][0]
        self.assertEqual(summary["valid_intervals"],3)
        self.assertTrue(summary["complete"])
        self.assertAlmostEqual(float(summary["rainfall_mm"]),3.6)
        VrainRainfallInterval.objects.order_by("interval_end").first().delete()
        summary=self.request(VrainSummaryAPIView,start=self.start.isoformat(),end=self.end.isoformat()).data["stations"][0]
        self.assertFalse(summary["complete"])
        self.assertIsNone(summary["rainfall_mm"])
        self.assertEqual(summary["valid_intervals"],2)

    @override_settings(VRAIN_INTERVAL_CONTRACT_VERIFIED=True)
    def test_missing_negative_offgrid_and_outside_are_not_zero(self):
        self.payload["Data"][0]["value"][1]["depth"]=-1
        self.payload["Data"][0]["value"].pop()
        self.payload["Data"][0]["value"].append({"time_point":"2026-01-01 19:11:00","depth":5})
        self.payload["Data"][0]["value"].append({"time_point":"2026-01-01 18:00:00","depth":10})
        result=self.sync()
        self.assertEqual(result["status"],"partial")
        self.assertEqual(result["counts"]["outside_window"],1)
        values=list(VrainRainfallInterval.objects.order_by("interval_end"))
        self.assertEqual([row.status for row in values],["valid","invalid","missing"])
        self.assertEqual(values[0].rainfall_mm,0)
        self.assertIsNone(values[1].rainfall_mm)
        self.assertIsNone(values[2].rainfall_mm)

    def test_conflicting_duplicate_rolls_back_preserves_evidence(self):
        self.payload["Data"][0]["value"].append({**self.payload["Data"][0]["value"][0],"depth":9})
        self.assertEqual(self.sync()["error_code"],"conflicting_duplicate")
        self.assertFalse(VrainSourceSample.objects.exists())
        self.assertTrue(VrainSyncRun.objects.get().evidence)

    def test_error_sanitized_retains_previous(self):
        self.sync()
        with patch("thongsothuyvan.vrain_history_services.fetch_history",side_effect=RuntimeError("secret")):
            result=sync_history(self.start,self.end)
        self.assertEqual(result["error_code"],"internal_error")
        self.assertEqual(VrainSourceSample.objects.count(),3)
        self.assertNotIn("secret",str(VrainSyncRun.objects.latest("pk").error_code))

    def test_disabled_lock_and_lost_lease(self):
        with override_settings(VRAIN_HISTORY_ENABLED=False),patch("thongsothuyvan.vrain_history_services.fetch_history") as fetch:
            self.assertEqual(sync_history()["status"],"disabled")
            fetch.assert_not_called()
        VrainSyncLease.objects.create(name="history",token="other",expires_at=timezone.now()+timedelta(minutes=5))
        self.assertEqual(self.sync()["status"],"locked")
        VrainSyncLease.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        def replacement(*args):
            VrainSyncLease.objects.update(token="replacement",expires_at=timezone.now()+timedelta(minutes=5))
            return self.payload
        with patch("thongsothuyvan.vrain_history_services.fetch_history",side_effect=replacement):
            self.assertEqual(sync_history(self.start,self.end)["error_code"],"lease_expired")
        self.assertEqual(VrainSyncLease.objects.get().token,"replacement")
        self.assertFalse(VrainSourceSample.objects.exists())

    def test_auth_scope_and_get_no_upstream(self):
        self.assertIn(VrainSyncStatusAPIView.as_view()(APIRequestFactory().get('/?plant=songhinh')).status_code,[401,403])
        VrainStation.objects.update_or_create(source_station_code="036616", defaults={"name":"VS","plant":"vinhson","enabled":True})
        self.assertEqual(self.request(VrainSyncStatusAPIView,"vinhson").status_code,403)
        with patch("thongsothuyvan.vrain_history_services.fetch_history") as fetch:
            response=self.request(VrainSyncStatusAPIView)
            self.assertEqual([s["code"] for s in response.data["stations"]],["036604"])
            self.assertEqual(response["Cache-Control"],"private, no-store")
            fetch.assert_not_called()

    @override_settings(VRAIN_INTERVAL_CONTRACT_VERIFIED=True)
    def test_utc_year_boundary_and_invalid_windows(self):
        self.start=datetime(2025,12,31,23,50,tzinfo=VN)
        self.end=self.start+timedelta(minutes=10)
        self.payload["Data"][0]["value"]=[{"time_point":"2026-01-01 00:00:00","depth":0}]
        self.sync()
        row=VrainRainfallInterval.objects.get()
        self.assertEqual(row.interval_end.hour,17)  # stored UTC
        self.assertEqual(row.interval_start.astimezone(VN).day,31)
        self.assertEqual(self.request(VrainHistoryAPIView,start="2026-01-01T00:00:00",end="2026-01-01T01:00:00").status_code,400)
        with self.assertRaises(VrainHistoryError):
            sync_history(self.start,self.end+timedelta(days=8))

    def test_backfill_bounded_cursor_and_error_resume(self):
        job=VrainBackfillJob.objects.create(window_start=self.start,window_end=self.start+timedelta(hours=2),cursor=self.start)
        with patch("thongsothuyvan.vrain_history_services.fetch_history",return_value=self.payload):
            advance_backfill(job)
        job.refresh_from_db()
        self.assertEqual(job.cursor,self.start+timedelta(hours=1))
        with patch("thongsothuyvan.vrain_history_services.fetch_history",side_effect=VrainHistoryError("http_500")):
            advance_backfill(job)
        job.refresh_from_db()
        self.assertEqual(job.cursor,self.start+timedelta(hours=1))
        self.assertEqual(job.status,"blocked")

    def test_source_matrix_zero_missing_invalid_and_no_network(self):
        other, _ = VrainStation.objects.update_or_create(source_station_code="036605", defaults={"name":"Other SH","plant":"songhinh","enabled":True})
        self.payload["Data"][0]["value"][1]["depth"]=-1
        self.sync()
        with patch("thongsothuyvan.vrain_history_services.fetch_history") as fetch:
            response = self.request(VrainSourceSamplesAPIView, start=self.start.isoformat(), end=(self.end+timedelta(minutes=1)).isoformat())
            fetch.assert_not_called()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response["Cache-Control"],"private, no-store")
        self.assertFalse(response.data["interval_verified"])
        self.assertEqual(response.data["total_timestamps"],3)
        self.assertEqual(response.data["results"][-1]["samples"]["036604"]["depth_mm"],0)
        self.assertIsNone(response.data["results"][1]["samples"]["036604"]["depth_mm"])
        self.assertNotIn("036605",response.data["results"][0]["samples"])
        self.assertEqual(len(response.data["stations"]),2)

    def test_source_matrix_auth_scope_bounds_and_station_filter(self):
        self.sync()
        args={"start":self.start.isoformat(),"end":self.end.isoformat()}
        self.assertEqual(self.request(VrainSourceSamplesAPIView,"vinhson",**args).status_code,403)
        self.assertEqual(self.request(VrainSourceSamplesAPIView,station="036616",**args).status_code,404)
        self.assertEqual(self.request(VrainSourceSamplesAPIView,page="0",**args).status_code,400)
        self.assertEqual(self.request(VrainSourceSamplesAPIView,start="2026-01-01T00:00:00",end="2026-01-01T01:00:00").status_code,400)
        self.assertEqual(self.request(VrainSourceSamplesAPIView,start=self.start.isoformat(),end=(self.start+timedelta(days=2)).isoformat()).status_code,400)
        response=self.request(VrainSourceSamplesAPIView,station="036604",**args)
        self.assertEqual([s["code"] for s in response.data["stations"]],["036604"])
        # Half-open source window excludes a sample exactly at end.
        self.assertEqual(response.data["total_timestamps"],2)

    def test_source_matrix_paginates_whole_timestamps(self):
        self.payload["Data"][0]["value"]=[{"time_point":(self.start+timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S"),"depth":i} for i in range(60)]
        with patch("thongsothuyvan.vrain_history_services.fetch_history",return_value=self.payload):
            sync_history(self.start,self.start+timedelta(hours=1))
        args={"start":self.start.isoformat(),"end":(self.start+timedelta(hours=1)).isoformat()}
        first=self.request(VrainSourceSamplesAPIView,**args).data
        second=self.request(VrainSourceSamplesAPIView,page="2",**args).data
        self.assertEqual(len(first["results"]),50)
        self.assertTrue(first["has_more"])
        self.assertEqual(len(second["results"]),10)
        self.assertFalse(second["has_more"])
        self.assertFalse({r["time_point"] for r in first["results"]} & {r["time_point"] for r in second["results"]})

    def test_source_matrix_tolerates_small_clock_skew_and_caps_at_server_now(self):
        self.sync()
        server_now = self.end - timedelta(minutes=1)
        with patch("thongsothuyvan.vrain_history_views.timezone.now", return_value=server_now):
            response = self.request(VrainSourceSamplesAPIView, start=self.start.isoformat(), end=self.end.isoformat())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["end"], server_now)
            self.assertEqual(response.data["total_timestamps"], 2)
            future = self.request(VrainSourceSamplesAPIView, start=self.start.isoformat(), end=(server_now+timedelta(minutes=6)).isoformat())
            self.assertEqual(future.status_code, 400)
            self.assertEqual(future.data["code"], "client_clock_ahead")
            too_long = self.request(VrainSourceSamplesAPIView, start=(server_now-timedelta(hours=25)).isoformat(), end=server_now.isoformat())
            self.assertEqual(too_long.status_code, 400)
            self.assertEqual(too_long.data["code"], "window_too_large")
