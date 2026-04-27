from rest_framework import permissions


def has_profile_permission(user, permission_name):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True

    try:
        profile = user.profile
    except Exception:
        return False

    return bool(getattr(profile, permission_name, False))


class UserProfilePermission(permissions.BasePermission):
    permission_name = None

    def has_permission(self, request, view):
        return has_profile_permission(request.user, self.permission_name)


class CanViewOperationEvents(UserProfilePermission):
    permission_name = "can_view_operation_events"


class CanCreateOperationEvents(UserProfilePermission):
    permission_name = "can_create_operation_events"


class CanAcknowledgeOperationEvents(UserProfilePermission):
    permission_name = "can_acknowledge_operation_events"


class CanProcessOperationEvents(UserProfilePermission):
    permission_name = "can_process_operation_events"


class CanConfirmOperationEvents(UserProfilePermission):
    permission_name = "can_confirm_operation_events"


class CanAddEventDevelopments(UserProfilePermission):
    permission_name = "can_add_event_developments"
