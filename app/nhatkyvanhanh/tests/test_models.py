from datetime import date
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from nhatkyvanhanh.models import (
    SogiaonhancaVH,
    Sonhatkyvanhanh,
    SoChuyenDoiThietBiTuan,
)

User = get_user_model()


class NhatKyVanHanhModelTests(TestCase):
    def setUp(self):
        # Create users
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            password="testpassword123!",
            username="user1",
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com",
            password="testpassword123!",
            username="user2",
        )

        # Create profiles with signatures
        self.profile1 = UserProfile.objects.create(
            user=self.user1,
            ho_ten="User One",
            chu_ky="signatures/user1.png",
        )
        self.profile2 = UserProfile.objects.create(
            user=self.user2,
            ho_ten="User Two",
            chu_ky="signatures/user2.png",
        )

        # Create factory/nha_may
        self.nha_may = Bang_nha_may.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Sông Hinh",
        )

    def test_sogiaonhancavh_validations(self):
        # Validation: user_giao_ca must be the creator (nguoi_tao)
        so_vh = SogiaonhancaVH(
            ngay_truc=date.today(),
            nha_may=self.nha_may,
            ca_truc="A",
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.user1,
            nguoi_tao=self.user2,  # Different user
        )
        with self.assertRaises(ValidationError) as ctx:
            so_vh.full_clean()
        self.assertIn("user_giao_ca", ctx.exception.message_dict)

        # Validation: user_nhan_ca must be different from user_giao_ca
        so_vh = SogiaonhancaVH(
            ngay_truc=date.today(),
            nha_may=self.nha_may,
            ca_truc="A",
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.user1,
            user_nhan_ca=self.user1,  # Same user
            nguoi_tao=self.user1,
        )
        with self.assertRaises(ValidationError) as ctx:
            so_vh.full_clean()
        self.assertIn("user_nhan_ca", ctx.exception.message_dict)

    def test_sogiaonhancavh_signature_sync(self):
        # Save SogiaonhancaVH and check signature synchronization
        so_vh = SogiaonhancaVH(
            ngay_truc=date.today(),
            nha_may=self.nha_may,
            ca_truc="A",
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.user1,
            nguoi_tao=self.user1,
            giao_ca_ky_at=timezone.now(),
        )
        so_vh.save()
        self.assertEqual(so_vh.chu_ky_user_giao_ca, "signatures/user1.png")

        # Confirm receipt and sign
        so_vh.user_nhan_ca = self.user2
        so_vh.nhan_ca_ky_at = timezone.now()
        so_vh.save()
        self.assertEqual(so_vh.chu_ky_user_nhan_ca, "signatures/user2.png")
        self.assertEqual(so_vh.trang_thai, SogiaonhancaVH.TrangThai.HOAN_THANH)

    def test_sonhatkyvanhanh_validations(self):
        # Validation: creator and confirmer must be different
        logbook = Sonhatkyvanhanh(
            nha_may=self.nha_may,
            noi_dung_tao="Test operational log",
            nguoi_tao=self.user1,
            nguoi_xac_nhan=self.user1,  # Same user
            xac_nhan_at=timezone.now(),
        )
        with self.assertRaises(ValidationError) as ctx:
            logbook.full_clean()
        self.assertIn("nguoi_xac_nhan", ctx.exception.message_dict)

    def test_sochuyendoithietbituan_time_calculation(self):
        # Weekly equipment switch calculation test
        so_tuan = SoChuyenDoiThietBiTuan(
            nam=2026,
            tuan=22,
            ca_truc="A",
            nha_may=self.nha_may,
            nguoi_tao=self.user1,
        )
        so_tuan.save()

        # ISO year 2026, week 22 starts on Monday, May 25, 2026 and ends on Sunday, May 31, 2026
        self.assertEqual(so_tuan.tuan_bat_dau, date(2026, 5, 25))
        self.assertEqual(so_tuan.tuan_ket_thuc, date(2026, 5, 31))
