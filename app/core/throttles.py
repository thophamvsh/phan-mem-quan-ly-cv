from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class RegistrationRateThrottle(AnonRateThrottle):
    scope = "register"


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class TokenRateThrottle(AnonRateThrottle):
    scope = "token"


class AiRateThrottle(UserRateThrottle):
    scope = "ai"
