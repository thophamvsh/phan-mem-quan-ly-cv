import io
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from openpyxl import Workbook, load_workbook

from core.models import UserProfile
from tochuc.models import NhaMay
from quanlyvanhanh.models import ThietBi, ThongSoVanHanh, ThongSoToMay, ThongSoTram110KV
from quanlyvanhanh.configs.operation_configs import get_tram_factory_config


class OwnershipPermissionTests(APITestCase):
    def setUp(self):
        # Create factories
        self.sh_factory = NhaMay.objects.create(ma_nha_may="SH", ten_nha_may="Song Hinh")

        # Create users
        self.user_a = get_user_model().objects.create_user(
            email="usera@example.com",
            password="testpass123",
            username="usera"
        )
        # Give permission to edit operation parameters
        self.profile_a = UserProfile.objects.create(
            user=self.user_a,
            nha_may=self.sh_factory,
            can_edit_operation_parameters=True,
            can_delete_operation_parameters=True,
            can_import_excel=True,
            can_export_excel=True,
        )

        self.user_b = get_user_model().objects.create_user(
            email="userb@example.com",
            password="testpass123",
            username="userb"
        )
        self.profile_b = UserProfile.objects.create(
            user=self.user_b,
            nha_may=self.sh_factory,
            can_edit_operation_parameters=True,
            can_delete_operation_parameters=True,
            can_import_excel=True,
            can_export_excel=True,
        )

        self.superuser = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password="testpass123",
            username="admin"
        )
        self.profile_admin = UserProfile.objects.create(
            user=self.superuser,
            nha_may=self.sh_factory,
            can_edit_operation_parameters=True,
            can_delete_operation_parameters=True,
            can_import_excel=True,
            can_export_excel=True,
        )

        # Create devices
        self.sh_device = ThietBi.objects.create(
            ten="Tổ máy H1",
            ma="SH.TB.H1",
            ma_day_du="SH.TB.H1",
            nha_may="Song Hinh"
        )
        self.sh_ge = ThietBi.objects.create(
            ten="Tổ máy H1 GE",
            ma="GE",
            ma_day_du="SH.TB.H1.GE",
            nha_may="Song Hinh",
            cha=self.sh_device
        )

        # Common datetime
        self.now = timezone.now()

    def _create_excel_file(self, rows):
        wb = Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'test.xlsx'
        return buf

    def test_thong_so_van_hanh_crud_ownership(self):
        # 1. Create using User A
        self.client.force_authenticate(user=self.user_a)
        url = reverse('quanlyvanhanh:thongsovanhanh-list')
        data = {
            "thiet_bi": self.sh_device.id,
            "ma_thong_so": "dien_ap_kich_tu_h1",
            "ten_thong_so": "Điện áp kích từ H1",
            "gia_tri": "120",
            "don_vi": "V",
            "thoi_diem_nhap": self.now.isoformat(),
            "ngay_nhap": "2026-06-11",
            "nha_may": "Song Hinh"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        record = ThongSoVanHanh.objects.get(
            thiet_bi=self.sh_device,
            ma_thong_so="dien_ap_kich_tu_h1",
            ngay_nhap="2026-06-11"
        )
        record_id = record.id
        self.assertEqual(record.nguoi_nhap, self.user_a)

        # 2. Try to update using User B (should be forbidden)
        self.client.force_authenticate(user=self.user_b)
        detail_url = reverse('quanlyvanhanh:thongsovanhanh-detail', kwargs={'pk': record_id})
        update_data = {
            "gia_tri": "130"
        }
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Try to delete using User B (should be forbidden)
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Update using User A (should be allowed)
        self.client.force_authenticate(user=self.user_a)
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['gia_tri'], "130")

        # 5. Delete using Superuser (should be allowed)
        self.client.force_authenticate(user=self.superuser)
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ThongSoVanHanh.objects.filter(id=record_id).exists())

    def test_thong_so_to_may_crud_ownership(self):
        # 1. Create using User A
        self.client.force_authenticate(user=self.user_a)
        url = reverse('quanlyvanhanh:thongsotomay-list')
        data = {
            "thiet_bi": self.sh_ge.id,
            "ma_thong_so": "ap_luc_nuoc",
            "ten_thong_so": "Áp lực nước",
            "don_vi": "bar",
            "gia_tri": "5.5",
            "thoi_diem_nhap": self.now.isoformat(),
            "ngay_nhap": "2026-06-11",
            "nha_may": "Song Hinh"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        record = ThongSoToMay.objects.get(
            thiet_bi=self.sh_ge,
            ma_thong_so="ap_luc_nuoc",
            ngay_nhap="2026-06-11"
        )
        record_id = record.id
        self.assertEqual(record.nguoi_nhap, self.user_a)

        # 2. Try to update using User B (should be forbidden)
        self.client.force_authenticate(user=self.user_b)
        detail_url = reverse('quanlyvanhanh:thongsotomay-detail', kwargs={'pk': record_id})
        update_data = {
            "gia_tri": "6.0"
        }
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Try to delete using User B (should be forbidden)
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Update using User A (should be allowed)
        self.client.force_authenticate(user=self.user_a)
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 5. Delete using User A (should be allowed)
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_thong_so_tram_crud_ownership(self):
        # 1. Create using User A
        self.client.force_authenticate(user=self.user_a)
        url = reverse('quanlyvanhanh:thongsotram110kv-list')
        data = {
            "thiet_bi": self.sh_device.id,
            "ma_thong_so": "ap_luc_khi_sf6",
            "ten_thong_so": "Áp lực khí SF6",
            "don_vi": "bar",
            "gia_tri": "6.5",
            "thoi_diem_nhap": self.now.isoformat(),
            "ngay_nhap": "2026-06-11",
            "nha_may": "Song Hinh"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        record = ThongSoTram110KV.objects.get(
            thiet_bi=self.sh_device,
            ma_thong_so="ap_luc_khi_sf6",
            ngay_nhap="2026-06-11"
        )
        record_id = record.id

        # 2. Try to update using User B (should be forbidden)
        self.client.force_authenticate(user=self.user_b)
        detail_url = reverse('quanlyvanhanh:thongsotram110kv-detail', kwargs={'pk': record_id})
        update_data = {
            "gia_tri": "7.0"
        }
        response = self.client.patch(detail_url, update_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Try to delete using User B (should be forbidden)
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Delete using Superuser (should be allowed)
        self.client.force_authenticate(user=self.superuser)
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_by_day_ownership(self):
        # Create records belonging to User A
        rec1 = ThongSoVanHanh.objects.create(
            thiet_bi=self.sh_device,
            ma_thong_so="dien_ap_kich_tu_h1",
            ten_thong_so="Điện áp kích từ H1",
            thoi_diem_nhap=self.now,
            ngay_nhap="2026-06-11",
            nguoi_nhap=self.user_a
        )
        rec2 = ThongSoToMay.objects.create(
            thiet_bi=self.sh_ge,
            ten_thong_so="Áp lực nước",
            ma_thong_so="ap_luc_nuoc",
            don_vi="bar",
            thoi_diem_nhap=self.now,
            ngay_nhap="2026-06-11",
            nguoi_nhap=self.user_a
        )
        rec3 = ThongSoTram110KV.objects.create(
            thiet_bi=self.sh_device,
            ten_thong_so="Áp lực khí SF6",
            ma_thong_so="ap_luc_khi_sf6",
            don_vi="bar",
            thoi_diem_nhap=self.now,
            ngay_nhap="2026-06-11",
            nguoi_nhap=self.user_a
        )

        # User B attempts to delete by day (should fail)
        self.client.force_authenticate(user=self.user_b)
        
        response = self.client.delete(reverse('quanlyvanhanh:thongsovanhanh-delete-by-day') + '?ngay=2026-06-11')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        response = self.client.delete(reverse('quanlyvanhanh:thongsotomay-delete-by-day') + '?ngay=2026-06-11')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        response = self.client.delete(reverse('quanlyvanhanh:thongsotram110kv-delete-by-day') + '?ngay=2026-06-11')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # User A attempts to delete by day (should succeed)
        self.client.force_authenticate(user=self.user_a)
        response = self.client.delete(reverse('quanlyvanhanh:thongsovanhanh-delete-by-day') + '?ngay=2026-06-11')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(reverse('quanlyvanhanh:thongsotomay-delete-by-day') + '?ngay=2026-06-11')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.delete(reverse('quanlyvanhanh:thongsotram110kv-delete-by-day') + '?ngay=2026-06-11')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_delete_by_day_requires_and_respects_factory_scope(self):
        vs_factory = NhaMay.objects.create(
            ma_nha_may="VS",
            ten_nha_may="Vinh Son",
        )
        vs_device = ThietBi.objects.create(
            ten="To may H1 Vinh Son",
            ma="VS.TB.H1",
            ma_day_du="VS.TB.H1",
            nha_may=vs_factory.ten_nha_may,
        )
        for device, factory_name in (
            (self.sh_device, self.sh_factory.ten_nha_may),
            (vs_device, vs_factory.ten_nha_may),
        ):
            ThongSoVanHanh.objects.create(
                thiet_bi=device,
                ma_thong_so="dien_ap",
                ten_thong_so="Dien ap",
                thoi_diem_nhap=self.now,
                ngay_nhap="2026-06-12",
                nha_may=factory_name,
                nguoi_nhap=self.superuser,
            )

        self.client.force_authenticate(user=self.superuser)
        url = reverse("quanlyvanhanh:thongsovanhanh-delete-by-day")

        response = self.client.delete(f"{url}?ngay=2026-06-12")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            ThongSoVanHanh.objects.filter(ngay_nhap="2026-06-12").count(),
            2,
        )

        response = self.client.delete(
            f"{url}?ngay=2026-06-12&factory_code=SH"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ThongSoVanHanh.objects.filter(
                ngay_nhap="2026-06-12",
                thiet_bi=self.sh_device,
            ).exists()
        )
        self.assertTrue(
            ThongSoVanHanh.objects.filter(
                ngay_nhap="2026-06-12",
                thiet_bi=vs_device,
            ).exists()
        )

    def test_superuser_export_respects_factory_scope(self):
        vs_factory = NhaMay.objects.create(
            ma_nha_may="VS",
            ten_nha_may="Vinh Son",
        )
        vs_device = ThietBi.objects.create(
            ten="To may H1 Vinh Son",
            ma="VS.TB.H1",
            ma_day_du="VS.TB.H1",
            nha_may=vs_factory.ten_nha_may,
        )
        for device, factory_name in (
            (self.sh_device, self.sh_factory.ten_nha_may),
            (vs_device, vs_factory.ten_nha_may),
        ):
            ThongSoVanHanh.objects.create(
                thiet_bi=device,
                ma_thong_so="dien_ap",
                ten_thong_so="Dien ap",
                gia_tri="110",
                thoi_diem_nhap=self.now,
                ngay_nhap="2026-06-13",
                nha_may=factory_name,
                nguoi_nhap=self.superuser,
            )

        self.client.force_authenticate(user=self.superuser)
        url = reverse("quanlyvanhanh:export_thong_so")
        response = self.client.get(f"{url}?date=2026-06-13&format=xlsx")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get(
            f"{url}?date=2026-06-13&format=xlsx&factory_code=SH"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workbook = load_workbook(io.BytesIO(response.content), read_only=True)
        rows = list(workbook.active.iter_rows(values_only=True))
        flattened = " ".join(
            str(value)
            for row in rows
            for value in row
            if value is not None
        )
        self.assertIn("SH.TB.H1", flattened)
        self.assertNotIn("VS.TB.H1", flattened)
    def test_excel_import_overwriting_forbidden(self):
        # Create a record belonging to User A
        ThongSoVanHanh.objects.create(
            thiet_bi=self.sh_device,
            ma_thong_so="dien_ap_kich_tu_h1",
            ten_thong_so="Điện áp kích từ H1",
            thoi_diem_nhap=self.now,
            ngay_nhap="2026-06-11",
            nguoi_nhap=self.user_a
        )

        # User B tries to import Excel which covers the same date/factory
        self.client.force_authenticate(user=self.user_b)
        url = reverse('quanlyvanhanh:excel_import')

        # Construct basic 48-slot Song Hinh layout row data (3 headers + 48 rows)
        headers = [["header"] * 34, ["header"] * 34, ["header"] * 34]
        values = [111, 222, 333, 444, 555, 666, 777] + [900 + i for i in range(27)]
        data_rows = [values[:] for _ in range(48)]
        excel_buf = self._create_excel_file(headers + data_rows)

        response = self.client.post(url, {
            'file': excel_buf,
            'selected_date': '2026-06-11',
            'factory_code': 'SH',
        }, format='multipart')

        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Bạn không có quyền cập nhật thông số', response.json()['error'])
