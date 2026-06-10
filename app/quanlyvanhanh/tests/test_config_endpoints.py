from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from khovattu.models import Bang_nha_may


class OperationConfigEndpointTests(APITestCase):
    def setUp(self):
        self.tkt_factory = Bang_nha_may.objects.create(
            ma_nha_may="TKT",
            ten_nha_may="Thuong Kon Tum",
        )
        self.user = get_user_model().objects.create_user(
            email="tkt@example.com",
            password="testpass123",
            username="tktuser",
        )
        UserProfile.objects.create(user=self.user, nha_may=self.tkt_factory)

    def test_dien_config_endpoint_supports_new_factory_prefix(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("quanlyvanhanh:thongsovanhanh-config"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["factory_code"], "TKT")
        self.assertEqual(response.data["layout"][0]["device_code"], "TKT.TB.H1")
        self.assertEqual(response.data["layout"][2]["device_code"], "TKT.TB.TPP")

    def test_dien_config_endpoint_rejects_other_factory_for_scoped_user(self):
        Bang_nha_may.objects.create(ma_nha_may="SH", ten_nha_may="Song Hinh")

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("quanlyvanhanh:thongsovanhanh-config"),
            {"factory_code": "SH"},
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_tram_config_endpoint_supports_new_factory_prefix(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("quanlyvanhanh:thongsotram110kv-config"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["factory_code"], "TKT")
        self.assertEqual(response.data["columns"][0]["ma_thiet_bi"], "TKT.TB.TPP.110.T1")
