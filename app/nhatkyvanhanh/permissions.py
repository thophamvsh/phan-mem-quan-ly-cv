from rest_framework import permissions


def has_profile_permission(user, permission_name):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
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


class CanViewShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_view_shift_handover_logs"


class CanCreateShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_create_shift_handover_logs"


class CanReceiveShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_receive_shift_handover_logs"


class CanViewAdminShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_view_admin_shift_handover_logs"


class CanCreateAdminShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_create_admin_shift_handover_logs"


class CanReceiveAdminShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_receive_admin_shift_handover_logs"


class CanViewOperationLogbooks(UserProfilePermission):
    permission_name = "can_view_operation_logbooks"


class CanCreateOperationLogbooks(UserProfilePermission):
    permission_name = "can_create_operation_logbooks"


class CanConfirmOperationLogbooks(UserProfilePermission):
    permission_name = "can_confirm_operation_logbooks"


class CanViewDieselOperationLogbooks(UserProfilePermission):
    permission_name = "can_view_diesel_operation_logbooks"


class CanCreateDieselOperationLogbooks(UserProfilePermission):
    permission_name = "can_create_diesel_operation_logbooks"
