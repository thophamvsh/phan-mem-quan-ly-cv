from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch
import qrcode

from core.models import UserProfile
from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi
from quanlyvanhanh.serializers import get_thiet_bi_qr_payload, ThietBiSerializer

class ThietBiQRTests(APITestCase):
    def setUp(self):
        # Create factory and user
        self.factory = Bang_nha_may.objects.create(ma_nha_may="VS", ten_nha_may="Vinh Son")
        self.user = get_user_model().objects.create_user(
            email="testuser@example.com",
            password="testpass123",
            username="testuser",
            is_superuser=True  # Ensure view permission
        )
        UserProfile.objects.create(user=self.user, nha_may=self.factory)

        self.device = ThietBi.objects.create(
            ten="Thiết bị Test QR",
            ma="VS.TB.TEST",
            ma_day_du="VS.TB.TEST",
            nha_may="Vinh Son"
        )

    def test_get_thiet_bi_qr_payload_fallback(self):
        # Without request, it should use the fallback host
        payload = get_thiet_bi_qr_payload(self.device)
        self.assertIn("http://localhost:5173/quanlyvanhanh/thietbi?detailId=", payload)
        self.assertIn(str(self.device.pk), payload)

    def test_get_thiet_bi_qr_payload_with_request_referer(self):
        # Create a mock request with referer
        class MockRequest:
            def __init__(self, referer):
                self.META = {'HTTP_REFERER': referer}

        request = MockRequest("http://192.168.1.50:3000/quanlyvanhanh/thietbi")
        payload = get_thiet_bi_qr_payload(self.device, request)
        self.assertEqual(payload, f"http://192.168.1.50:3000/quanlyvanhanh/thietbi?detailId={self.device.pk}")

    def test_serializer_ma_qr(self):
        # Create a request context for serializer
        class MockRequest:
            def __init__(self):
                self.META = {'HTTP_REFERER': 'https://my-app.domain/quanlyvanhanh/thietbi'}
            def build_absolute_uri(self, path):
                return f"https://my-app.domain{path}"

        request = MockRequest()
        serializer = ThietBiSerializer(self.device, context={'request': request})
        self.assertEqual(
            serializer.data['ma_qr'],
            f"https://my-app.domain/quanlyvanhanh/thietbi?detailId={self.device.pk}"
        )

    @patch('qrcode.QRCode.add_data')
    def test_qr_view_encodes_correct_url(self, mock_add_data):
        self.client.force_authenticate(user=self.user)
        
        # Test request with HTTP_REFERER header
        url = reverse('quanlyvanhanh:thietbi-qr', kwargs={'pk': self.device.pk})
        response = self.client.get(url, HTTP_REFERER="https://custom-domain.com/thietbi")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'image/png')
        
        # Verify that add_data was called with the correct URL
        mock_add_data.assert_called_once()
        called_data = mock_add_data.call_args[0][0]
        self.assertEqual(called_data, f"https://custom-domain.com/quanlyvanhanh/thietbi?detailId={self.device.pk}")
