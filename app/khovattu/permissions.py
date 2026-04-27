"""
Custom permissions for khovattu app
"""
from rest_framework import permissions


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow authenticated users to edit objects.
    Anonymous users can read.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed for authenticated users
        return request.user and request.user.is_authenticated


class HasFactoryAccess(permissions.BasePermission):
    """
    Permission to check if user has access to specific factory
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser có quyền truy cập tất cả
        if request.user.is_superuser:
            return True

        # Staff user có quyền truy cập tất cả
        if request.user.is_staff:
            return True

        # Kiểm tra UserProfile
        try:
            profile = request.user.profile

            # User có quyền truy cập tất cả nhà máy
            if profile.is_all_factories:
                return True

            # User chỉ có quyền truy cập nhà máy cụ thể
            if profile.nha_may:
                # Lấy ma_nha_may từ request (có thể từ URL params hoặc query params)
                request_factory = self._get_factory_from_request(request)
                if request_factory:
                    return profile.nha_may.ma_nha_may == request_factory
                # Nếu không có factory trong request, cho phép nhưng sẽ filter ở view level
                return True

            # User chưa được gán nhà máy - không có quyền truy cập
            return False

        except Exception:
            # Nếu không có profile hoặc lỗi, không cho phép
            return False

    def _get_factory_from_request(self, request):
        """
        Extract factory code from request (URL params or query params)
        """
        # Thử lấy từ URL params trước
        factory = None

        # Check URL parameters (ma_nha_may)
        if hasattr(request, 'resolver_match') and request.resolver_match:
            kwargs = request.resolver_match.kwargs
            factory = kwargs.get('ma_nha_may')

        # Check query parameters
        if not factory:
            factory = request.query_params.get('ma_nha_may')

        # Check POST data
        if not factory and request.method in ['POST', 'PATCH', 'PUT']:
            if hasattr(request, 'data'):
                factory = request.data.get('ma_nha_may')

        return factory


class HasSpecificFactoryAccess(permissions.BasePermission):
    """
    Permission to check access to specific factory code
    """
    def __init__(self, factory_code=None):
        self.factory_code = factory_code

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        # Kiểm tra UserProfile
        try:
            profile = request.user.profile

            # User có quyền truy cập tất cả nhà máy
            if profile.is_all_factories:
                return True

            # User chỉ có quyền truy cập nhà máy cụ thể
            if profile.nha_may:
                target_factory = self.factory_code or self._get_factory_from_request(request)
                if target_factory:
                    return profile.nha_may.ma_nha_may == target_factory
                return True  # Nếu không có factory target, cho phép

            return False

        except Exception:
            return False

    def _get_factory_from_request(self, request):
        """Extract factory code from request"""
        # Check URL parameters
        if hasattr(request, 'resolver_match') and request.resolver_match:
            kwargs = request.resolver_match.kwargs
            return kwargs.get('ma_nha_may')

        # Check query parameters
        return request.query_params.get('ma_nha_may')


class HasFactoryAccessStrict(permissions.BasePermission):
    """
    Strict permission that requires factory code in request
    Used for APIs that must specify factory (like create export request)
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        # Kiểm tra UserProfile
        try:
            profile = request.user.profile

            # User có quyền truy cập tất cả nhà máy
            if profile.is_all_factories:
                return True

            # User chỉ có quyền truy cập nhà máy cụ thể
            if profile.nha_may:
                request_factory = self._get_factory_from_request(request)
                if request_factory:
                    return profile.nha_may.ma_nha_may == request_factory
                # Nếu không có factory trong request, KHÔNG cho phép
                return False

            return False

        except Exception:
            return False

    def _get_factory_from_request(self, request):
        """Extract factory code from request"""
        # Check URL parameters
        if hasattr(request, 'resolver_match') and request.resolver_match:
            kwargs = request.resolver_match.kwargs
            factory = kwargs.get('ma_nha_may')
            if factory:
                return factory

        # Check query parameters
        factory = request.query_params.get('ma_nha_may')
        if factory:
            return factory

        # Check POST data
        if request.method in ['POST', 'PATCH', 'PUT']:
            if hasattr(request, 'data'):
                factory = request.data.get('ma_nha_may')
                if factory:
                    return factory

        return None


class CanViewMaterials(permissions.BasePermission):
    """Permission to view materials"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_view_materials
        except Exception:
            return False


class CanAddMaterials(permissions.BasePermission):
    """Permission to add materials"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_add_materials
        except Exception:
            return False


class CanEditMaterials(permissions.BasePermission):
    """Permission to edit materials"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_edit_materials
        except Exception:
            return False


class CanDeleteMaterials(permissions.BasePermission):
    """Permission to delete materials"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_delete_materials
        except Exception:
            return False


class CanImportExcel(permissions.BasePermission):
    """Permission to import Excel"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_import_excel
        except Exception:
            return False


class CanExportExcel(permissions.BasePermission):
    """Permission to export Excel"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_export_excel
        except Exception:
            return False


class CanCreateExportRequest(permissions.BasePermission):
    """Permission to create export request"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_create_export_request
        except Exception:
            return False


class CanApproveExportRequest(permissions.BasePermission):
    """Permission to approve export request"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_approve_export_request
        except Exception:
            return False


class CanCreateImportRequest(permissions.BasePermission):
    """Permission to create import request"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_create_import_request
        except Exception:
            return False


class CanApproveImportRequest(permissions.BasePermission):
    """Permission to approve import request"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_approve_import_request
        except Exception:
            return False


class CanViewInventory(permissions.BasePermission):
    """Permission to view inventory"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_view_inventory
        except Exception:
            return False


class CanEditInventory(permissions.BasePermission):
    """Permission to edit inventory"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_edit_inventory
        except Exception:
            return False


class CanViewReports(permissions.BasePermission):
    """Permission to view reports"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superuser và staff có quyền truy cập tất cả
        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            return profile.can_view_reports
        except Exception:
            return False


class CanViewImportRequest(permissions.BasePermission):
    """Permission to view import request data"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            # User can view if they have view permission or any import-related permissions
            return (profile.can_view_import_requests or
                   profile.can_view_materials or
                   profile.can_create_import_request or
                   profile.can_approve_import_request)
        except Exception:
            return False


class CanViewExportRequest(permissions.BasePermission):
    """Permission to view export request data"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.is_staff:
            return True

        try:
            profile = request.user.profile
            # User can view if they have view permission or any export-related permissions
            return (profile.can_view_export_requests or
                   profile.can_view_materials or
                   profile.can_create_export_request or
                   profile.can_approve_export_request)
        except Exception:
            return False


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission to only allow admins to edit objects.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed for admins
        return request.user and request.user.is_staff
