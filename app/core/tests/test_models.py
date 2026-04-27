"""
Tests for models.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from core.models import UserProfile


class ModelTests(TestCase):
    """Test models."""

    def test_create_user_with_email_successful(self):
        """Test creating a user with an email is successful."""
        email = 'test@example.com'
        password = 'testpass123'
        user = get_user_model().objects.create_user(
            email=email,
            password=password,
        )

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        """Test email is normalized for new users."""
        sample_emails = [
            ['test1@EXAMPLE.com', 'test1@example.com'],
            ['Test2@Example.com', 'Test2@example.com'],
            ['TEST3@EXAMPLE.COM', 'TEST3@example.com'],
            ['test4@example.COM', 'test4@example.com'],
        ]
        for email, expected in sample_emails:
            user = get_user_model().objects.create_user(email, 'sample123')
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raises_error(self):
        """Test that creating a user without an email raises a ValueError."""
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user('', 'test123')

    def test_create_superuser(self):
        """Test creating a superuser."""
        user = get_user_model().objects.create_superuser(
            'test@example.com',
            'test123',
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_user_str_representation(self):
        """Test user string representation."""
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
            username='testuser',
            first_name='Test',
            last_name='User'
        )
        self.assertEqual(str(user), user.email)

    def test_user_fields(self):
        """Test user model fields."""
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
            username='testuser',
            first_name='Test',
            last_name='User'
        )

        # Test default values
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.email, 'test@example.com')

    def test_user_manager_create_user_with_extra_fields(self):
        """Test creating user with extra fields."""
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123',
            username='testuser',
            first_name='Test',
            last_name='User',
            is_active=True
        )

        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertTrue(user.is_active)

    def test_user_manager_create_superuser_with_extra_fields(self):
        """Test creating superuser with extra fields."""
        user = get_user_model().objects.create_superuser(
            email='admin@example.com',
            password='admin123',
            username='admin',
            first_name='Admin',
            last_name='User'
        )

        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.username, 'admin')
        self.assertEqual(user.first_name, 'Admin')
        self.assertEqual(user.last_name, 'User')

    def test_user_email_unique(self):
        """Test that user email must be unique."""
        get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            get_user_model().objects.create_user(
                email='test@example.com',
                password='testpass123'
            )

    def test_user_can_have_permissions(self):
        """Test that user can have permissions."""
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        # Test that user can have permissions
        self.assertIsNotNone(user.user_permissions)
        self.assertIsNotNone(user.groups)

    def test_user_password_hashing(self):
        """Test that user password is properly hashed."""
        user = get_user_model().objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        # Password should be hashed, not stored as plain text
        self.assertNotEqual(user.password, 'testpass123')
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))

    def test_user_save_syncs_profile_name_fields(self):
        """Saving user should sync profile name fields without recursion issues."""
        user = get_user_model().objects.create_user(
            email='sync@example.com',
            password='testpass123',
            username='syncuser',
        )
        profile = UserProfile.objects.create(user=user)

        user.first_name = 'Nguyen'
        user.last_name = 'An'
        user.save()

        profile.refresh_from_db()
        self.assertEqual(profile.ho_ten, 'Nguyen An')
        self.assertEqual(profile.ho, 'Nguyen')
        self.assertEqual(profile.ten, 'An')

    def test_profile_save_syncs_user_name_fields(self):
        """Saving profile should sync user name fields."""
        user = get_user_model().objects.create_user(
            email='profile@example.com',
            password='testpass123',
            username='profileuser',
        )
        profile = UserProfile.objects.create(user=user)

        profile.ho_ten = 'Tran Binh'
        profile.save()

        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Tran')
        self.assertEqual(user.last_name, 'Binh')

    def test_admin_can_add_user(self):
        """Admin add user should not fail on custom save synchronization."""
        admin_user = get_user_model().objects.create_superuser(
            email='admin@example.com',
            password='admin123456',
            username='admin',
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse('admin:core_user_add'),
            {
                'email': 'newuser@example.com',
                'username': 'newuser',
                'first_name': 'Le',
                'last_name': 'Minh',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
                '_save': 'Save',
            }
        )

        self.assertEqual(response.status_code, 302)
        created_user = get_user_model().objects.get(email='newuser@example.com')
        self.assertEqual(created_user.first_name, 'Le')
        self.assertEqual(created_user.last_name, 'Minh')
