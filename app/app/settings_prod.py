from urllib.parse import urlparse

from .settings_base import *  # noqa

DEBUG = False

SECRET_KEY = env_required('DJANGO_SECRET_KEY')
if (
    SECRET_KEY.startswith('django-insecure')
    or SECRET_KEY.lower().startswith('replace-')
    or SECRET_KEY in {'change-me-secret-key', 'changeme', 'change-me'}
    or len(SECRET_KEY) < 50
):
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be a strong production secret')

ALLOWED_HOSTS = [
    host.strip() for host in env_required('DJANGO_ALLOWED_HOSTS').split(',') if host.strip()
]
if '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must not contain * in production')

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in env_required('CORS_ALLOWED_ORIGINS').split(',') if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in env_required('CSRF_TRUSTED_ORIGINS').split(',') if origin.strip()
]

for setting_name, origins in (
    ('CORS_ALLOWED_ORIGINS', CORS_ALLOWED_ORIGINS),
    ('CSRF_TRUSTED_ORIGINS', CSRF_TRUSTED_ORIGINS),
):
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.scheme != 'https' or not parsed.netloc:
            raise ImproperlyConfigured(
                f'{setting_name} must contain only absolute HTTPS origins in production'
            )

for required_db_setting in ('DB_HOST', 'DB_NAME', 'DB_USER'):
    env_required(required_db_setting)

DB_PASSWORD = env_required('DB_PASS')
if (
    DB_PASSWORD.lower().startswith('replace-')
    or DB_PASSWORD.lower() in {'changeme', 'change-me', 'password', 'postgres'}
    or len(DB_PASSWORD) < 16
):
    raise ImproperlyConfigured('DB_PASS must not use a default production password')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
if not SECURE_SSL_REDIRECT:
    raise ImproperlyConfigured('SECURE_SSL_REDIRECT must be enabled in production')

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', True)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', False)
X_FRAME_OPTIONS = 'DENY'

CORS_ALLOW_ALL_ORIGINS = False

AUTH_COOKIE_SECURE = env_bool('AUTH_COOKIE_SECURE', True)
if not AUTH_COOKIE_SECURE:
    raise ImproperlyConfigured('AUTH_COOKIE_SECURE must be enabled in production')

STATIC_ROOT = '/vol/web/static'
MEDIA_ROOT = '/vol/web/media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
