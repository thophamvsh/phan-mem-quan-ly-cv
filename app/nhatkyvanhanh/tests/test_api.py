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
        self.viewer = User.objects.create_user(
            email="viewer@example.com",
            password="testpassword123!",
            username="viewer",
        )
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="testpassword123!",
            username="manager",
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
            can_edit_own_operation_events=True,
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
        self.viewer_profile = UserProfile.objects.create(
            user=self.viewer,
            ho_ten="View Only User",
            nha_may=self.nha_may,
            can_view_shift_handover_logs=True,
            can_create_shift_handover_logs=False,
            can_edit_shift_handover_logs=False,
            can_delete_shift_handover_logs=False,
            can_view_operation_events=True,
            can_edit_own_operation_events=False,
            can_edit_all_operation_events=False,
            can_delete_own_operation_events=False,
            can_delete_all_operation_events=False,
        )
        self.manager_profile = UserProfile.objects.create(
            user=self.manager,
            ho_ten="Manager User",
            nha_may=self.nha_may,
            can_view_operation_events=True,
            can_edit_all_operation_events=True,
            can_delete_all_operation_events=True,
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

    def test_nhatkysukien_viewer_cannot_update_or_delete(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.viewer)
        patch_response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated by viewer"},
            format="json",
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nhatkysukien_creator_can_update_before_acknowledged(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated by creator"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["hien_tuong_dien_bien"], "Updated by creator")

    def test_nhatkysukien_creator_cannot_update_after_acknowledged(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
            ben_ghi_nhan_su_kien=self.receiver,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated after acknowledged"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nhatkysukien_creator_cannot_update_after_completed(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
            ben_ghi_nhan_su_kien=self.receiver,
            trang_thai=SuKien.TrangThaiXuLy.XU_LY_XONG,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated after completed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nhatkysukien_other_user_with_edit_all_cannot_update(self):
        event = SuKien.objects.create(
            nha_may=self.nha_may,
            thoi_gian_xay_ra=timezone.now(),
            ten_he_thong_thiet_bi="H1",
            hien_tuong_dien_bien="Test event",
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:nhatkysukien-detail", kwargs={"pk": event.id})

        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            detail_url,
            {"hien_tuong_dien_bien": "Updated by manager"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

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

    def test_sogiaonhancavh_viewer_cannot_update_or_delete(self):
        so = SogiaonhancaVH.objects.create(
            nha_may=self.nha_may,
            ngay_truc=date.today(),
            ca_truc=SogiaonhancaVH.CaTruc.A,
            thoi_gian_giao_ca=timezone.now(),
            user_giao_ca=self.creator,
            nguoi_tao=self.creator,
        )
        detail_url = reverse("nhatkyvanhanh:sogiaonhancavh-detail", kwargs={"pk": so.id})

        self.client.force_authenticate(user=self.viewer)
        patch_response = self.client.patch(
            detail_url,
            {"dia_diem": "Updated by viewer"},
            format="json",
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)
