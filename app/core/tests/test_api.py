import os
from unittest.mock import patch
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import User, UserProfile
from core.throttles import LoginRateThrottle

class CoreAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='testuser', 
            password='testpassword123',
            email='test@example.com'
        )
        self.admin = User.objects.create_superuser(
            username='admin', 
            password='adminpassword123',
            email='admin@example.com'
        )
        
    def test_health_check(self):
        url = reverse('health-check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'ok')

    def test_user_login(self):
        url = reverse('user-login')
        data = {'username': 'testuser', 'password': 'testpassword123'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('tokens' in response.data)
        
    def test_user_profile_unauthenticated(self):
        url = reverse('user-profile')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_user_profile_authenticated(self):
        url = reverse('user-profile')
        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
    def test_user_list_admin_only(self):
        url = reverse('user-list')
        
        # Test normal user
        self.client.force_authenticate(user=self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test admin user
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertTrue('count' in response.data)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'core-throttle-tests',
        }
    },
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'login': '2/minute',
            'register': '2/minute',
            'token': '2/minute',
            'ai': '2/minute',
        }
    },
)
class AuthenticationThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='throttle-user',
            password='testpassword123',
            email='throttle@example.com',
        )

    def test_login_is_throttled_after_configured_limit(self):
        url = reverse('user-login')
        credentials = {
            'username': self.user.username,
            'password': 'wrong-password',
        }

        with patch.object(
            LoginRateThrottle,
            'THROTTLE_RATES',
            {'login': '2/minute'},
        ):
            self.assertEqual(self.client.post(url, credentials).status_code, 400)
            self.assertEqual(self.client.post(url, credentials).status_code, 400)
            response = self.client.post(url, credentials)

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Retry-After', response)
