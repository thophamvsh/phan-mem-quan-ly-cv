import io
import pandas as pd
import tablib
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from quanlyvanhanh.admin import ThietBiResource
from quanlyvanhanh.configs.operation_configs import get_tram_factory_config
from quanlyvanhanh.models import ThietBi, ThongSoTram110KV, ThongSoVanHanh, ThongSoToMay
from openpyxl import Workbook


class ExcelImportTests(APITestCase):
    def setUp(self):
        # Create factories
        self.sh_factory = Bang_nha_may.objects.create(ma_nha_may="SH", ten_nha_may="Song Hinh")

        # Create user
        self.user = get_user_model().objects.create_user(
            email="sh@example.com",
            password="testpass123",
            username="shuser"
        )
        UserProfile.objects.create(user=self.user, nha_may=self.sh_factory)

        # Create devices
        self.h1_device = ThietBi.objects.create(
            ten="Tổ máy H1",
            ma="SH.TB.H1",
            ma_day_du="SH.TB.H1",
            nha_may="Song Hinh"
        )
        self.h1_ge = ThietBi.objects.create(
            ten="Tổ máy H1 GE",
            ma="GE",
            nha_may="Song Hinh",
            cha=self.h1_device
        )

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

    def test_thietbi_resource_import_sorts_parent_before_child(self):
        dataset = tablib.Dataset(headers=["ma_day_du", "ten", "nha_may"])
        dataset.append(("VS.TB.H9.GE.OD", "OD", "VS"))
        dataset.append(("VS.TB.H9", "Root H9", "VS"))
        dataset.append(("VS.TB.H9.GE", "GE", "VS"))

        result = ThietBiResource().import_data(dataset, dry_run=False, raise_errors=True)

        self.assertFalse(result.has_errors())
        root = ThietBi.objects.get(ma_day_du="VS.TB.H9")
        ge = ThietBi.objects.get(ma_day_du="VS.TB.H9.GE")
        od = ThietBi.objects.get(ma_day_du="VS.TB.H9.GE.OD")
        self.assertIsNone(root.cha_id)
        self.assertEqual(root.ma, "VS.TB.H9")
        self.assertEqual(ge.cha_id, root.id)
        self.assertEqual(ge.ma, "GE")
        self.assertEqual(od.cha_id, ge.id)
        self.assertEqual(od.ma, "OD")

    def test_thietbi_resource_import_auto_creates_missing_parent(self):
        dataset = tablib.Dataset(headers=["ma_day_du", "ten", "nha_may"])
        dataset.append(("VS.TB.H10.GE", "GE", "VS"))

        result = ThietBiResource().import_data(dataset, dry_run=False, raise_errors=True)

        self.assertFalse(result.has_errors())
        parent = ThietBi.objects.get(ma_day_du="VS.TB.H10")
        child = ThietBi.objects.get(ma_day_du="VS.TB.H10.GE")
        self.assertIsNone(parent.cha_id)
        self.assertEqual(parent.ma, "VS.TB.H10")
        self.assertEqual(parent.ten, "VS.TB.H10")
        self.assertEqual(child.cha_id, parent.id)
        self.assertEqual(child.ma, "GE")

    def _dien_rows(self, include_index_column=False):
        headers = [["header"] * 34, ["header"] * 34, ["header"] * 34]
        values = [111, 222, 333, 444, 555, 666, 777] + [900 + i for i in range(26)]
        data_rows = []
        for idx in range(1, 49):
            row = values[:]
            if include_index_column:
                row = [idx] + row
            data_rows.append(row)
        return headers + data_rows

    def test_excel_import_dien_legacy_template_keeps_column_a(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:excel_import')
        excel_buf = self._create_excel_file(self._dien_rows(include_index_column=False))

        response = self.client.post(url, {
            'file': excel_buf,
            'selected_date': '2026-06-09',
            'factory_code': 'SH',
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_param = ThongSoVanHanh.objects.filter(
            thiet_bi=self.h1_device,
            ngay_nhap='2026-06-09',
            ma_thong_so='dien_ap_kich_tu_h1',
        ).order_by('thoi_diem_nhap').first()

        self.assertIsNotNone(first_param)
        self.assertEqual(first_param.gia_tri, '111')

    def test_excel_import_dien_new_template_drops_index_column(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:excel_import')
        excel_buf = self._create_excel_file(self._dien_rows(include_index_column=True))

        response = self.client.post(url, {
            'file': excel_buf,
            'selected_date': '2026-06-10',
            'factory_code': 'SH',
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first_param = ThongSoVanHanh.objects.filter(
            thiet_bi=self.h1_device,
            ngay_nhap='2026-06-10',
            ma_thong_so='dien_ap_kich_tu_h1',
        ).order_by('thoi_diem_nhap').first()

        self.assertIsNotNone(first_param)
        self.assertEqual(first_param.gia_tri, '111')

    def test_excel_import_h1_fuzzy_matching(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:excel_import_tomay')

        # H1 mong đợi 3 hàng header, sau đó là 24 hàng dữ liệu
        # Hàng 1: "THÔNG SỐ H1"
        # Hàng 2: Tên thông số H1 (sử dụng một số lỗi viết sai nhỏ để test fuzzy matching)
        # Hàng 3: Đơn vị
        headers_row1 = ["THÔNG SỐ H1"] + [""] * 19
        headers_row2 = [
            "Ap luc nuoc",  # Lỗi viết không dấu của "Áp lực nước"
            "Áp lực chèn trục",
            "Lưu lượng chèn trục",
            "Lưu lượng ổ hướng tuabin",
            "Nhiệt độ ổ hướng tuabin",
            "Lưu lượng ổ hướng máy phát",
            "Nhiệt độ ổ hướng máy phát",
            "Lưu lượng ổ đỡ máy phát",
            "Nhiệt độ ổ đỡ",
            "Nhiệt độ ổ hướng - ổ đỡ",
            "Nhiệt độ đầu ổ đỡ",
            "Lưu lượng làm mát máy phát",
            "Nhiệt độ nước làm mát máy phát",
            "Nhiệt độ khí mát",
            "Nhiệt độ khí nóng",
            "Nhiệt độ cuộn dây stato",
            "Tốc độ",
            "Giới hạn độ mở cánh hướng",
            "Độ mở cánh hướng",
            "Độ rơi tốc"
        ]
        headers_row3 = ["bar"] * 20
        
        # 24 dòng dữ liệu (00:00 đến 23:00)
        data_rows = []
        for hour in range(24):
            data_rows.append([5.5] + [1.2] * 19)

        excel_buf = self._create_excel_file([headers_row1, headers_row2, headers_row3] + data_rows)

        response = self.client.post(url, {
            'file': excel_buf,
            'selected_date': '2026-05-31',
            'device_code': 'SH.TB.H1.GE'
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Import thành công', response.json()['message'])

        # Xác minh các bản ghi được ghi hàng loạt thành công xuống DB (24 dòng * 20 cột = 480 bản ghi)
        count = ThongSoToMay.objects.filter(thiet_bi=self.h1_ge, ngay_nhap='2026-05-31').count()
        self.assertEqual(count, 480)

    def test_excel_import_h2_validation(self):
        self.client.force_authenticate(user=self.user)
        # Tạo thiết bị H2
        self.h2_device = ThietBi.objects.create(
            ten="Tổ máy H2",
            ma="SH.TB.H2",
            ma_day_du="SH.TB.H2",
            nha_may="Song Hinh"
        )
        self.h2_ge = ThietBi.objects.create(
            ten="Tổ máy H2 GE",
            ma="GE",
            nha_may="Song Hinh",
            cha=self.h2_device
        )

        url = reverse('quanlyvanhanh:excel_import_tomay_h2')

        headers_row1 = ["THÔNG SỐ H2"] + [""] * 19
        headers_row2 = [
            "Áp lực nước", "Áp lực chèn trục", "Lưu lượng chèn trục", "Lưu lượng ổ hướng tuabin",
            "Nhiệt độ ổ hướng tuabin", "Lưu lượng ổ hướng máy phát", "Nhiệt độ ổ hướng máy phát",
            "Lưu lượng ổ đỡ máy phát", "Nhiệt độ ổ đỡ", "Nhiệt độ ổ hướng - ổ đỡ",
            "Nhiệt độ đầu ổ đỡ", "Lưu lượng làm mát máy phát", "Nhiệt độ nước làm mát máy phát",
            "Nhiệt độ khí mát", "Nhiệt độ khí nóng", "Nhiệt độ cuộn dây stato",
            "Tốc độ", "Giới hạn độ mở cánh hướng", "Độ mở cánh hướng", "Độ rơi tốc"
        ]
        headers_row3 = ["bar"] * 20
        
        data_rows = [[5.5] + [1.2] * 19] * 24

        excel_buf = self._create_excel_file([headers_row1, headers_row2, headers_row3] + data_rows)

        response = self.client.post(url, {
            'file': excel_buf,
            'selected_date': '2026-05-31',
            'device_code': 'SH.TB.H2.GE'
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Import thành công', response.json()['message'])
        
        count = ThongSoToMay.objects.filter(thiet_bi=self.h2_ge, ngay_nhap='2026-05-31').count()
        self.assertEqual(count, 480)

    def test_excel_import_mismatch_error(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:excel_import_tomay')  # H1 import

        # File Excel của H2
        headers_row1 = ["THÔNG SỐ H2"] + [""] * 19
        headers_row2 = [
            "Áp lực nước", "Áp lực chèn trục", "Lưu lượng chèn trục", "Lưu lượng ổ hướng tuabin",
            "Nhiệt độ ổ hướng tuabin", "Lưu lượng ổ hướng máy phát", "Nhiệt độ ổ hướng máy phát",
            "Lưu lượng ổ đỡ máy phát", "Nhiệt độ ổ đỡ", "Nhiệt độ ổ hướng - ổ đỡ",
            "Nhiệt độ đầu ổ đỡ", "Lưu lượng làm mát máy phát", "Nhiệt độ nước làm mát máy phát",
            "Nhiệt độ khí mát", "Nhiệt độ khí nóng", "Nhiệt độ cuộn dây stato",
            "Tốc độ", "Giới hạn độ mở cánh hướng", "Độ mở cánh hướng", "Độ rơi tốc"
        ]
        headers_row3 = ["bar"] * 20
        data_rows = [[5.5] + [1.2] * 19] * 24

        excel_buf = self._create_excel_file([headers_row1, headers_row2, headers_row3] + data_rows)

        # Upload file H2 nhưng truyền device_code H1 (hoặc gọi API import H1)
        response = self.client.post(url, {
            'file': excel_buf,
            'selected_date': '2026-05-31',
            'device_code': 'SH.TB.H1.GE'
        }, format='multipart')

        # Phải trả về lỗi 400 Bad Request do lệch tổ máy
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('không khớp với tổ máy được chọn', response.json()['error'])

    def test_excel_import_tram_uses_dynamic_config_mapping(self):
        self.client.force_authenticate(user=self.user)
        config = get_tram_factory_config("SH")
        columns = config["columns"]

        def ensure_device_tree(code):
            parent = None
            current_parts = []
            for part in code.split("."):
                current_parts.append(part)
                parent, _ = ThietBi.objects.get_or_create(
                    cha=parent,
                    ma=part,
                    defaults={
                        "ten": ".".join(current_parts),
                        "nha_may": "Song Hinh",
                    },
                )
            return parent

        for column in columns:
            ensure_device_tree(column["ma_thiet_bi"])

        rows = [
            [config["title"]] + [""] * (len(columns) - 1),
            [column["ten"] for column in columns],
            [column["don_vi"] for column in columns],
        ]
        for row_idx in range(12):
            rows.append([row_idx * 100 + col_idx for col_idx in range(len(columns))])

        excel_buf = self._create_excel_file(rows)
        response = self.client.post(
            reverse("quanlyvanhanh:excel_import_tram"),
            {
                "file": excel_buf,
                "selected_date": "2026-06-11",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["imported_count"], 216)

        first_column = columns[0]
        first_record = ThongSoTram110KV.objects.get(
            ma_thong_so=first_column["ma"],
            thiet_bi__ma_day_du=first_column["ma_thiet_bi"],
            ngay_nhap="2026-06-11",
            thoi_diem_nhap__hour=0,
        )
        self.assertEqual(first_record.gia_tri, "0")
        self.assertEqual(first_record.nha_may, "Song Hinh")

    def test_device_import_excel_standard(self):
        self.client.force_authenticate(user=self.user)
        profile = self.user.profile
        profile.can_create_equipment = True
        profile.save()

        # Standard template import
        headers = [
            "Mã thiết bị (*)",
            "Mã đầy đủ thiết bị chi tiết cha",
            "Tên thiết bị (*)",
            "Loại/Phân loại",
            "Trạng thái",
            "Nhà chế tạo",
            "Nhà cung cấp",
            "Nước sản xuất",
            "Nhà máy (*)",
            "Mã vận hành",
            "Bộ phận quản lý",
            "Bảng vẽ",
            "Thông số kỹ thuật",
            "Ngày lắp đặt (YYYY-MM-DD)",
            "Ngày vận hành (YYYY-MM-DD)"
        ]
        row_data = [
            "PD.02",
            "SH.TB.H1",
            "Phân phối dầu tổ máy 02",
            "Thiết bị phụ",
            "Hoạt động",
            "Alstom",
            "Alstom Vietnam",
            "Pháp",
            "SH",
            "2-OPD",
            "Phân xưởng vận hành",
            "SH-H1-GE-02",
            "Áp lực định mức 40 bar",
            "2026-01-15",
            "2026-02-01"
        ]
        excel_buf = self._create_excel_file([headers, row_data])

        url = reverse("quanlyvanhanh:thietbi-import-excel")
        response = self.client.post(url, {'file': excel_buf}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify device was created
        device = ThietBi.objects.filter(ma_day_du="SH.TB.H1.PD.02").first()
        self.assertIsNotNone(device)
        self.assertEqual(device.ten, "Phân phối dầu tổ máy 02")
        self.assertEqual(device.nha_may, "SH")

    def test_device_import_excel_legacy(self):
        self.client.force_authenticate(user=self.user)
        profile = self.user.profile
        profile.can_create_equipment = True
        profile.save()

        # Legacy format import
        headers = [
            "Mã đầy đủ",
            "Mã cấp hiện tại",
            "Mã đầy đủ thiết bị cha",
            "Tên thiết bị",
            "Loại/Phân loại",
            "Trạng thái",
            "Nhà chế tạo",
            "Nhà cung cấp",
            "Nước sản xuất",
            "Nhà máy",
            "Cấp",
            "Mã vận hành",
            "Bộ phận quản lý",
            "Bảng vẽ",
            "Thông số kỹ thuật",
            "Ngày lắp đặt",
            "Ngày vận hành"
        ]
        row_data = [
            "SH.TB.H1.PD.03",
            "PD.03",
            "SH.TB.H1",
            "Phân phối dầu tổ máy 03",
            "Thiết bị phụ",
            "Hoạt động",
            "Alstom",
            "Alstom Vietnam",
            "Pháp",
            "SH",
            "4",
            "3-OPD",
            "Phân xưởng vận hành",
            "SH-H1-GE-03",
            "Áp lực định mức 40 bar",
            "2026-01-15",
            "2026-02-01"
        ]
        excel_buf = self._create_excel_file([headers, row_data])

        url = reverse("quanlyvanhanh:thietbi-import-excel")
        response = self.client.post(url, {'file': excel_buf}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify device was created
        device = ThietBi.objects.filter(ma_day_du="SH.TB.H1.PD.03").first()
        self.assertIsNotNone(device)
        self.assertEqual(device.ten, "Phân phối dầu tổ máy 03")
        self.assertEqual(device.nha_may, "SH")

    def test_device_import_excel_fallback_ma_day_du(self):
        self.client.force_authenticate(user=self.user)
        profile = self.user.profile
        profile.can_create_equipment = True
        profile.save()

        # Fallback to Mã đầy đủ (missing Mã thiết bị (*) or Mã cấp hiện tại)
        headers = [
            "Mã đầy đủ",
            "Tên thiết bị",
            "Nhà máy",
        ]
        row_data = [
            "SH.TB.H1.PD.04",
            "Phân phối dầu tổ máy 04",
            "SH",
        ]
        excel_buf = self._create_excel_file([headers, row_data])

        url = reverse("quanlyvanhanh:thietbi-import-excel")
        response = self.client.post(url, {'file': excel_buf}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify device was created and hierarchy resolved
        device = ThietBi.objects.filter(ma_day_du="SH.TB.H1.PD.04").first()
        self.assertIsNotNone(device)
        self.assertEqual(device.ma, "PD.04")
        self.assertEqual(device.cha_id, self.h1_device.id)
        self.assertEqual(device.ten, "Phân phối dầu tổ máy 04")

