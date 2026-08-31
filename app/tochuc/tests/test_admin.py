from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tochuc.models import BoPhan, DonViToChuc, NhaMay, NhanSu


class NhanSuAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="organization-admin",
            email="organization-admin@example.com",
            password="test-pass-123",
        )
        self.plant = NhaMay.objects.create(
            ma_nha_may="SH-ADMIN",
            ten_nha_may="Sông Hinh",
        )
        unit = DonViToChuc.objects.create(
            ma_don_vi="SH-ADMIN-UNIT",
            ten_don_vi="Quản lý vận hành",
            nha_may=self.plant,
        )
        department = BoPhan.objects.create(
            don_vi=unit,
            ma_bo_phan="VH-ADMIN",
            ten_bo_phan="Vận hành",
        )
        self.staff = NhanSu.objects.create(
            ho_ten="Nguyễn Văn Trực",
            don_vi=unit,
            bo_phan=department,
        )
        self.client.force_login(self.admin_user)

    def test_staff_changelist_renders_with_factory_filter(self):
        response = self.client.get(reverse("admin:tochuc_nhansu_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff.ho_ten)
        self.assertContains(response, self.plant.ten_nha_may)

    def test_staff_changelist_filters_by_factory(self):
        response = self.client.get(
            reverse("admin:tochuc_nhansu_changelist"),
            {"nha_may": self.plant.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.staff.ho_ten)
