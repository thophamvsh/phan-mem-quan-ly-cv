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


class AnyUserProfilePermission(permissions.BasePermission):
    permission_names = ()

    def has_permission(self, request, view):
        return any(
            has_profile_permission(request.user, permission_name)
            for permission_name in self.permission_names
        )


class CanViewOperationEvents(UserProfilePermission):
    permission_name = "can_view_operation_events"


class CanCreateOperationEvents(UserProfilePermission):
    permission_name = "can_create_operation_events"


class CanEditOperationEvents(AnyUserProfilePermission):
    permission_names = (
        "can_edit_own_operation_events",
        "can_edit_all_operation_events",
        "can_edit_leadership_directives",
    )


class CanDeleteOperationEvents(AnyUserProfilePermission):
    permission_names = (
        "can_delete_own_operation_events",
        "can_delete_all_operation_events",
    )


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


class CanEditShiftHandoverLogs(AnyUserProfilePermission):
    permission_names = (
        "can_edit_own_shift_handover_logs",
        "can_manage_all_shift_handover_logs",
    )


class CanDeleteShiftHandoverLogs(AnyUserProfilePermission):
    permission_names = (
        "can_delete_own_shift_handover_logs",
        "can_manage_all_shift_handover_logs",
    )


class CanExportNightShiftReport(AnyUserProfilePermission):
    permission_names = (
        "can_export_night_shift_report",
        "can_manage_all_shift_handover_logs",
    )


class CanViewAdminShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_view_admin_shift_handover_logs"


class CanCreateAdminShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_create_admin_shift_handover_logs"


class CanReceiveAdminShiftHandoverLogs(UserProfilePermission):
    permission_name = "can_receive_admin_shift_handover_logs"


class CanEditAdminShiftHandoverLogs(AnyUserProfilePermission):
    permission_names = (
        "can_edit_admin_shift_handover_logs",
        "can_create_admin_shift_handover_logs",
    )


class CanDeleteAdminShiftHandoverLogs(AnyUserProfilePermission):
    permission_names = (
        "can_delete_admin_shift_handover_logs",
        "can_create_admin_shift_handover_logs",
    )


class CanViewAdminShiftDutyRosters(UserProfilePermission):
    permission_name = "can_view_admin_shift_duty_rosters"


class CanCreateAdminShiftDutyRosters(UserProfilePermission):
    permission_name = "can_create_admin_shift_duty_rosters"


class CanEditAdminShiftDutyRosters(AnyUserProfilePermission):
    permission_names = (
        "can_edit_admin_shift_duty_rosters",
        "can_create_admin_shift_duty_rosters",
    )


class CanDeleteAdminShiftDutyRosters(AnyUserProfilePermission):
    permission_names = (
        "can_delete_admin_shift_duty_rosters",
        "can_create_admin_shift_duty_rosters",
    )


class CanViewOperationLogbooks(UserProfilePermission):
    permission_name = "can_view_operation_logbooks"


class CanCreateOperationLogbooks(UserProfilePermission):
    permission_name = "can_create_operation_logbooks"


class CanConfirmOperationLogbooks(UserProfilePermission):
    permission_name = "can_confirm_operation_logbooks"


class CanEditOperationLogbooks(AnyUserProfilePermission):
    permission_names = (
        "can_edit_operation_logbooks",
        "can_create_operation_logbooks",
    )


class CanDeleteOperationLogbooks(AnyUserProfilePermission):
    permission_names = (
        "can_delete_operation_logbooks",
        "can_create_operation_logbooks",
    )


class CanViewWeeklyEquipmentSwitchLogs(UserProfilePermission):
    permission_name = "can_view_weekly_equipment_switch_logs"


class CanCreateWeeklyEquipmentSwitchLogs(UserProfilePermission):
    permission_name = "can_create_weekly_equipment_switch_logs"


class CanEditWeeklyEquipmentSwitchLogs(AnyUserProfilePermission):
    permission_names = (
        "can_edit_own_weekly_equipment_switch_logs",
        "can_manage_all_weekly_equipment_switch_logs",
    )


class CanDeleteWeeklyEquipmentSwitchLogs(AnyUserProfilePermission):
    permission_names = (
        "can_delete_own_weekly_equipment_switch_logs",
        "can_manage_all_weekly_equipment_switch_logs",
    )


class CanConfirmWeeklyEquipmentSwitchLogs(AnyUserProfilePermission):
    permission_names = (
        "can_confirm_weekly_equipment_switch_logs",
        "can_manage_all_weekly_equipment_switch_logs",
    )


class CanViewMonthlyEquipmentSwitchTemplates(AnyUserProfilePermission):
    permission_names = (
        "can_view_monthly_equipment_switch_templates",
        "can_create_monthly_equipment_switch_templates",
        "can_edit_monthly_equipment_switch_templates",
        "can_delete_monthly_equipment_switch_templates",
        "can_manage_all_monthly_equipment_switch_logs",
    )


class CanCreateMonthlyEquipmentSwitchTemplates(AnyUserProfilePermission):
    permission_names = (
        "can_create_monthly_equipment_switch_templates",
        "can_manage_all_monthly_equipment_switch_logs",
    )


class CanEditMonthlyEquipmentSwitchTemplates(AnyUserProfilePermission):
    permission_names = (
        "can_edit_monthly_equipment_switch_templates",
        "can_manage_all_monthly_equipment_switch_logs",
    )


class CanDeleteMonthlyEquipmentSwitchTemplates(AnyUserProfilePermission):
    permission_names = (
        "can_delete_monthly_equipment_switch_templates",
        "can_manage_all_monthly_equipment_switch_logs",
    )


class CanViewMonthlyEquipmentSwitchLogs(UserProfilePermission):
    permission_name = "can_view_monthly_equipment_switch_logs"


class CanCreateMonthlyEquipmentSwitchLogs(UserProfilePermission):
    permission_name = "can_create_monthly_equipment_switch_logs"


class CanEditMonthlyEquipmentSwitchLogs(AnyUserProfilePermission):
    permission_names = (
        "can_edit_own_monthly_equipment_switch_logs",
        "can_manage_all_monthly_equipment_switch_logs",
    )


class CanDeleteMonthlyEquipmentSwitchLogs(AnyUserProfilePermission):
    permission_names = (
        "can_delete_own_monthly_equipment_switch_logs",
        "can_manage_all_monthly_equipment_switch_logs",
    )


class CanConfirmMonthlyEquipmentSwitchLogs(AnyUserProfilePermission):
    permission_names = (
        "can_confirm_monthly_equipment_switch_logs",
        "can_manage_all_monthly_equipment_switch_logs",
    )


class CanViewDieselOperationLogbooks(UserProfilePermission):
    permission_name = "can_view_diesel_operation_logbooks"


class CanCreateDieselOperationLogbooks(UserProfilePermission):
    permission_name = "can_create_diesel_operation_logbooks"


class CanEditDieselOperationLogbooks(AnyUserProfilePermission):
    permission_names = (
        "can_edit_own_diesel_operation_logbooks",
        "can_manage_all_diesel_operation_logbooks",
    )


class CanDeleteDieselOperationLogbooks(AnyUserProfilePermission):
    permission_names = (
        "can_delete_own_diesel_operation_logbooks",
        "can_manage_all_diesel_operation_logbooks",
    )


class CanViewBCHCSongHinh(UserProfilePermission):
    permission_name = "can_view_bchc_song_hinh"


class CanCreateBCHCSongHinh(UserProfilePermission):
    permission_name = "can_create_bchc_song_hinh"


class CanEditBCHCSongHinh(UserProfilePermission):
    permission_name = "can_edit_bchc_song_hinh"


class CanViewSoAnToanDauGio(UserProfilePermission):
    permission_name = "can_view_so_an_toan_dau_gio"


class CanCreateSoAnToanDauGio(UserProfilePermission):
    permission_name = "can_create_so_an_toan_dau_gio"


class IsShiftLogCreator(permissions.BasePermission):
    message = "Chi user tao so giao nhan ca moi duoc ky giao ca."

    def has_object_permission(self, request, view, obj):
        from .views.helpers import _is_creator_of_shift_log
        return _is_creator_of_shift_log(request.user, obj)


class IsNotShiftLogCreator(permissions.BasePermission):
    message = "User giao ca khong duoc tu ky nhan ca."

    def has_object_permission(self, request, view, obj):
        return obj.user_giao_ca_id != request.user.id
