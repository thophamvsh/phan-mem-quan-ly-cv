from rest_framework import permissions


def has_ai_tools_permission(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(getattr(profile, "can_use_ai_tools", False))


class CanUseAiTools(permissions.BasePermission):
    message = "Ban khong co quyen su dung tro ly AI."

    def has_permission(self, request, view):
        return has_ai_tools_permission(request.user)
