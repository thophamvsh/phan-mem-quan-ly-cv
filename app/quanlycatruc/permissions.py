from rest_framework.permissions import BasePermission


def has_profile_permission(user, permission):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return bool(getattr(getattr(user, "profile", None), permission, False))


def can_access_plant(user, plant_id):
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    return bool(profile.is_all_factories or (profile.nha_may_id and str(profile.nha_may_id) == str(plant_id)))


class ShiftSchedulePermission(BasePermission):
    action_permissions = {
        "list": "can_view_shift_schedule", "retrieve": "can_view_shift_schedule",
        "create": "can_create_shift_schedule", "destroy": "can_delete_shift_schedule",
        "update": "can_edit_shift_schedule", "partial_update": "can_edit_shift_schedule",
        "sinh_lich": "can_create_shift_schedule", "gui_duyet": "can_submit_shift_schedule",
        "phe_duyet": "can_approve_shift_schedule", "tu_choi": "can_approve_shift_schedule",
        "ap_dung": "can_approve_shift_schedule", "khoa": "can_approve_shift_schedule",
        "xuat_excel": "can_export_shift_schedule", "xuat_pdf": "can_export_shift_schedule",
    }

    def has_permission(self, request, view):
        return has_profile_permission(request.user, self.action_permissions.get(view.action, "can_view_shift_schedule"))

    def has_object_permission(self, request, view, obj):
        plant_id = getattr(obj, "nha_may_id", None) or getattr(getattr(obj, "lich_truc", None), "nha_may_id", None)
        return can_access_plant(request.user, plant_id)


class RosterPermission(BasePermission):
    def has_permission(self, request, view):
        permission = "can_view_shift_schedule" if request.method in {"GET", "HEAD", "OPTIONS"} else "can_manage_shift_roster"
        return has_profile_permission(request.user, permission)

    def has_object_permission(self, request, view, obj):
        unit = getattr(obj, "don_vi", None)
        plant_id = (
            getattr(obj, "nha_may_id", None)
            or getattr(unit, "nha_may_pham_vi_id", None)
            or getattr(getattr(obj, "kip_truc", None), "nha_may_id", None)
        )
        return can_access_plant(request.user, plant_id)


class ShiftAdjustmentPermission(BasePermission):
    def has_permission(self, request, view):
        if view.action in {"phe_duyet", "tu_choi", "phe_duyet_phieu", "tu_choi_phieu"}:
            return has_profile_permission(request.user, "can_approve_shift_schedule")
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return has_profile_permission(request.user, "can_view_shift_schedule")
        return (
            has_profile_permission(request.user, "can_manage_shift_roster")
            or has_profile_permission(request.user, "can_edit_shift_schedule")
            or has_profile_permission(request.user, "can_delete_shift_schedule")
            or has_profile_permission(request.user, "can_create_shift_schedule")
            or has_profile_permission(request.user, "can_approve_shift_schedule")
        )

    def has_object_permission(self, request, view, obj):
        return can_access_plant(request.user, obj.ngay_truc.lich_truc.nha_may_id)
