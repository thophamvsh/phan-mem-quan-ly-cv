from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from tochuc.models import NhaMay
from core.models import UserProfile
from ..models.phan_cong_nhiem_vu_hc import BangPhanCongNhiemVuHC, ChiTietNhiemVuThuTrongTuan


User = get_user_model()


class BangPhanCongNhiemVuHCTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="admin@example.com",
            username="admin_user",
            password="StrongPassword123!",
            first_name="Admin",
            last_name="Test",
        )
        self.profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={
                "can_view_admin_shift_duty_rosters": True,
                "can_create_admin_shift_duty_rosters": True,
                "can_edit_admin_shift_duty_rosters": True,
                "can_delete_admin_shift_duty_rosters": True,
            }
        )
        self.profile.can_view_admin_shift_duty_rosters = True
        self.profile.can_create_admin_shift_duty_rosters = True
        self.profile.can_edit_admin_shift_duty_rosters = True
        self.profile.can_delete_admin_shift_duty_rosters = True
        self.profile.save()
        self.plant = NhaMay.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Nhà máy TĐ Sông Hinh",
        )
        self.client.force_authenticate(user=self.user)

    def test_lay_mau_mac_dinh(self):
        url = reverse("nhatkyvanhanh:phancongnhiemvuhc-lay-mau-mac-dinh")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["chi_tiets"]), 7)
        self.assertIn("Thứ 2", response.data["chi_tiets"][0]["thu"])

    def test_create_bang_phan_cong_with_default_items(self):
        url = reverse("nhatkyvanhanh:phancongnhiemvuhc-list")
        data = {
            "nha_may": self.plant.id,
            "thang": 7,
            "nam": 2026,
            "tieu_de": "BẢNG PHÂN LÀM VỆ SINH CA KT-VH THÁNG 07/2026",
            "dia_diem_lap": "Sông Hinh",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["thang"], 7)
        self.assertEqual(response.data["nam"], 2026)
        self.assertEqual(len(response.data["chi_tiets"]), 7)
        self.assertEqual(BangPhanCongNhiemVuHC.objects.count(), 1)
        self.assertEqual(ChiTietNhiemVuThuTrongTuan.objects.count(), 7)

    def test_unique_constraint_same_month(self):
        BangPhanCongNhiemVuHC.objects.create(
            nha_may=self.plant,
            thang=7,
            nam=2026,
            tieu_de="Bản tháng 7",
            nguoi_tao=self.user,
        )
        url = reverse("nhatkyvanhanh:phancongnhiemvuhc-list")
        data = {
            "nha_may": self.plant.id,
            "thang": 7,
            "nam": 2026,
            "tieu_de": "Bản tháng 7 trùng",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sao_chep_thang(self):
        roster = BangPhanCongNhiemVuHC.objects.create(
            nha_may=self.plant,
            thang=7,
            nam=2026,
            tieu_de="Bảng Tháng 07/2026",
            ghi_chu="Ghi chú tháng 7",
            nguoi_tao=self.user,
        )
        ChiTietNhiemVuThuTrongTuan.objects.create(
            bang_phan_cong=roster,
            stt=1,
            thu="Thứ 2",
            noi_dung_nhiem_vu="Nhiệm vụ riêng thứ 2 tháng 7",
        )

        url = reverse("nhatkyvanhanh:phancongnhiemvuhc-sao-chep-thang")
        data = {
            "nha_may": self.plant.id,
            "tu_thang": 7,
            "tu_nam": 2026,
            "den_thang": 8,
            "den_nam": 2026,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["thang"], 8)
        self.assertEqual(response.data["ghi_chu"], "Ghi chú tháng 7")
        self.assertEqual(len(response.data["chi_tiets"]), 1)
        self.assertEqual(
            response.data["chi_tiets"][0]["noi_dung_nhiem_vu"],
            "Nhiệm vụ riêng thứ 2 tháng 7",
        )

    def test_permission_denied_when_cannot_create(self):
        self.profile.can_create_admin_shift_duty_rosters = False
        self.profile.save()

        url = reverse("nhatkyvanhanh:phancongnhiemvuhc-list")
        data = {
            "nha_may": self.plant.id,
            "thang": 9,
            "nam": 2026,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)