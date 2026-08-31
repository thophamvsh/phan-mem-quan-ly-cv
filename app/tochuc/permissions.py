from rest_framework.permissions import BasePermission


def has_organization_permission(user, permission):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    return profile.has_effective_permission(permission)


def can_access_organization_plant(user, plant_id):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    return bool(
        profile.is_all_factories
        or (
            profile.nha_may_id
            and str(profile.nha_may_id) == str(plant_id)
        )
    )


class OrganizationDirectoryPermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return any(
                has_organization_permission(request.user, permission)
                for permission in (
                    "can_view_organization_directory",
                    "can_manage_organization_directory",
                    "can_view_shift_schedule",
                    "can_manage_shift_roster",
                )
            )
        return any(
            has_organization_permission(request.user, permission)
            for permission in (
                "can_manage_organization_directory",
                "can_manage_shift_roster",
            )
        )
