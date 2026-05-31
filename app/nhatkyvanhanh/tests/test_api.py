from datetime import date
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from nhatkyvanhanh.models import SogiaonhancaVH, SuKien

User = get_user_model()


class NhatKyVanHanhAPITests(APITestCase):
    def setUp(self):
        # Create factory/nha_may first
        self.nha_may = Bang_nha_may.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Sông Hinh",
        )

        # Create users
        self.creator = User.objects.create_user(
            email="creator@example.com",
            password="testpassword123!",
            username="creator",
        )
        self.receiver = User.objects.create_user(
            email="receiver@example.com",
            password="testpassword123!",
            username="receiver",
        )
        self.unprivileged_user = User.objects.create_user(
            email="unprivileged@example.com",
            password="testpassword123!",
            username="unprivileged",
        )

        # Create profiles with permissions and assigned factory
        self.creator_profile = UserProfile.objects.create(
            user=self.creator,
            ho_ten="Creator User",
            chu_ky="signatures/creator.png",
            nha_may=self.nha_may,
            can_view_shift_handover_logs=True,
            can_create_shift_handover_logs=True,
            can_view_operation_events=True,
            can_create_operation_events=True,
        )
        self.receiver_profile = UserProfile.objects.create(
            user=self.receiver,
            ho_ten="Receiver User",
            chu_ky="signatures/receiver.png",
            nha_may=self.nha_may,
            can_view_shift_handover_logs=True,
            can_receive_shift_handover_logs=True,
        )
        self.unprivileged_profile = UserProfile.objects.create(
            user=self.unprivileged_user,
            ho_ten="Unprivileged User",
            nha_may=self.nha_may,
            can_view_shift_handover_logs=False,
            can_create_shift_handover_logs=False,
            can_view_operation_events=False,
        )

    def test_nhatkysukien_list_permissions(self):
        url = reverse("nhatkyvanhanh:nhatkysukien-list")

        # 1. Anonymous user should be unauthorized
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Unprivileged user should be forbidden
        self.client.force_authenticate(user=self.unprivileged_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Privileged user should succeed
        self.client.force_authenticate(user=self.creator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sogiaonhancavh_shift_handover_flow(self):
        # 1. Create a shift handover log as self.creator
        self.client.force_authenticate(user=self.creator)
        create_url = reverse("nhatkyvanhanh:sogiaonhancavh-list")
        data = {
            "ngay_truc": str(date.today()),
            "ca_truc": "A",
            "dia_diem": "Phòng điều khiển trung tâm",
            "thoi_gian_giao_ca": timezone.now().isoformat(),
            "nha_may": self.nha_may.id,
        }
        response = self.client.post(create_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        so_id = response.data["id"]

        # 2. Try to sign shift log as self.receiver (should succeed to receive the shift)
        self.client.force_authenticate(user=self.receiver)
        ky_nhan_url = reverse("nhatkyvanhanh:sogiaonhancavh-ky-nhan-ca", kwargs={"pk": so_id})
        response = self.client.post(ky_nhan_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["nhan_ca_ky_at"])
        self.assertEqual(response.data["user_nhan_ca"], self.receiver.id)

        # 3. Try to finalize the handover (ky_giao_ca) as self.creator
        self.client.force_authenticate(user=self.creator)
        ky_giao_url = reverse("nhatkyvanhanh:sogiaonhancavh-ky-giao-ca", kwargs={"pk": so_id})
        response = self.client.post(ky_giao_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["giao_ca_ky_at"])
        self.assertEqual(response.data["trang_thai"], SogiaonhancaVH.TrangThai.HOAN_THANH)
