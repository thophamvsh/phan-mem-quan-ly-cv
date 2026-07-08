from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import UserActivityLog

def get_client_ip(request):
    if not request:
        return None
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_user_agent(request):
    if not request:
        return ""
    return request.META.get('HTTP_USER_AGENT', '')

@receiver(user_logged_in, dispatch_uid="core.log_user_logged_in")
def log_user_logged_in(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    UserActivityLog.objects.create(
        user=user,
        action_type="LOGIN",
        description="Người dùng đăng nhập thành công",
        ip_address=ip,
        user_agent=ua
    )

@receiver(user_logged_out, dispatch_uid="core.log_user_logged_out")
def log_user_logged_out(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    if user:
        UserActivityLog.objects.create(
            user=user,
            action_type="LOGOUT",
            description="Người dùng đăng xuất khỏi hệ thống",
            ip_address=ip,
            user_agent=ua
        )

@receiver(user_login_failed, dispatch_uid="core.log_user_login_failed")
def log_user_login_failed(sender, credentials, request, **kwargs):
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    username = credentials.get('username') or credentials.get('email') or 'Unknown'
    UserActivityLog.objects.create(
        user=None,
        action_type="LOGIN_FAILED",
        description=f"Đăng nhập thất bại cho tài khoản: {username}",
        ip_address=ip,
        user_agent=ua
    )
