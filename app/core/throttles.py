from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class RegistrationRateThrottle(AnonRateThrottle):
    scope = "register"


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class TokenRateThrottle(AnonRateThrottle):
    scope = "token"


class AiRateThrottle(UserRateThrottle):
    scope = "ai"


class AuditExportRateThrottle(UserRateThrottle):
    scope = "audit_export"
    rate = "10/minute"


class MonthlySwitchQRResolveRateThrottle(UserRateThrottle):
    scope = "monthly_switch_qr_resolve"


class MonthlySwitchQRSaveRateThrottle(UserRateThrottle):
    scope = "monthly_switch_qr_save"


class WeeklySwitchQRReadRateThrottle(UserRateThrottle):
    scope = "weekly_switch_qr_read"


class WeeklySwitchQRWriteRateThrottle(UserRateThrottle):
    scope = "weekly_switch_qr_write"
