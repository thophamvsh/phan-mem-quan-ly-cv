import os
from unittest.mock import patch
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import User, UserProfile
from core.throttles import LoginRateThrottle
from tochuc.models import NhaMay

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


class UserOptionAPITests(APITestCase):
    def setUp(self):
        self.url = reverse("user-options")
        self.sh = NhaMay.objects.create(
            ma_nha_may="SH-OPT",
            ten_nha_may="Sông Hinh",
        )
        self.vs = NhaMay.objects.create(
            ma_nha_may="VS-OPT",
            ten_nha_may="Vĩnh Sơn",
        )
        self.user = User.objects.create_user(
            username="shift-user",
            email="shift-user@example.com",
            password="testpassword123",
        )
        self.same_factory_user = User.objects.create_user(
            username="same-factory-user",
            email="same-factory-user@example.com",
            password="testpassword123",
        )
        self.other_factory_user = User.objects.create_user(
            username="other-factory-user",
            email="other-factory-user@example.com",
            password="testpassword123",
        )
        self.inactive_user = User.objects.create_user(
            username="inactive-shift-user",
            email="inactive-shift-user@example.com",
            password="testpassword123",
            is_active=False,
        )
        for user, factory in (
            (self.user, self.sh),
            (self.same_factory_user, self.sh),
            (self.other_factory_user, self.vs),
            (self.inactive_user, self.sh),
        ):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.nha_may = factory
            profile.save(update_fields=["nha_may"])

    def test_requires_authentication(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_user_without_shift_log_permissions(self):
        profile = self.user.profile
        for field in UserOptionListPermissionFields:
            setattr(profile, field, False)
        profile.save(update_fields=UserOptionListPermissionFields)
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_returns_only_active_users_in_same_factory(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = {item["username"] for item in response.data}
        self.assertIn(self.user.username, usernames)
        self.assertIn(self.same_factory_user.username, usernames)
        self.assertNotIn(self.other_factory_user.username, usernames)
        self.assertNotIn(self.inactive_user.username, usernames)
        self.assertEqual(
            set(response.data[0]),
            {"id", "username", "full_name"},
        )

    def test_all_factories_user_can_see_other_factory(self):
        profile = self.user.profile
        profile.is_all_factories = True
        profile.save(update_fields=["is_all_factories"])
        self.client.force_authenticate(self.user)

        response = self.client.get(self.url)

        usernames = {item["username"] for item in response.data}
        self.assertIn(self.other_factory_user.username, usernames)


UserOptionListPermissionFields = [
    "can_view_shift_handover_logs",
    "can_create_shift_handover_logs",
    "can_receive_shift_handover_logs",
    "can_view_admin_shift_handover_logs",
    "can_create_admin_shift_handover_logs",
    "can_receive_admin_shift_handover_logs",
]


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
