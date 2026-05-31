import io
import pandas as pd
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi, ThongSoVanHanh, ThongSoToMay
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
