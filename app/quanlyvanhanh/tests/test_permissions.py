from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import UserProfile
from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi, ThongSoVanHanh


class QuanLyVanHanhPermissionsTests(APITestCase):
    def setUp(self):
        # Create factories
        self.vs_factory = Bang_nha_may.objects.create(ma_nha_may="VS", ten_nha_may="Vinh Son")
        self.sh_factory = Bang_nha_may.objects.create(ma_nha_may="SH", ten_nha_may="Song Hinh")

        # Create users
        self.vs_user = get_user_model().objects.create_user(
            email="vs@example.com",
            password="testpass123",
            username="vsuser"
        )
        UserProfile.objects.create(user=self.vs_user, nha_may=self.vs_factory)

        self.sh_user = get_user_model().objects.create_user(
            email="sh@example.com",
            password="testpass123",
            username="shuser"
        )
        UserProfile.objects.create(user=self.sh_user, nha_may=self.sh_factory)

        # Create devices
        # VS device
        self.vs_device = ThietBi.objects.create(
            ten="Thiết bị Vinh Son",
            ma="VS.TB.H1",
            ma_day_du="VS.TB.H1",
            nha_may=""  # Trống sẽ match với VS user dựa trên tiền tố của ma_day_du
        )
        # SH device
        self.sh_device = ThietBi.objects.create(
            ten="Thiết bị Song Hinh",
            ma="SH.TB.H1",
            ma_day_du="SH.TB.H1",
            nha_may="Song Hinh"
        )

    def test_list_thiet_bi_filters_by_factory(self):
        # Authenticate as VS user
        self.client.force_authenticate(user=self.vs_user)
        url = reverse('quanlyvanhanh:thietbi-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Chỉ nhìn thấy thiết bị VS
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.vs_device.id)

        # Authenticate as SH user
        self.client.force_authenticate(user=self.sh_user)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.sh_device.id)

    def test_cannot_create_thiet_bi_for_other_factory(self):
        self.client.force_authenticate(user=self.vs_user)
        url = reverse('quanlyvanhanh:thietbi-list')
        
        # Cố gắng tạo thiết bị con dưới thiết bị SH
        data = {
            "ten": "Thiết bị con SH",
            "ma": "CON",
            "cha": self.sh_device.id,
            "nha_may": "Song Hinh"
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_can_create_thiet_bi_for_own_factory(self):
        self.client.force_authenticate(user=self.vs_user)
        url = reverse('quanlyvanhanh:thietbi-list')
        
        data = {
            "ten": "Thiết bị con VS",
            "ma": "CON",
            "cha": self.vs_device.id,
            "nha_may": ""
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
