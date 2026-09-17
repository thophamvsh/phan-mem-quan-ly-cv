from rest_framework import permissions


def has_ai_documents_permission(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(getattr(profile, "can_use_ai_documents", False))


class CanUseAiDocuments(permissions.BasePermission):
    message = "Ban khong co quyen su dung kho tai lieu AI."

    def has_permission(self, request, view):
        return has_ai_documents_permission(request.user)


def has_module_guide_permission(user, permission_name):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.has_effective_permission(permission_name))


def can_view_module_guides(user):
    return any(
        has_module_guide_permission(user, permission)
        for permission in (
            "can_view_module_guides",
            "can_manage_module_guides",
            "can_publish_module_guides",
        )
    )


def can_view_module_guide_history(user):
    return any(
        has_module_guide_permission(user, permission)
        for permission in (
            "can_view_module_guide_history",
            "can_manage_module_guides",
            "can_publish_module_guides",
        )
    )


def can_manage_module_guides(user):
    return has_module_guide_permission(user, "can_manage_module_guides")


def can_publish_module_guides(user):
    return has_module_guide_permission(user, "can_publish_module_guides")


def can_review_module_guides(user):
    return can_manage_module_guides(user) or can_publish_module_guides(user)


def can_download_module_guides(user):
    return has_module_guide_permission(user, "can_download_module_guides")


class CanViewModuleGuides(permissions.BasePermission):
    message = "Bạn không có quyền xem tài liệu hướng dẫn."

    def has_permission(self, request, view):
        return can_view_module_guides(request.user)


class CanViewModuleGuideHistory(permissions.BasePermission):
    message = "Bạn không có quyền xem lịch sử tài liệu hướng dẫn."

    def has_permission(self, request, view):
        return can_view_module_guide_history(request.user)


class CanManageModuleGuides(permissions.BasePermission):
    message = "Bạn không có quyền quản lý tài liệu hướng dẫn."

    def has_permission(self, request, view):
        return can_manage_module_guides(request.user)


class CanPublishModuleGuides(permissions.BasePermission):
    message = "Bạn không có quyền phê duyệt tài liệu hướng dẫn."

    def has_permission(self, request, view):
        return can_publish_module_guides(request.user)


class CanAccessModuleGuideContent(permissions.BasePermission):
    message = "Bạn không có quyền mở nội dung tài liệu hướng dẫn."

    def has_permission(self, request, view):
        user = request.user
        return (
            can_view_module_guides(user)
            or can_view_module_guide_history(user)
            or can_review_module_guides(user)
        )
