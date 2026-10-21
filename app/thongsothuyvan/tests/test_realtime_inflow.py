from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

from thongsothuyvan.realtime_inflow import calculate_inflow


class InflowFormulaTests(TestCase):
    def calculate(self, seconds=1800, start=(1,), end=(1.018,), flows=(10, 30, 2, 4)):
        time = datetime(2026, 10, 20, tzinfo=timezone.utc)
        return calculate_inflow(time, time + timedelta(seconds=seconds), start, end, *flows)

    def test_actual_intervals_and_average_flows(self):
        for seconds in (1800, 3600, 7200):
            value, meta = self.calculate(seconds=seconds)
            self.assertAlmostEqual(value, 18000 / seconds + 20 + 3)
            self.assertEqual(meta["interval_seconds"], seconds)

    def test_three_reservoirs_and_internal_transfer(self):
        value, _ = self.calculate(start=(1, 2, 3), end=(1.1, 1.9, 3))
        self.assertAlmostEqual(value, 23)  # transfer cancels; Qcm/spill counted once
        value, _ = self.calculate(start=(1, 2, 3), end=(1.018, 2.018, 3.018))
        self.assertAlmostEqual(value, 53)

    def test_missing_invalid_and_timestamps(self):
        for seconds in (0, -1800):
            value, meta = self.calculate(seconds=seconds)
            self.assertIsNone(value)
            self.assertEqual(meta["status"], "non_increasing_timestamp")
        for missing in (None, float("nan"), float("inf")):
            self.assertIsNone(self.calculate(end=(missing,))[0])
            self.assertIsNone(self.calculate(flows=(missing, 0, 0, 0))[0])
        value, meta = calculate_inflow(None, datetime.now(timezone.utc), [], [1], None, 0, None, 0)
        self.assertIsNone(value)
        self.assertEqual(meta["status"], "no_previous_sample")

    def test_negative_result_preserved(self):
        value, meta = self.calculate(end=(0.9,), flows=(0, 0, 0, 0))
        self.assertLess(value, 0)
        self.assertTrue(meta["negative_result"])


class InflowSnapshotTests(TestCase):
    def test_strict_interpolation_rejects_out_of_range_and_preserves_precision(self):
        from decimal import Decimal
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from thongsothuyvan.realtime_services import get_capacity_by_level
        table = MagicMock()
        lower = SimpleNamespace(Mucnuoc=Decimal("100"), dungtich=Decimal("1"))
        upper = SimpleNamespace(Mucnuoc=Decimal("101"), dungtich=Decimal("1.001"))
        table.objects.filter.return_value.order_by.return_value.first.side_effect = [lower, upper]
        self.assertAlmostEqual(get_capacity_by_level(table, 100.5, strict=True), 1.0005)
        table.objects.filter.return_value.order_by.return_value.first.side_effect = [None, upper]
        self.assertIsNone(get_capacity_by_level(table, 99, strict=True))

    def test_service_sets_fields_and_keeps_source(self):
        from thongsothuyvan.models import SongHinhRealtimeSnapshot, VinhSonRealtimeSnapshot
        from thongsothuyvan.realtime_services import save_snapshot_with_inflow
        from thongsothuyvan.serializers import (
            SongHinhRealtimeSnapshotSerializer, VinhSonRealtimeSnapshotSerializer,
        )
        now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        for model, serializer, levels in (
            (SongHinhRealtimeSnapshot, SongHinhRealtimeSnapshotSerializer, {"mntl": 199}),
            (VinhSonRealtimeSnapshot, VinhSonRealtimeSnapshotSerializer,
             {"mntla": 760, "mntlb": 820, "mntlc": 970}),
        ):
            previous = model(time_stamp=now, qcm=20, qtran=0, **levels)
            current = model(time_stamp=now + timedelta(minutes=30), qcm=20, qtran=0,
                            raw_data={"Qve": 999}, **levels)
            count = len(levels)
            with (
                patch.object(model, "objects") as objects,
                patch.object(model, "save") as save,
                patch("thongsothuyvan.realtime_services.get_capacity_by_level",
                      side_effect=[1] * count + [1.018] * count) as capacity,
            ):
                objects.order_by.return_value.first.return_value = previous
                save_snapshot_with_inflow(current)
                self.assertAlmostEqual(current.qve_tinh_toan, 20 + count * 10)
                self.assertEqual(current.raw_data, {"Qve": 999})
                self.assertEqual(capacity.call_count, count * 2)
                self.assertTrue(all(call.kwargs["strict"] for call in capacity.call_args_list))
                save.assert_called_once()
                self.assertIn("qve_tinh_toan", serializer(current).data)
