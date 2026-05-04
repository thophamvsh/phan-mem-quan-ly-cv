from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import User

class KhoVattuAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='khouser', 
            password='testpassword123',
            email='kho@example.com'
        )
        
    def test_khovattu_unauthorized(self):
        # We assume 'khovattu-list' or similar exists, but let's just test a basic endpoint we know from urls if possible.
        # Let's test the compatibility auth endpoints for Khovattu
        url = reverse('khovattu-profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_khovattu_authorized(self):
        url = reverse('khovattu-profile')
        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
