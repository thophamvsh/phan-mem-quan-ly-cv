from datetime import date,timedelta,datetime,timezone
from django.test import SimpleTestCase
from django.core.management import CommandError
from thongsothuyvan.inflow_audit import candidate_events,distribution,compare_daily
from thongsothuyvan.management.commands.audit_inflow_sh import group_days,Command


class InflowAuditTests(SimpleTestCase):
    def test_event_threshold_bridge_and_missing(self):
        d=date(2025,1,1)
        values={d:301,d+timedelta(days=1):100,d+timedelta(days=2):500,d+timedelta(days=4):400,d+timedelta(days=5):300}
        events=candidate_events(values,300,1)
        self.assertEqual(len(events),2)
        self.assertEqual(events[0]["days_above_threshold"],2)
        self.assertEqual(events[0]["peak_qve"],500)
        self.assertEqual(events[0]["span_days"],3)
        self.assertEqual(len(candidate_events(values,300,0)),3)

    def test_distribution_filters_missing_without_changing_zero(self):
        result=distribution([None,float("nan"),True,-1,0,1,9])
        self.assertEqual(result["finite"],4)
        self.assertEqual(result["zero"],1)
        self.assertEqual(result["negative"],1)
        self.assertEqual(result["p50"],.5)
        self.assertIsNone(distribution([])["p99"])

    def test_comparison_reports_difference_and_excludes_invalid(self):
        d=date(2025,1,1)
        result=compare_daily({d:100,d+timedelta(days=1):None},{d:120,d+timedelta(days=1):20})
        self.assertEqual(result["compared_finite"],1)
        self.assertEqual(result["mean_absolute_difference"],20)
        self.assertEqual(result["exceeds_review_tolerance"],1)

    def test_group_days_converts_vietnam_and_excludes_duplicates(self):
        values,duplicates=group_days([{"t":datetime(2025,1,1,17,tzinfo=timezone.utc),"q":1},{"t":datetime(2025,1,2,0,tzinfo=timezone.utc),"q":2}],"t","q")
        self.assertEqual(values,{})
        self.assertEqual(duplicates,["2025-01-02"])

    def test_audit_handle_rejects_invalid_configuration(self):
        for kwargs in [{"threshold":-1},{"threshold":float("nan")},{"bridge_days":8}]:
            with self.assertRaises(CommandError):
                Command().handle(**{"threshold":300,"bridge_days":1,**kwargs})
