from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from datetime import datetime, time
import pytz
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi, ThongSoVanHanh, ThongSoToMay, ThongSoTram110KV, NguongThongSo
from django.utils import timezone


class OptimizedViewsTests(APITestCase):
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

        # Create device
        self.device = ThietBi.objects.create(
            ten="Tổ máy H1",
            ma="SH.TB.H1",
            ma_day_du="SH.TB.H1",
            nha_may="Song Hinh"
        )

        # Define targets
        self.target_date = datetime(2026, 5, 31).date()
        self.vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')

        # Create some ThongSoVanHanh
        dt_0830 = self.vietnam_tz.localize(datetime(2026, 5, 31, 8, 30))
        self.ts_vh = ThongSoVanHanh.objects.create(
            thiet_bi=self.device,
            ma_thong_so="dien_ap_h1",
            ten_thong_so="Điện áp H1",
            don_vi="kV",
            gia_tri="220.5",
            thoi_diem_nhap=dt_0830,
            ngay_nhap=self.target_date,
            nha_may="Song Hinh"
        )

        # Create some ThongSoToMay
        dt_0900 = self.vietnam_tz.localize(datetime(2026, 5, 31, 9, 0))
        self.ts_tm = ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="ap_luc_nuoc",
            ten_thong_so="Áp lực nước",
            don_vi="bar",
            gia_tri=5.4,
            thoi_diem_nhap=dt_0900,
            ngay_nhap=self.target_date,
            nha_may="Song Hinh"
        )

    def test_thong_so_by_day_view_binned_slots(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thong-so-by-day')
        response = self.client.get(url, {
            'thiet_bi_ma': 'SH.TB.H1',
            'ngay': '2026-05-31',
            'aggregate': 'true'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ngay'], '2026-05-31')
        self.assertEqual(response.data['thiet_bi']['ma_day_du'], 'SH.TB.H1')
        
        # Verify 48-slot binning
        thong_sos = response.data['thong_sos']
        self.assertTrue(len(thong_sos) >= 1)
        
        # Find "dien_ap_h1"
        dien_ap_data = next((ts for ts in thong_sos if ts['ma'] == 'dien_ap_h1'), None)
        self.assertIsNotNone(dien_ap_data)
        self.assertEqual(len(dien_ap_data['values']), 48)
        
        # 08:30 is slot index 17
        self.assertEqual(dien_ap_data['values'][17], 220.5)

    def test_thong_so_to_may_by_day_view_binned_slots(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thong-so-to-may-by-day')
        response = self.client.get(url, {
            'thiet_bi_ma': 'SH.TB.H1',
            'ngay': '2026-05-31',
            'aggregate': 'true'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify 24-slot binning
        thong_sos = response.data['thong_sos']
        self.assertTrue(len(thong_sos) >= 1)
        
        # Find "ap_luc_nuoc"
        ap_luc_data = next((ts for ts in thong_sos if ts['ma'] == 'ap_luc_nuoc'), None)
        self.assertIsNotNone(ap_luc_data)
        self.assertEqual(len(ap_luc_data['values']), 24)
        
        # 09:00 is slot index 9
        self.assertEqual(ap_luc_data['values'][9], 5.4)

    def test_thong_so_to_may_bulk_upsert_accepts_device_code(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thongsotomay-bulk-upsert')
        response = self.client.post(
            url,
            [
                {
                    'thiet_bi_ma': 'SH.TB.H1',
                    'ma_thong_so': 'ap_luc_nuoc',
                    'ten_thong_so': 'Áp lực nước',
                    'don_vi': 'bar',
                    'gia_tri': 6.2,
                    'thoi_diem_nhap': '2026-05-31 10:00:00',
                    'ngay_nhap': '2026-05-31',
                    'nha_may': 'Song Hinh',
                }
            ],
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created'], 1)
        self.assertTrue(
            ThongSoToMay.objects.filter(
                thiet_bi=self.device,
                ma_thong_so='ap_luc_nuoc',
                ngay_nhap='2026-05-31',
                gia_tri=6.2,
            ).exists()
        )

    def test_thong_so_to_may_bulk_upsert_null_value_deletes_existing_record(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thongsotomay-bulk-upsert')
        response = self.client.post(
            url,
            [
                {
                    'thiet_bi_ma': 'SH.TB.H1',
                    'ma_thong_so': self.ts_tm.ma_thong_so,
                    'ten_thong_so': self.ts_tm.ten_thong_so,
                    'don_vi': self.ts_tm.don_vi,
                    'gia_tri': None,
                    'thoi_diem_nhap': '2026-05-31T09:00:00+07:00',
                    'ngay_nhap': '2026-05-31',
                    'nha_may': 'Song Hinh',
                }
            ],
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted'], 1)
        self.assertFalse(
            ThongSoToMay.objects.filter(id=self.ts_tm.id).exists()
        )

    def test_thong_so_van_hanh_bulk_create_accepts_thiet_bi_id(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thongsovanhanh-bulk-create')
        response = self.client.post(
            url,
            [
                {
                    'thiet_bi_id': self.device.id,
                    'ma_thong_so': 'dien_ap_h1',
                    'ten_thong_so': 'Dien ap H1',
                    'don_vi': 'kV',
                    'gia_tri': '221.5',
                    'thoi_diem_nhap': '2026-05-31T10:00:00+07:00',
                    'ngay_nhap': '2026-05-31',
                    'nha_may': 'Song Hinh',
                }
            ],
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created'], 1)
        self.assertTrue(
            ThongSoVanHanh.objects.filter(
                thiet_bi=self.device,
                ma_thong_so='dien_ap_h1',
                ngay_nhap='2026-05-31',
                gia_tri='221.5',
            ).exists()
        )

    def test_thong_so_van_hanh_bulk_create_updates_unique_name_match(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thongsovanhanh-bulk-create')
        response = self.client.post(
            url,
            [
                {
                    'thiet_bi_id': self.device.id,
                    'ma_thong_so': 'dien_ap_kich_tu',
                    'ten_thong_so': self.ts_vh.ten_thong_so,
                    'don_vi': self.ts_vh.don_vi,
                    'gia_tri': '225.5',
                    'thoi_diem_nhap': '2026-05-31T08:30:00+07:00',
                    'ngay_nhap': '2026-05-31',
                    'nha_may': 'Song Hinh',
                }
            ],
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['created'], 0)
        self.assertEqual(response.data['updated'], 1)
        self.assertEqual(
            ThongSoVanHanh.objects.filter(
                thiet_bi=self.device,
                ten_thong_so=self.ts_vh.ten_thong_so,
                thoi_diem_nhap=self.ts_vh.thoi_diem_nhap,
            ).count(),
            1,
        )
        self.ts_vh.refresh_from_db()
        self.assertEqual(self.ts_vh.ma_thong_so, 'dien_ap_kich_tu')
        self.assertEqual(self.ts_vh.gia_tri, '225.5')

    def test_thong_so_van_hanh_bulk_create_null_value_deletes_existing_record(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thongsovanhanh-bulk-create')
        response = self.client.post(
            url,
            [
                {
                    'thiet_bi_id': self.device.id,
                    'ma_thong_so': self.ts_vh.ma_thong_so,
                    'ten_thong_so': self.ts_vh.ten_thong_so,
                    'don_vi': self.ts_vh.don_vi,
                    'gia_tri': None,
                    'thoi_diem_nhap': '2026-05-31T08:30:00+07:00',
                    'ngay_nhap': '2026-05-31',
                    'nha_may': 'Song Hinh',
                }
            ],
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['deleted'], 1)
        self.assertFalse(
            ThongSoVanHanh.objects.filter(id=self.ts_vh.id).exists()
        )

    def test_thong_so_tram_bulk_upsert_fills_blank_nha_may(self):
        tram_device = ThietBi.objects.create(
            ten='Tram T1',
            ma='SH.TB.TPP.110.T1',
            ma_day_du='SH.TB.TPP.110.T1',
            nha_may='Song Hinh',
        )

        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thongsotram110kv-bulk-upsert')
        response = self.client.post(
            url,
            [
                {
                    'thiet_bi_ma': tram_device.ma_day_du,
                    'ma_thong_so': 'nhiet_do_mba_t1',
                    'ten_thong_so': 'Nhiet do MBA T1',
                    'don_vi': 'C',
                    'gia_tri': '45',
                    'thoi_diem_nhap': '2026-05-31T10:00:00+07:00',
                    'ngay_nhap': '2026-05-31',
                    'nha_may': '',
                    'ky_hieu_van_hanh': '',
                    'ghi_chu': '',
                }
            ],
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        record = ThongSoTram110KV.objects.get(
            thiet_bi=tram_device,
            ma_thong_so='nhiet_do_mba_t1',
            ngay_nhap='2026-05-31',
        )
        self.assertEqual(record.nha_may, 'Song Hinh')
        self.assertEqual(record.gia_tri, '45')

    def test_thong_so_to_may_by_day_resolves_fallback_thresholds_for_subdevices(self):
        # Create a sub-device that belongs to TuB under H1 (e.g. TuB.SH)
        sub_device = ThietBi.objects.create(
            ten="Lưu lượng chèn trục H1",
            ma="SH.TB.H1.TuB.SH",
            ma_day_du="SH.TB.H1.TuB.SH",
            cha=self.device,
            nha_may="Song Hinh"
        )
        
        # Configure a threshold for this sub-device specifically
        NguongThongSo.objects.create(
            nha_may="Song Hinh",
            thiet_bi=sub_device,
            ma_thong_so="luu_luong_chen_truc",
            ten_thong_so="Lưu lượng chèn trục",
            alarm=8.0,
            trip=6.0,
            rated=10.0,
        )

        # Create a sample ThongSoToMay record so it is returned by the API
        dt_0930 = self.vietnam_tz.localize(datetime(2026, 5, 31, 9, 30))
        ThongSoToMay.objects.create(
            thiet_bi=sub_device,
            ma_thong_so="luu_luong_chen_truc",
            ten_thong_so="Lưu lượng chèn trục",
            don_vi="l/p",
            gia_tri=5.0,
            thoi_diem_nhap=dt_0930,
            ngay_nhap=self.target_date,
            nha_may="Song Hinh"
        )
        
        # Now query H1 main device 'SH.TB.H1' via the by_day endpoint
        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thong-so-to-may-by-day')
        response = self.client.get(url, {
            'thiet_bi_ma': 'SH.TB.H1',
            'ngay': '2026-05-31',
            'aggregate': 'true'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the thresholds are correctly resolved and returned for 'luu_luong_chen_truc'
        thong_sos = response.data['thong_sos']
        chen_truc_data = next((ts for ts in thong_sos if ts['ma'] == 'luu_luong_chen_truc'), None)
        self.assertIsNotNone(chen_truc_data)
        
        # The thresholds should be resolved successfully using fallback prefix lookup
        self.assertEqual(chen_truc_data['alarm'], 8.0)
        self.assertEqual(chen_truc_data['trip'], 6.0)
        self.assertEqual(chen_truc_data['rated'], 10.0)

    def test_thong_so_active_alerts_endpoint(self):
        # Configure threshold for ap_luc_nuoc
        NguongThongSo.objects.create(
            nha_may="Song Hinh",
            thiet_bi=self.device,
            ma_thong_so="ap_luc_nuoc",
            ten_thong_so="Áp lực nước",
            alarm=5.0,
            trip=4.0,
        )

        # Create today's measurement that is within the Alarm Warning Margin (5.05, within margin 5.1)
        today = timezone.localtime(timezone.now()).date()
        dt_now = timezone.localtime(timezone.now())
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="ap_luc_nuoc",
            ten_thong_so="Áp lực nước",
            don_vi="bar",
            gia_tri=5.05, # below alarm + margin (5.1) but above alarm (5.0)
            thoi_diem_nhap=dt_now,
            ngay_nhap=today,
            nha_may="Song Hinh"
        )

        self.client.force_authenticate(user=self.user)
        url = reverse('quanlyvanhanh:thong-so-active-alerts')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        alert = response.data[0]
        self.assertEqual(alert["ma_thong_so"], "ap_luc_nuoc")
        self.assertEqual(alert["gia_tri"], 5.05)
        self.assertEqual(alert["alert_type"], "near_alarm")

        # Now test actual alarm violation (e.g. 4.8, below alarm 5.0 but above trip 4.0)
        ThongSoToMay.objects.all().delete()
        ThongSoToMay.objects.create(
            thiet_bi=self.device,
            ma_thong_so="ap_luc_nuoc",
            ten_thong_so="Áp lực nước",
            don_vi="bar",
            gia_tri=4.8,
            thoi_diem_nhap=dt_now,
            ngay_nhap=today,
            nha_may="Song Hinh"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        alert = response.data[0]
        self.assertEqual(alert["alert_type"], "alarm")
