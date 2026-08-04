from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from unittest.mock import patch

from core.models import User
from core.throttles import LoginRateThrottle, TokenRateThrottle


@override_settings(
    AUTH_COOKIE_NAME='refresh_token',
    AUTH_COOKIE_SECURE=True,
    AUTH_COOKIE_SAMESITE='Lax',
    AUTH_COOKIE_PATH='/api/v1/auth/',
    AUTH_COOKIE_DOMAIN=None,
)
class SecureAuthenticationTests(APITestCase):
    csrf_url = '/api/v1/auth/csrf-token/'
    login_url = '/api/v1/auth/login-secure/'
    refresh_url = '/api/v1/auth/refresh-secure/'
    logout_url = '/api/v1/auth/logout-secure/'

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username='secure-user',
            password='testpassword123',
            email='secure@example.com',
        )

    def _csrf_token(self):
        response = self.client.get(self.csrf_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('csrftoken', response.cookies)
        return response.data['csrfToken']

    def _login(self):
        csrf_token = self._csrf_token()
        return self.client.post(
            self.login_url,
            {'username': self.user.username, 'password': 'testpassword123'},
            format='json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )

    def test_secure_login_requires_csrf(self):
        response = self.client.post(
            self.login_url,
            {'username': self.user.username, 'password': 'testpassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_secure_login_sets_httponly_refresh_cookie(self):
        response = self._login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertNotIn('refresh', response.data)
        self.assertNotIn('tokens', response.data)

        cookie = response.cookies['refresh_token']
        self.assertTrue(cookie['httponly'])
        self.assertTrue(cookie['secure'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/api/v1/auth/')
        self.assertEqual(int(cookie['max-age']), 30 * 24 * 60 * 60)

    def test_secure_refresh_requires_csrf(self):
        login_response = self._login()
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        response = self.client.post(self.refresh_url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_secure_refresh_requires_cookie(self):
        csrf_token = self._csrf_token()
        response = self.client.post(
            self.refresh_url,
            {},
            format='json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_secure_refresh_rotates_cookie_and_rejects_reuse(self):
        login_response = self._login()
        old_refresh = login_response.cookies['refresh_token'].value
        csrf_token = self.client.cookies['csrftoken'].value

        refresh_response = self.client.post(
            self.refresh_url,
            {},
            format='json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)
        self.assertNotIn('refresh', refresh_response.data)
        new_refresh = refresh_response.cookies['refresh_token'].value
        self.assertNotEqual(old_refresh, new_refresh)

        self.client.cookies['refresh_token'] = old_refresh
        reuse_response = self.client.post(
            self.refresh_url,
            {},
            format='json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_secure_logout_is_idempotent_and_deletes_cookie(self):
        login_response = self._login()
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        csrf_token = self.client.cookies['csrftoken'].value

        logout_response = self.client.post(
            self.logout_url,
            {},
            format='json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        deleted_cookie = logout_response.cookies['refresh_token']
        self.assertEqual(deleted_cookie.value, '')
        self.assertEqual(deleted_cookie['max-age'], 0)
        self.assertEqual(deleted_cookie['path'], '/api/v1/auth/')

        second_response = self.client.post(
            self.logout_url,
            {},
            format='json',
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'secure-auth-throttle-tests',
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
    AUTH_COOKIE_SECURE=False,
)
class SecureAuthenticationThrottleTests(APITestCase):
    csrf_url = '/api/v1/auth/csrf-token/'
    login_url = '/api/v1/auth/login-secure/'
    refresh_url = '/api/v1/auth/refresh-secure/'

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username='secure-throttle-user',
            password='testpassword123',
            email='secure-throttle@example.com',
        )
        csrf_response = self.client.get(self.csrf_url)
        self.csrf_token = csrf_response.data['csrfToken']

    def test_secure_login_is_rate_limited(self):
        credentials = {
            'username': self.user.username,
            'password': 'wrong-password',
        }
        with patch.object(
            LoginRateThrottle,
            'THROTTLE_RATES',
            {'login': '2/minute'},
        ):
            self.assertEqual(
                self.client.post(
                    self.login_url,
                    credentials,
                    format='json',
                    HTTP_X_CSRFTOKEN=self.csrf_token,
                ).status_code,
                status.HTTP_400_BAD_REQUEST,
            )
            self.assertEqual(
                self.client.post(
                    self.login_url,
                    credentials,
                    format='json',
                    HTTP_X_CSRFTOKEN=self.csrf_token,
                ).status_code,
                status.HTTP_400_BAD_REQUEST,
            )
            response = self.client.post(
                self.login_url,
                credentials,
                format='json',
                HTTP_X_CSRFTOKEN=self.csrf_token,
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_secure_refresh_is_rate_limited(self):
        login_response = self.client.post(
            self.login_url,
            {
                'username': self.user.username,
                'password': 'testpassword123',
            },
            format='json',
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        with patch.object(
            TokenRateThrottle,
            'THROTTLE_RATES',
            {'token': '2/minute'},
        ):
            for _ in range(2):
                response = self.client.post(
                    self.refresh_url,
                    {},
                    format='json',
                    HTTP_X_CSRFTOKEN=self.csrf_token,
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

            response = self.client.post(
                self.refresh_url,
                {},
                format='json',
                HTTP_X_CSRFTOKEN=self.csrf_token,
            )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
