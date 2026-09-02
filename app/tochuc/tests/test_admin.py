from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from tablib import Dataset

from tochuc.admin import NhaMayAdmin, NhanSuAdmin
from tochuc.models import BoPhan, DonViToChuc, NhaMay, NhanSu
from tochuc.resources import NhaMayResource, NhanSuResource


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
        self.unit = DonViToChuc.objects.create(
            ma_don_vi="SH-ADMIN-UNIT",
            ten_don_vi="Quản lý vận hành",
            nha_may=self.plant,
        )
        self.department = BoPhan.objects.create(
            don_vi=self.unit,
            ma_bo_phan="VH-ADMIN",
            ten_bo_phan="Vận hành",
        )
        self.staff = NhanSu.objects.create(
            ho_ten="Nguyễn Văn Trực",
            ma_nhan_vien="NV-ADMIN-01",
            don_vi=self.unit,
            bo_phan=self.department,
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

    def test_factory_admin_belongs_to_tochuc_and_keeps_excel_resource(self):
        response = self.client.get(reverse("admin:tochuc_nhamay_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertIs(NhaMayAdmin.resource_class, NhaMayResource)

    def test_staff_admin_exposes_xlsx_import_and_export(self):
        changelist = self.client.get(reverse("admin:tochuc_nhansu_changelist"))
        import_page = self.client.get(reverse("admin:tochuc_nhansu_import"))
        export_page = self.client.get(reverse("admin:tochuc_nhansu_export"))

        self.assertEqual(changelist.status_code, 200)
        self.assertEqual(import_page.status_code, 200)
        self.assertEqual(export_page.status_code, 200)
        self.assertIs(NhanSuAdmin.resource_class, NhanSuResource)

    def test_staff_resource_exports_natural_organization_codes(self):
        dataset = NhanSuResource().export(NhanSu.objects.filter(pk=self.staff.pk))

        self.assertEqual(dataset.height, 1)
        row = dict(zip(dataset.headers, dataset[0]))
        self.assertEqual(row["ma_nha_may"], self.plant.ma_nha_may)
        self.assertEqual(row["ten_nha_may"], self.plant.ten_nha_may)
        self.assertEqual(row["ma_don_vi"], self.unit.ma_don_vi)
        self.assertEqual(row["ma_bo_phan"], self.department.ma_bo_phan)

    def test_staff_resource_imports_and_updates_by_employee_code(self):
        dataset = Dataset(headers=[
            "ma_nhan_vien",
            "ho_ten",
            "ma_nha_may",
            "ten_nha_may",
            "ma_don_vi",
            "ma_bo_phan",
            "username",
            "chuc_danh",
            "dien_thoai",
            "tu_ngay",
            "den_ngay",
            "dang_lam_viec",
        ])
        dataset.append([
            "NV-IMPORT-01",
            "Nguyễn Văn Ca",
            self.plant.ma_nha_may,
            self.plant.ten_nha_may,
            self.unit.ma_don_vi,
            self.department.ma_bo_phan,
            "",
            "Trực chính",
            "0900000000",
            "01/09/2026",
            "",
            True,
        ])

        result = NhanSuResource().import_data(dataset, dry_run=False, raise_errors=True)

        self.assertFalse(result.has_errors())
        imported = NhanSu.objects.get(ma_nhan_vien="NV-IMPORT-01")
        self.assertEqual(imported.ho_ten, "Nguyễn Văn Ca")
        self.assertEqual(imported.don_vi, self.unit)
        self.assertEqual(imported.bo_phan, self.department)

    def test_staff_resource_rejects_unit_from_another_factory_code(self):
        dataset = Dataset(headers=[
            "ma_nhan_vien",
            "ho_ten",
            "ma_nha_may",
            "ten_nha_may",
            "ma_don_vi",
        ])
        dataset.append([
            "NV-WRONG-PLANT",
            "Nhân sự sai nhà máy",
            "VS",
            "Vĩnh Sơn",
            self.unit.ma_don_vi,
        ])

        result = NhanSuResource().import_data(dataset, dry_run=True)

        self.assertTrue(result.has_errors())

    def test_staff_resource_reimports_legacy_row_without_employee_code(self):
        dataset = Dataset(headers=[
            "ma_nhan_vien",
            "ho_ten",
            "ma_nha_may",
            "ten_nha_may",
            "ma_don_vi",
            "ma_bo_phan",
            "chuc_danh",
        ])
        dataset.append([
            "",
            self.staff.ho_ten,
            self.plant.ma_nha_may,
            self.plant.ten_nha_may,
            self.unit.ma_don_vi,
            self.department.ma_bo_phan,
            "Trưởng ca",
        ])

        result = NhanSuResource().import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(NhanSu.objects.count(), 1)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.chuc_danh, "Trưởng ca")

    def test_staff_resource_maps_foreign_auto_code_to_matching_person(self):
        dataset = Dataset(headers=[
            "ma_nhan_vien",
            "ho_ten",
            "ma_nha_may",
            "ten_nha_may",
            "ma_don_vi",
            "ma_bo_phan",
            "chuc_danh",
        ])
        dataset.append([
            "NS-99999999",
            self.staff.ho_ten,
            self.plant.ma_nha_may,
            self.plant.ten_nha_may,
            self.unit.ma_don_vi,
            self.department.ma_bo_phan,
            "Trực chính",
        ])

        result = NhanSuResource().import_data(
            dataset,
            dry_run=False,
            raise_errors=True,
        )

        self.assertFalse(result.has_errors())
        self.assertEqual(NhanSu.objects.count(), 1)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.ma_nhan_vien, "NV-ADMIN-01")
        self.assertEqual(self.staff.chuc_danh, "Trực chính")

    def test_staff_resource_rejects_foreign_auto_code_collision(self):
        other = NhanSu.objects.create(
            ma_nhan_vien="NS-99999999",
            ho_ten="Nhân sự khác",
            don_vi=self.unit,
            bo_phan=self.department,
        )
        dataset = Dataset(headers=[
            "ma_nhan_vien",
            "ho_ten",
            "ma_nha_may",
            "ma_don_vi",
            "ma_bo_phan",
        ])
        dataset.append([
            other.ma_nhan_vien,
            "Người nhập từ môi trường khác",
            self.plant.ma_nha_may,
            self.unit.ma_don_vi,
            self.department.ma_bo_phan,
        ])

        result = NhanSuResource().import_data(dataset, dry_run=True)

        self.assertTrue(result.has_errors())
