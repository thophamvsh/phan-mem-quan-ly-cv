from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from tochuc.models import NhaMay
from nhatkyvanhanh.serializers import (
    ChiTietSoGiaoNhanCaHCSerializer,
    NguoiTrucSoGiaoNhanCaHCSerializer,
    SogiaonhancaHCSerializer,
    SogiaonhancaVHSerializer,
)


class ShiftHandoverSerializerTimeTests(TestCase):
    def setUp(self):
        self.plant = NhaMay.objects.create(
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

    def test_hc_detail_rejects_end_before_start(self):
        start = timezone.now()
        serializer = ChiTietSoGiaoNhanCaHCSerializer(
            data={
                "thoi_gian": start.isoformat(),
                "thoi_gian_bat_dau": start.isoformat(),
                "thoi_gian_ket_thuc": (start - timedelta(minutes=1)).isoformat(),
                "noi_dung": "Kiểm tra công việc hành chính",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("thoi_gian_ket_thuc", serializer.errors)

    def test_hc_duty_person_rejects_end_before_start(self):
        start = timezone.now()
        serializer = NguoiTrucSoGiaoNhanCaHCSerializer(
            data={
                "thoi_gian": start.isoformat(),
                "thoi_gian_bat_dau": start.isoformat(),
                "thoi_gian_ket_thuc": (start - timedelta(minutes=1)).isoformat(),
                "ten_nguoi_truc": "Nguyễn Văn A",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("thoi_gian_ket_thuc", serializer.errors)
