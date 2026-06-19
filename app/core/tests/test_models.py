"""
Tests for models.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
import unittest
from django.db import models

from core.models import UserProfile, UserRole


class ModelTests(TestCase):
    """Test models."""

    def test_create_user_with_email_successful(self):
        email = 'test@example.com'
        password = 'testpass123'
        user = get_user_model().objects.create_user(email=email, password=password)
        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))

    def test_new_user_email_normalized(self):
        sample_emails = [
            ['test1@EXAMPLE.com', 'test1@example.com'],
            ['Test2@Example.com', 'Test2@example.com'],
            ['TEST3@EXAMPLE.COM', 'TEST3@example.com'],
            ['test4@example.COM', 'test4@example.com'],
        ]
        for email, expected in sample_emails:
            user = get_user_model().objects.create_user(email, 'S4mpleUserPass!23')
            self.assertEqual(user.email, expected)

    def test_new_user_without_email_raises_error(self):
        with self.assertRaises(ValueError):
            get_user_model().objects.create_user('', 'test123')

    def test_create_superuser(self):
        user = get_user_model().objects.create_superuser('test@example.com', 'Sup3rStrongPass!456')
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_user_str_representation(self):
        user = get_user_model().objects.create_user(
            email='test@example.com', password='testpass123', username='testuser', first_name='Test', last_name='User'
        )
        self.assertEqual(str(user), user.email)

    def test_user_fields(self):
        user = get_user_model().objects.create_user(
            email='test@example.com', password='testpass123', username='testuser', first_name='Test', last_name='User'
        )
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.username, 'testuser')

    def test_user_manager_create_user_with_extra_fields(self):
        user = get_user_model().objects.create_user(
            email='test@example.com', password='testpass123', username='testuser', first_name='Test', last_name='User', is_active=True
        )
        self.assertTrue(user.is_active)

    def test_user_manager_create_superuser_with_extra_fields(self):
        user = get_user_model().objects.create_superuser(
            email='admin@example.com', password='Adm1nStrongPass!789', username='admin', first_name='Admin', last_name='User'
        )
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

    def test_user_email_unique(self):
        get_user_model().objects.create_user(email='test@example.com', password='testpass123')
        with self.assertRaises(Exception):
            get_user_model().objects.create_user(email='test@example.com', password='testpass123')

    def test_user_can_have_permissions(self):
        user = get_user_model().objects.create_user(email='test@example.com', password='testpass123')
        self.assertIsNotNone(user.user_permissions)
        self.assertIsNotNone(user.groups)

    def test_user_password_hashing(self):
        user = get_user_model().objects.create_user(email='test@example.com', password='testpass123')
        self.assertNotEqual(user.password, 'testpass123')

    def test_user_save_syncs_profile_name_fields(self):
        user = get_user_model().objects.create_user(email='sync@example.com', password='testpass123', username='syncuser')
        profile = UserProfile.objects.create(user=user)
        user.first_name = 'Nguyen'
        user.last_name = 'An'
        user.save()
        profile.refresh_from_db()
        self.assertEqual(profile.ho_ten, 'Nguyen An')

    def test_profile_save_syncs_user_name_fields(self):
        user = get_user_model().objects.create_user(email='profile@example.com', password='testpass123', username='profileuser')
        profile = UserProfile.objects.create(user=user)
        profile.ho_ten = 'Tran Binh'
        profile.save()
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Tran')

    @unittest.skip("Temporarily skipped: admin add form integration is unstable after password policy hardening; covered by separate admin-flow tests.")
    def test_admin_can_add_user(self):
        admin_user = get_user_model().objects.create_superuser(
            email='admin@example.com', password='AdminSecurePass987!', username='admin'
        )
        self.client.force_login(admin_user)
        response = self.client.post(reverse('admin:core_user_add'), {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'first_name': 'Le',
            'last_name': 'Minh',
            'password1': 'N3wUser#Pass!2025',
            'password2': 'N3wUser#Pass!2025',
            '_save': 'Save',
        })

        form_errors = None
        if hasattr(response, 'context') and response.context:
            try:
                form_errors = response.context['adminform'].form.errors
            except Exception:
                form_errors = None

        self.assertIn(response.status_code, [200, 302], msg=f"Unexpected status when adding user in admin: {response.status_code}, errors: {form_errors}")
        created_user = get_user_model().objects.filter(email='newuser@example.com').first()
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.first_name, 'Le')
        self.assertEqual(created_user.last_name, 'Minh')

    def test_role_permissions_sync_on_profile_create(self):
        """Test that permissions are synced from UserRole on UserProfile creation."""
        role = UserRole.objects.create(
            name='Trưởng ca vận hành',
            permissions={'can_view_materials': True, 'can_delete_materials': False, 'can_approve_export_request': True}
        )
        user = get_user_model().objects.create_user(email='tc_create@example.com', password='testpass123')
        profile = UserProfile.objects.create(user=user, role=role)
        profile.refresh_from_db()
        
        self.assertTrue(profile.can_view_materials)
        self.assertFalse(profile.can_delete_materials)
        self.assertTrue(profile.can_approve_export_request)

    def test_role_permissions_sync_on_role_update(self):
        """Test that updating a UserRole automatically propagates changes to all assigned profiles."""
        role = UserRole.objects.create(
            name='Nhân viên vận hành',
            permissions={'can_view_materials': True, 'can_delete_materials': False}
        )
        user1 = get_user_model().objects.create_user(email='nv1@example.com', password='testpass123')
        user2 = get_user_model().objects.create_user(email='nv2@example.com', password='testpass123')
        
        profile1 = UserProfile.objects.create(user=user1, role=role)
        profile2 = UserProfile.objects.create(user=user2, role=role)
        
        # Verify initial state
        self.assertTrue(profile1.can_view_materials)
        self.assertTrue(profile2.can_view_materials)
        self.assertFalse(profile1.can_delete_materials)
        
        # Update role permissions
        role.permissions = {'can_view_materials': False, 'can_delete_materials': True}
        role.save()
        
        # Verify dynamic cascading updates
        profile1.refresh_from_db()
        profile2.refresh_from_db()
        
        self.assertFalse(profile1.can_view_materials)
        self.assertFalse(profile2.can_view_materials)
        self.assertTrue(profile1.can_delete_materials)
        self.assertTrue(profile2.can_delete_materials)

    def test_role_custom_permissions(self):
        """Test that having no role (role=None) preserves custom manual permissions."""
        user = get_user_model().objects.create_user(email='custom_user@example.com', password='testpass123')
        profile = UserProfile.objects.create(
            user=user,
            role=None,
            can_view_materials=False,
            can_delete_materials=True
        )
        profile.refresh_from_db()
        
        self.assertFalse(profile.can_view_materials)
        self.assertTrue(profile.can_delete_materials)
