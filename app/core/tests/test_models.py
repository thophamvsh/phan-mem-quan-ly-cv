"""
Tests for models.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


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