"""One policy for both capabilities and writes. Deny by default."""
from rest_framework.exceptions import PermissionDenied, ValidationError
from tochuc.models import NhaMay
from .models import UserProfile, UserRole, UserRoleDelegation

MANAGEMENT_PERMISSIONS = (
    'can_view_users', 'can_create_users', 'can_edit_users',
    'can_assign_user_roles', 'can_manage_user_status',
)


def has_permission(user, name):
    profile = getattr(user, 'profile', None)
    return bool(user.is_active and (user.is_superuser or (
        profile and profile.has_effective_permission(name))))


def require_permissions(user, *names):
    if not all(has_permission(user, name) for name in ('can_view_users', *names)):
        raise PermissionDenied('Bạn không có quyền quản lý tài khoản này.')


def plant_scope(user):
    profile = getattr(user, 'profile', None)
    if user.is_superuser or getattr(profile, 'is_all_factories', False):
        return NhaMay.objects.all()
    return NhaMay.objects.filter(pk=getattr(profile, 'nha_may_id', None))


def resolve_plant(user, value):
    if value is None:
        profile = getattr(user, 'profile', None)
        if user.is_superuser or getattr(profile, 'is_all_factories', False):
            raise ValidationError({'nha_may': 'Vui lòng chọn nhà máy.'})
        value = getattr(profile, 'nha_may_id', None)
    plant = plant_scope(user).filter(pk=value).first()
    if not plant:
        raise PermissionDenied('Không có quyền truy cập nhà máy đã chọn.')
    return plant


def safe_role(role):
    permissions = role.permissions or {}
    known = {field.name for field in UserProfile._meta.fields if field.name.startswith('can_')}
    return isinstance(permissions, dict) and not any(
        not isinstance(value, bool) or key not in known or (value and key in MANAGEMENT_PERMISSIONS)
        for key, value in permissions.items()
    )


class ManagementPolicy:
    def __init__(self, actor):
        self.actor = actor
        self.grants = {}
        for grant in UserRoleDelegation.objects.filter(
            delegate=actor, is_active=True, nha_may__in=plant_scope(actor),
        ).select_related('assignable_role'):
            if safe_role(grant.assignable_role):
                self.grants.setdefault(grant.nha_may_id, set()).add(grant.assignable_role_id)

    def roles(self, plant):
        if self.actor.is_superuser:
            return UserRole.objects.all().order_by('name')
        roles = UserRole.objects.filter(pk__in=self.grants.get(plant.pk, set()))
        return UserRole.objects.filter(pk__in=[role.pk for role in roles if safe_role(role)]).order_by('name')

    def reason(self, target):
        if target.pk == self.actor.pk:
            return 'Không quản lý chính tài khoản của mình tại đây.'
        if self.actor.is_superuser:
            return ''
        profile = getattr(target, 'profile', None)
        if (target.is_staff or target.is_superuser or not profile
                or profile.is_all_factories or not profile.role_id
                or (profile.role_id and not safe_role(profile.role))
                or any((profile.individual_permissions or {}).values())
                or any(profile.has_effective_permission(p) for p in MANAGEMENT_PERMISSIONS)
                or target.groups.all() or target.user_permissions.all()):
            return 'Tài khoản được bảo vệ; vui lòng liên hệ quản trị viên.'
        if profile.role_id not in self.grants.get(profile.nha_may_id, set()):
            return 'Vai trò hiện tại nằm ngoài phạm vi được ủy quyền.'
        return ''

    def capabilities(self, target):
        reason = self.reason(target)
        return {
            'can_edit': not reason and has_permission(self.actor, 'can_edit_users'),
            'can_change_role': not reason and has_permission(self.actor, 'can_assign_user_roles'),
            'can_change_status': not reason and has_permission(self.actor, 'can_manage_user_status'),
            'protected_reason': reason,
        }

    def check_target(self, target):
        reason = self.reason(target)
        if reason:
            raise PermissionDenied(reason)
