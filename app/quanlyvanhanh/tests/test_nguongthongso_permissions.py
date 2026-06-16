from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import NguongThongSo


def profile_permission(user, field):
    if user.is_superuser:
        return True
    return bool(getattr(user.profile, field, False))


class NguongThongSoPermissionTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="nguong@example.com",
            username="nguong",
            password="testpass123",
        )
        self.profile = UserProfile.objects.create(user=self.user, is_all_factories=True)
        self.record = NguongThongSo.objects.create(
            nha_may="Song Hinh",
            ma_thong_so="muc_dau",
            ten_thong_so="Muc dau",
        )

    def authenticate(self, **permissions):
        for field, value in permissions.items():
            setattr(self.profile, field, value)
        self.profile.save()
        self.client.force_authenticate(self.user)

    @patch("quanlyvanhanh.views_nguongthongso.has_profile_permission", side_effect=profile_permission)
    def test_list_requires_view_permission(self, _permission_mock):
        self.authenticate(can_view_operation_thresholds=False)

        response = self.client.get(reverse("quanlyvanhanh:nguongthongso-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("quanlyvanhanh.views_nguongthongso.has_profile_permission", side_effect=profile_permission)
    def test_list_allows_view_permission(self, _permission_mock):
        self.authenticate(can_view_operation_thresholds=True)

        response = self.client.get(reverse("quanlyvanhanh:nguongthongso-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("quanlyvanhanh.views_nguongthongso.has_profile_permission", side_effect=profile_permission)
    def test_create_requires_create_permission(self, _permission_mock):
        payload = {
            "nha_may": "Song Hinh",
            "ma_thong_so": "ap_luc",
            "ten_thong_so": "Ap luc",
        }
        self.authenticate(can_create_operation_thresholds=False)

        response = self.client.post(
            reverse("quanlyvanhanh:nguongthongso-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(can_create_operation_thresholds=True)
        response = self.client.post(
            reverse("quanlyvanhanh:nguongthongso-list"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("quanlyvanhanh.views_nguongthongso.has_profile_permission", side_effect=profile_permission)
    def test_update_requires_edit_permission(self, _permission_mock):
        self.authenticate(can_edit_operation_thresholds=False)

        response = self.client.patch(
            reverse("quanlyvanhanh:nguongthongso-detail", args=[self.record.id]),
            {"alarm": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(can_edit_operation_thresholds=True)
        response = self.client.patch(
            reverse("quanlyvanhanh:nguongthongso-detail", args=[self.record.id]),
            {"alarm": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.record.refresh_from_db()
        self.assertEqual(self.record.alarm, 10)

    @patch("quanlyvanhanh.views_nguongthongso.has_profile_permission", side_effect=profile_permission)
    def test_delete_requires_delete_permission(self, _permission_mock):
        self.authenticate(can_delete_operation_thresholds=False)

        response = self.client.delete(
            reverse("quanlyvanhanh:nguongthongso-detail", args=[self.record.id]),
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(can_delete_operation_thresholds=True)
        response = self.client.delete(
            reverse("quanlyvanhanh:nguongthongso-detail", args=[self.record.id]),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class NguongThongSoFactoryScopeTests(APITestCase):
    def setUp(self):
        self.vs_factory = Bang_nha_may.objects.create(ma_nha_may="VS", ten_nha_may="Vinh Son")
        self.sh_factory = Bang_nha_may.objects.create(ma_nha_may="SH", ten_nha_may="Song Hinh")

        User = get_user_model()
        self.vs_user = User.objects.create_user(
            email="nguong-vs@example.com",
            username="nguong_vs",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.vs_user,
            nha_may=self.vs_factory,
            can_view_operation_thresholds=True,
            can_create_operation_thresholds=True,
        )

        self.vs_record = NguongThongSo.objects.create(
            nha_may="Vinh Son",
            ma_thong_so="vs_metric",
            ten_thong_so="VS metric",
        )
        self.sh_record = NguongThongSo.objects.create(
            nha_may="Song Hinh",
            ma_thong_so="sh_metric",
            ten_thong_so="SH metric",
        )

    def test_list_is_scoped_to_user_factory(self):
        self.client.force_authenticate(self.vs_user)

        response = self.client.get(reverse("quanlyvanhanh:nguongthongso-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data["results"]}
        self.assertIn(self.vs_record.id, ids)
        self.assertNotIn(self.sh_record.id, ids)

    def test_create_uses_user_factory_scope(self):
        self.client.force_authenticate(self.vs_user)

        response = self.client.post(
            reverse("quanlyvanhanh:nguongthongso-list"),
            {
                "nha_may": "Song Hinh",
                "ma_thong_so": "created_metric",
                "ten_thong_so": "Created metric",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = NguongThongSo.objects.get(ma_thong_so="created_metric")
        self.assertEqual(created.nha_may, "Vinh Son")
