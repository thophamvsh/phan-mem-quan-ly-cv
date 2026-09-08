import ipaddress
from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from .models import UserActivityLog


def is_valid_ip(ip_str):
    if not ip_str:
        return False
    try:
        ipaddress.ip_address(ip_str.strip())
        return True
    except (ValueError, TypeError):
        return False


def is_trusted_proxy(ip_str):
    if not is_valid_ip(ip_str):
        return False
    proxy_ip = ipaddress.ip_address(ip_str.strip())
    for cidr in getattr(settings, 'TRUSTED_PROXY_CIDRS', ()):
        try:
            if proxy_ip in ipaddress.ip_network(cidr, strict=False):
                return True
        except (ValueError, TypeError):
            continue
    return False


def get_client_ip(request):
    if not request:
        return None

    remote_addr = request.META.get('REMOTE_ADDR')

    # Nếu cấu hình tin tưởng proxy headers (mặc định cho Nginx/Cloudflare)
    trust_proxy = getattr(settings, 'TRUST_PROXY_HEADERS', False)

    if trust_proxy and is_trusted_proxy(remote_addr):
        # 1. Ưu tiên Cloudflare Connecting IP nếu có
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip and is_valid_ip(cf_ip):
            return cf_ip.strip()

        # 2. Ưu tiên X-Real-IP từ Nginx reverse proxy
        real_ip = request.META.get('HTTP_X_REAL_IP')
        if real_ip and is_valid_ip(real_ip):
            return real_ip.strip()

        # 3. Lấy IP hợp lệ đầu tiên từ X-Forwarded-For
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            candidates = [part.strip() for part in x_forwarded_for.split(',')]
            for candidate in reversed(candidates):
                candidate = candidate.strip()
                if is_valid_ip(candidate) and not is_trusted_proxy(candidate):
                    return candidate

    return remote_addr


def get_user_agent(request):
    if not request:
        return ""
    return request.META.get('HTTP_USER_AGENT', '')


@receiver(user_logged_in, dispatch_uid="core.log_user_logged_in")
def log_user_logged_in(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    nha_may = getattr(user.profile, 'nha_may', None) if hasattr(user, 'profile') else None
    UserActivityLog.objects.create(
        user=user,
        action_type="LOGIN",
        description="Người dùng đăng nhập thành công",
        ip_address=ip,
        user_agent=ua,
        nha_may=nha_may
    )


@receiver(user_logged_out, dispatch_uid="core.log_user_logged_out")
def log_user_logged_out(sender, request, user, **kwargs):
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    if user:
        nha_may = getattr(user.profile, 'nha_may', None) if hasattr(user, 'profile') else None
        UserActivityLog.objects.create(
            user=user,
            action_type="LOGOUT",
            description="Người dùng đăng xuất khỏi hệ thống",
            ip_address=ip,
            user_agent=ua,
            nha_may=nha_may
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
        user_agent=ua,
        nha_may=None
    )
