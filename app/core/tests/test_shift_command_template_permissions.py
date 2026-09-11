from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile, UserRole
from core.user_management_policy import has_permission


class ShiftCommandTemplatePermissionsModelTest(TestCase):
    """Kiểm tra logic phân quyền mẫu nội dung vận hành ở tầng Model & Policy."""

    PERMISSION_FIELDS = [
        "can_view_shift_command_templates",
        "can_create_shift_command_templates",
        "can_edit_shift_command_templates",
        "can_delete_shift_command_templates",
        "can_activate_shift_command_templates",
    ]

    def setUp(self):
        User = get_user_model()
        self.normal_user = User.objects.create_user(
            email="operator@vsh.vn",
            username="operator",
            password="testpassword123",
            first_name="Vận hành",
            last_name="Viên",
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.normal_user)

        self.superuser = User.objects.create_superuser(
            email="admin@vsh.vn",
            username="admin",
            password="superpassword123",
            first_name="Quản trị",
            last_name="Hệ thống",
        )
        self.superuser_profile, _ = UserProfile.objects.get_or_create(user=self.superuser)

    def test_default_values_are_false(self):
        """1. Kiểm tra giá trị mặc định của cả 5 quyền là False."""
        self.profile.refresh_from_db()
        for perm in self.PERMISSION_FIELDS:
            value = getattr(self.profile, perm)
            self.assertFalse(
                value,
                f"Giá trị mặc định của {perm} phải là False nhưng nhận được {value}",
            )

    def test_superuser_has_all_permissions(self):
        """2. Kiểm tra Superuser có toàn quyền theo policy và model."""
        self.assertTrue(self.superuser.is_superuser)
        for perm in self.PERMISSION_FIELDS:
            self.assertTrue(
                has_permission(self.superuser, perm),
                f"Superuser phải có quyền {perm} qua has_permission",
            )

    def test_role_and_individual_permissions_effective(self):
        """3. Kiểm tra cả quyền nhóm (UserRole) và quyền cá nhân (individual_permissions) đều có hiệu lực."""
        # A. Cấp quyền qua UserRole
        role = UserRole.objects.create(
            name="Trưởng ca vận hành",
            description="Có quyền xem và tạo mẫu nội dung",
            permissions={
                "can_view_shift_command_templates": True,
                "can_create_shift_command_templates": True,
            },
        )
        self.profile.role = role
        self.profile.save()
        self.profile.refresh_from_db()

        self.assertTrue(self.profile.can_view_shift_command_templates)
        self.assertTrue(self.profile.can_create_shift_command_templates)
        self.assertFalse(self.profile.can_edit_shift_command_templates)
        self.assertFalse(self.profile.can_delete_shift_command_templates)
        self.assertFalse(self.profile.can_activate_shift_command_templates)

        self.assertTrue(
            self.profile.has_effective_permission("can_view_shift_command_templates")
        )
        self.assertTrue(has_permission(self.normal_user, "can_view_shift_command_templates"))
        self.assertFalse(
            self.profile.has_effective_permission("can_delete_shift_command_templates")
        )
        self.assertFalse(has_permission(self.normal_user, "can_delete_shift_command_templates"))

        # B. Cấp quyền cá nhân bổ sung qua individual_permissions (override/grant)
        self.profile.individual_permissions = {
            "can_edit_shift_command_templates": True,
        }
        self.profile.save()
        self.profile.refresh_from_db()

        # Quyền từ role vẫn giữ nguyên
        self.assertTrue(self.profile.can_view_shift_command_templates)
        self.assertTrue(self.profile.can_create_shift_command_templates)
        # Quyền từ individual_permissions được cộng thêm
        self.assertTrue(self.profile.can_edit_shift_command_templates)
        self.assertTrue(
            self.profile.has_effective_permission("can_edit_shift_command_templates")
        )
        self.assertTrue(has_permission(self.normal_user, "can_edit_shift_command_templates"))
        # Quyền chưa cấp vẫn False
        self.assertFalse(self.profile.can_delete_shift_command_templates)

        # C. Cập nhật UserRole tự động lan tỏa (cascade) tới profile
        role.permissions = {
            "can_view_shift_command_templates": True,
            "can_create_shift_command_templates": False,
            "can_activate_shift_command_templates": True,
        }
        role.save()
        self.profile.refresh_from_db()

        self.assertTrue(self.profile.can_view_shift_command_templates)
        self.assertFalse(self.profile.can_create_shift_command_templates)
        self.assertTrue(self.profile.can_activate_shift_command_templates)
        # Quyền cá nhân riêng vẫn được bảo toàn
        self.assertTrue(self.profile.can_edit_shift_command_templates)

    def test_migration_preserves_existing_accounts_unaffected(self):
        """5. Kiểm tra migration không làm thay đổi dữ liệu hiện hữu của tài khoản ngoài việc thêm trường mặc định."""
        User = get_user_model()
        legacy_user = User.objects.create_user(
            email="legacy@vsh.vn",
            username="legacy_operator",
            password="legacypassword123",
            first_name="Cũ",
            last_name="Tài khoản",
        )
        profile, _ = UserProfile.objects.get_or_create(user=legacy_user)
        profile.phone = "0987654321"
        profile.chuc_danh = "Kỹ sư vận hành"
        profile.can_view_materials = True
        profile.save()

        profile.refresh_from_db()
        self.assertEqual(profile.user.email, "legacy@vsh.vn")
        self.assertEqual(profile.phone, "0987654321")
        self.assertEqual(profile.chuc_danh, "Kỹ sư vận hành")
        self.assertTrue(profile.can_view_materials)

        # Các quyền mới an toàn ở giá trị False
        for perm in self.PERMISSION_FIELDS:
            self.assertFalse(getattr(profile, perm))


class ShiftCommandTemplatePermissionsAPITest(APITestCase):
    """Kiểm tra API profile trả về đầy đủ 5 trường quyền mẫu nội dung vận hành."""

    PERMISSION_FIELDS = [
        "can_view_shift_command_templates",
        "can_create_shift_command_templates",
        "can_edit_shift_command_templates",
        "can_delete_shift_command_templates",
        "can_activate_shift_command_templates",
    ]

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="api_operator@vsh.vn",
            username="api_operator",
            password="testpassword123",
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile_url = reverse("user-profile")

    def test_profile_api_returns_all_five_permissions(self):
        """4. API profile trả đủ 5 trường quyền với giá trị chính xác."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("success"))
        data = response.data.get("user", {})

        # Đảm bảo có đủ 5 trường quyền
        for perm in self.PERMISSION_FIELDS:
            self.assertIn(
                perm,
                data,
                f"API profile phải trả trường {perm} trong data",
            )
            self.assertIs(
                data[perm],
                False,
                f"Trường {perm} phải có giá trị False mặc định",
            )

        # Cấp quyền và kiểm tra lại API
        self.profile.can_view_shift_command_templates = True
        self.profile.can_activate_shift_command_templates = True
        self.profile.save()

        response2 = self.client.get(self.profile_url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response2.data.get("user", {})

        self.assertIs(data2["can_view_shift_command_templates"], True)
        self.assertIs(data2["can_create_shift_command_templates"], False)
        self.assertIs(data2["can_edit_shift_command_templates"], False)
        self.assertIs(data2["can_delete_shift_command_templates"], False)
        self.assertIs(data2["can_activate_shift_command_templates"], True)
