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
                return True  # Nếu không có factory trong request, cho phép

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
