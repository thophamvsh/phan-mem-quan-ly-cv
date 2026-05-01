from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.factory_scope import filter_queryset_by_factory
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi, ThongSoVanHanh


class FactoryScopeTests(TestCase):
    def setUp(self):
        self.vs = Bang_nha_may.objects.create(ma_nha_may="VS", ten_nha_may="Vinh Son")
        self.sh = Bang_nha_may.objects.create(ma_nha_may="SH", ten_nha_may="Song Hinh")

        self.user = get_user_model().objects.create_user(
            email="vs@example.com",
            password="testpass123",
            username="vsuser",
        )
        UserProfile.objects.create(user=self.user, nha_may=self.vs)

        self.vs_device = ThietBi.objects.create(
            ten="To may H1 VS",
            ma="VS.TB.H1",
            ma_day_du="VS.TB.H1",
            nha_may="",
        )
        self.sh_device = ThietBi.objects.create(
            ten="To may H1 SH",
            ma="SH.TB.H1",
            ma_day_du="SH.TB.H1",
            nha_may="Song Hinh",
        )

    def test_string_scope_matches_device_code_prefix(self):
        scoped = filter_queryset_by_factory(
            ThietBi.objects.order_by("ma_day_du"),
            self.user,
            "nha_may",
            "string",
        )

        self.assertEqual(list(scoped), [self.vs_device])

    def test_string_scope_matches_related_device_code_prefix(self):
        now = timezone.now()
        vs_param = ThongSoVanHanh.objects.create(
            thiet_bi=self.vs_device,
            ma_thong_so="p",
            ten_thong_so="P",
            gia_tri="1",
            thoi_diem_nhap=now,
            ngay_nhap=now.date(),
            nha_may="",
        )
        ThongSoVanHanh.objects.create(
            thiet_bi=self.sh_device,
            ma_thong_so="p",
            ten_thong_so="P",
            gia_tri="2",
            thoi_diem_nhap=now,
            ngay_nhap=now.date(),
            nha_may="Song Hinh",
        )

        scoped = filter_queryset_by_factory(
            ThongSoVanHanh.objects.order_by("id"),
            self.user,
            "nha_may",
            "string",
        )

        self.assertEqual(list(scoped), [vs_param])
