from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from tochuc.models import BoPhan, DonViToChuc, NhaMay


User = get_user_model()


def create_user(username, plant, **permissions):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="test-pass-123",
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nha_may = plant
    for field, value in permissions.items():
        setattr(profile, field, value)
    profile.save()
    return user


class OrganizationDirectoryAPITests(APITestCase):
    def setUp(self):
        self.song_hinh = NhaMay.objects.create(
            ma_nha_may="SH-API",
            ten_nha_may="Sông Hinh",
        )
        self.vinh_son = NhaMay.objects.create(
            ma_nha_may="VS-API",
            ten_nha_may="Vĩnh Sơn",
        )
        self.song_hinh_unit = DonViToChuc.objects.create(
            ma_don_vi="SH-UNIT",
            ten_don_vi="Quản lý vận hành SH",
            nha_may=self.song_hinh,
        )
        self.vinh_son_unit = DonViToChuc.objects.create(
            ma_don_vi="VS-UNIT",
            ten_don_vi="Quản lý vận hành VS",
            nha_may=self.vinh_son,
        )
        self.song_hinh_department = BoPhan.objects.create(
            don_vi=self.song_hinh_unit,
            ma_bo_phan="VH",
            ten_bo_phan="Vận hành",
        )

    def test_viewer_only_sees_own_factory(self):
        user = create_user(
            "org-viewer",
            self.song_hinh,
            can_view_organization_directory=True,
        )
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/tochuc/don-vi/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["id"] for item in response.data},
            {self.song_hinh_unit.id},
        )

    def test_user_without_related_permission_is_denied(self):
        user = create_user("org-denied", self.song_hinh)
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/tochuc/don-vi/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_create_in_own_factory_but_not_another_factory(self):
        user = create_user(
            "org-manager",
            self.song_hinh,
            can_manage_organization_directory=True,
        )
        self.client.force_authenticate(user)

        own_response = self.client.post(
            "/api/v1/tochuc/don-vi/",
            {
                "ma_don_vi": "SH-NEW",
                "ten_don_vi": "Đơn vị mới SH",
                "nha_may": self.song_hinh.id,
            },
            format="json",
        )
        other_response = self.client.post(
            "/api/v1/tochuc/don-vi/",
            {
                "ma_don_vi": "VS-NEW",
                "ten_don_vi": "Đơn vị mới VS",
                "nha_may": self.vinh_son.id,
            },
            format="json",
        )

        self.assertEqual(own_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(other_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_marks_department_inactive_and_options_hide_it(self):
        user = create_user(
            "org-soft-delete",
            self.song_hinh,
            can_manage_organization_directory=True,
        )
        self.client.force_authenticate(user)

        delete_response = self.client.delete(
            f"/api/v1/tochuc/bo-phan/{self.song_hinh_department.id}/"
        )
        options_response = self.client.get(
            f"/api/v1/tochuc/bo-phan/options/?don_vi={self.song_hinh_unit.id}"
        )
        self.song_hinh_department.refresh_from_db()

        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.song_hinh_department.dang_hoat_dong)
        self.assertEqual(options_response.status_code, status.HTTP_200_OK)
        self.assertEqual(options_response.data, [])

    def test_legacy_shift_endpoint_uses_same_shared_records(self):
        user = create_user(
            "legacy-org-viewer",
            self.song_hinh,
            can_view_shift_schedule=True,
        )
        self.client.force_authenticate(user)

        shared_response = self.client.get("/api/v1/tochuc/don-vi/")
        legacy_response = self.client.get("/api/v1/quanlycatruc/don-vi/")

        self.assertEqual(shared_response.status_code, status.HTTP_200_OK)
        self.assertEqual(legacy_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item["id"] for item in shared_response.data},
            {item["id"] for item in legacy_response.data},
        )
