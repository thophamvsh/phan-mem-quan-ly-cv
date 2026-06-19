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
