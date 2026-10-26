import io,json
from datetime import datetime,timedelta,date
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.core.management import call_command,CommandError
from thongsothuyvan.models import ThongSoThuyVanThucTe
from thongsothuyvan.inflow_b0_models import InflowB0Forecast,InflowB0Run,InflowB0Evaluation
from thongsothuyvan.inflow_b0_services import publish_b0,reconcile_b0,b0_report,VN


@override_settings(INFLOW_B0_SH_ENABLED=False,INFLOW_B0_SH_MAX_SOURCE_AGE_DAYS=2)
class B0ShadowTests(TestCase):
    def setUp(self):
        self.now=datetime(2026,1,3,7,30,tzinfo=VN)
        self.source=self.actual(date(2026,1,2),100,datetime(2026,1,3,7,tzinfo=VN))

    def actual(self,day,value,received):
        row=ThongSoThuyVanThucTe.objects.create(nha_may="songhinh",ngay=day,qve=value)
        ThongSoThuyVanThucTe.objects.filter(pk=row.pk).update(created_at=received,updated_at=received)
        row.refresh_from_db();return row

    def publish(self,**kwargs):
        with patch("thongsothuyvan.inflow_b0_services.timezone.now",return_value=self.now):
            return publish_b0(manual=True,**kwargs)

    def reconcile(self,when=None,**kwargs):
        with patch("thongsothuyvan.inflow_b0_services.timezone.now",return_value=when or self.now):
            return reconcile_b0(manual=True,**kwargs)

    def test_disabled_schedule_no_writes_and_manual_dry_run(self):
        self.assertEqual(publish_b0()["status"],"disabled")
        self.assertEqual(reconcile_b0()["status"],"disabled")
        self.assertEqual(self.publish(dry_run=True)["predicted_qve"],100)
        self.assertEqual(InflowB0Forecast.objects.count(),0)
        self.assertEqual(InflowB0Run.objects.count(),0)

    def test_prospective_idempotent_snapshot_unchanged_after_source_correction(self):
        first=self.publish();self.assertEqual(first["status"],"published")
        forecast=InflowB0Forecast.objects.get()
        self.assertEqual(forecast.target_day,date(2026,1,4))
        self.assertEqual(forecast.issued_at,self.now)
        self.assertLess(forecast.issued_at,forecast.target_start)
        ThongSoThuyVanThucTe.objects.filter(pk=self.source.pk).update(qve=200)
        self.assertEqual(self.publish()["status"],"already_exists")
        forecast.refresh_from_db()
        self.assertEqual(forecast.predicted_qve,100)
        self.assertEqual(forecast.source_snapshot["qve"],100)
        self.assertEqual(InflowB0Forecast.objects.count(),1)
        self.assertEqual(InflowB0Run.objects.count(),2)
        with patch("thongsothuyvan.inflow_b0_services.timezone.now",return_value=self.now):
            report=b0_report()
        self.assertEqual(report["results"][0]["status"],"target_not_ended")
        self.assertEqual(report["results"][0]["prediction"],100)
        self.assertEqual(report["scored"],0)

    def test_no_today_future_or_late_received_source(self):
        self.source.delete()
        self.actual(date(2026,1,3),500,self.now-timedelta(minutes=1))
        self.actual(date(2026,1,2),300,self.now+timedelta(minutes=1))
        result=self.publish()
        self.assertEqual(result["status"],"unavailable")
        self.assertFalse(InflowB0Forecast.objects.exists())
        # A later genuine retry may publish after the report actually arrives.
        self.now+=timedelta(minutes=2)
        self.assertEqual(self.publish()["predicted_qve"],300)

    def test_stale_invalid_and_zero_source(self):
        self.now+=timedelta(days=5)
        self.assertEqual(self.publish()["status"],"unavailable")
        self.now=datetime(2026,1,3,7,30,tzinfo=VN)
        for value in [None,-1]:
            ThongSoThuyVanThucTe.objects.filter(pk=self.source.pk).update(qve=value)
            self.assertEqual(self.publish()["status"],"unavailable")
        ThongSoThuyVanThucTe.objects.filter(pk=self.source.pk).update(qve=0)
        self.assertEqual(self.publish()["predicted_qve"],0)

    def test_reconciliation_waits_for_target_end_and_actual_then_revises(self):
        self.publish()
        self.assertEqual(self.reconcile()["checked"],0)
        ended=datetime(2026,1,5,7,45,tzinfo=VN)
        self.assertEqual(self.reconcile(ended)["missing_actual"],1)
        actual=self.actual(date(2026,1,4),80,ended-timedelta(minutes=20))
        self.assertEqual(self.reconcile(ended)["verified"],1)
        self.assertEqual(self.reconcile(ended)["new_revisions"],0)
        evaluation=InflowB0Evaluation.objects.order_by("-revision").first()
        self.assertEqual(evaluation.signed_error,20)
        self.assertEqual(evaluation.volume_error_m3,20*86400)
        ThongSoThuyVanThucTe.objects.filter(pk=actual.pk).update(qve=110,updated_at=ended+timedelta(minutes=1))
        self.reconcile(ended+timedelta(minutes=2))
        self.assertEqual(InflowB0Evaluation.objects.count(),3)
        self.assertEqual(InflowB0Evaluation.objects.order_by("-revision").first().signed_error,-10)
        self.assertEqual(InflowB0Forecast.objects.get().predicted_qve,100)
        report=b0_report()
        self.assertEqual(report["scored"],1)
        self.assertEqual(report["mae"],10)
        self.assertEqual(report["bias"],-10)
        self.assertIsNone(report["nse"])

    def test_invalid_actual_does_not_reuse_old_score(self):
        self.publish();ended=datetime(2026,1,5,8,tzinfo=VN)
        actual=self.actual(date(2026,1,4),80,ended-timedelta(minutes=1))
        self.reconcile(ended)
        ThongSoThuyVanThucTe.objects.filter(pk=actual.pk).update(qve=None)
        self.reconcile(ended+timedelta(minutes=1))
        report=b0_report()
        self.assertEqual(report["scored"],0)
        self.assertEqual(report["invalid_actual"],1)
        self.assertIsNone(report["mae"])

    def test_target_filter_limit_and_reconciliation_fairness(self):
        self.publish()
        self.now+=timedelta(days=1)
        self.actual(date(2026,1,3),120,self.now-timedelta(minutes=1))
        self.publish()
        ended=datetime(2026,1,8,8,tzinfo=VN)
        self.reconcile(ended,limit=1)
        self.reconcile(ended+timedelta(minutes=1),limit=1)
        self.assertEqual(InflowB0Evaluation.objects.count(),2)
        with self.assertRaises(ValueError):self.reconcile(ended,target_day=date(2026,1,8))
        with self.assertRaises(ValueError):self.reconcile(ended,limit=0)

    def test_manual_commands_no_backdating_parameter_and_read_report(self):
        out=io.StringIO()
        with patch("thongsothuyvan.inflow_b0_services.timezone.now",return_value=self.now):
            call_command("publish_inflow_b0_sh",dry_run=True,stdout=out)
        self.assertEqual(json.loads(out.getvalue())["status"],"dry_run")
        with self.assertRaises(TypeError):call_command("publish_inflow_b0_sh",issue_date="2025-01-01")
        with self.assertRaises(CommandError):call_command("reconcile_inflow_b0_sh",target_date="bad",stdout=io.StringIO())
        output=io.StringIO();call_command("report_inflow_b0_sh",stdout=output)
        self.assertEqual(json.loads(output.getvalue())["scored"],0)

    def test_failure_records_safe_error_without_forecast(self):
        with patch("thongsothuyvan.inflow_b0_services.InflowB0Forecast.objects.get_or_create",side_effect=RuntimeError("secret")):
            result=self.publish()
        self.assertEqual(result["error_code"],"internal_error")
        self.assertFalse(InflowB0Forecast.objects.exists())
        self.assertNotIn("secret",str(InflowB0Run.objects.get().details))

    def test_actual_value_reverts_preserving_all_revisions(self):
        self.publish();ended=datetime(2026,1,5,8,tzinfo=VN)
        actual=self.actual(date(2026,1,4),80,ended-timedelta(minutes=1))
        self.reconcile(ended)
        for value in [110,80]:
            ThongSoThuyVanThucTe.objects.filter(pk=actual.pk).update(qve=value)
            self.reconcile(ended+timedelta(minutes=1))
        self.assertEqual(list(InflowB0Evaluation.objects.order_by("revision").values_list("actual_qve",flat=True)),[80,110,80])
        self.assertEqual(b0_report()["scored"],1)


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connections
from django.test import TransactionTestCase,skipUnlessDBFeature


@skipUnlessDBFeature("has_select_for_update")
class B0ConcurrencyTests(TransactionTestCase):
    @override_settings(INFLOW_B0_SH_ENABLED=False,INFLOW_B0_SH_MAX_SOURCE_AGE_DAYS=2)
    def test_two_publishers_produce_one_forecast(self):
        now=datetime(2026,1,3,7,30,tzinfo=VN)
        row=ThongSoThuyVanThucTe.objects.create(nha_may="songhinh",ngay=date(2026,1,2),qve=100)
        ThongSoThuyVanThucTe.objects.filter(pk=row.pk).update(created_at=now-timedelta(minutes=1),updated_at=now-timedelta(minutes=1))
        barrier=Barrier(2)
        def publish():
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                return publish_b0(manual=True)
            finally:
                connections.close_all()
        with patch("thongsothuyvan.inflow_b0_services.timezone.now",return_value=now),ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(publish) for _ in range(2)]
            results=[future.result(timeout=20) for future in futures]
        self.assertEqual(sorted(r["status"] for r in results),["already_exists","published"])
        self.assertEqual(InflowB0Forecast.objects.count(),1)
