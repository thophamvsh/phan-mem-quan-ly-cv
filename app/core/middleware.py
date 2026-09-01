class DRFAuthenticationMiddleware:
    """
    Middleware to force DRF JWT authentication early in the request lifecycle.
    This ensures that django-auditlog middleware can capture the correct logged-in
    JWT user (e.g., hoaxh) instead of falling back to session-based users (e.g., thovsh@gmail.com)
    or AnonymousUser.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only attempt JWT auth if the Authorization header is present
        header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
        if header and (header.startswith('Bearer ') or header.startswith('bearer ')):
            try:
                from rest_framework_simplejwt.authentication import JWTAuthentication
                authenticator = JWTAuthentication()
                auth_result = authenticator.authenticate(request)
                if auth_result:
                    request.user = auth_result[0]
            except Exception:
                # If authentication fails, let DRF handle it in the view (e.g. returning 401/403)
                pass
        return self.get_response(request)


class LegacyApiDeprecationMiddleware:
    """Advertise the versioned successor without breaking legacy clients."""

    excluded_paths = (
        "/api/v1/",
        "/api/schema/",
        "/api/docs/",
        "/api/redoc/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        is_legacy = request.path.startswith("/api/") and not any(
            request.path.startswith(path) for path in self.excluded_paths
        )
        if is_legacy:
            response["Deprecation"] = "true"
            response["Sunset"] = "Fri, 31 Dec 2027 23:59:59 GMT"
            response["Link"] = '</api/v1/>; rel="successor-version"'
        return response
