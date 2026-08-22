from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from khovattu.models import Bang_nha_may
from nhatkyvanhanh.serializers import (
    SogiaonhancaHCSerializer,
    SogiaonhancaVHSerializer,
)


class ShiftHandoverSerializerTimeTests(TestCase):
    def setUp(self):
        self.plant = Bang_nha_may.objects.create(
            ma_nha_may="TEST-SHIFT",
            ten_nha_may="Nhà máy kiểm thử giao nhận ca",
        )

    def _assert_rejects_invalid_range(self, serializer_class, extra_data=None):
        start = timezone.now()
        serializer = serializer_class(
            data={
                "ngay_truc": start.date().isoformat(),
                "nha_may": self.plant.pk,
                "thoi_gian_bat_dau_ca": start.isoformat(),
                "thoi_gian_giao_ca": (start - timedelta(minutes=1)).isoformat(),
                **(extra_data or {}),
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("thoi_gian_giao_ca", serializer.errors)

    def test_vh_rejects_handover_before_shift_start(self):
        self._assert_rejects_invalid_range(
            SogiaonhancaVHSerializer,
            {"ca_truc": "A"},
        )

    def test_hc_rejects_handover_before_shift_start(self):
        self._assert_rejects_invalid_range(SogiaonhancaHCSerializer)
