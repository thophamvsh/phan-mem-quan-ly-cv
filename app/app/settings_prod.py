from .settings_base import *  # noqa

DEBUG = False

SECRET_KEY = env_required('DJANGO_SECRET_KEY')
if SECRET_KEY.startswith('django-insecure') or SECRET_KEY == 'change-me-secret-key':
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be a strong production secret')

ALLOWED_HOSTS = [
    host.strip() for host in env_required('DJANGO_ALLOWED_HOSTS').split(',') if host.strip()
]
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in env_required('CORS_ALLOWED_ORIGINS').split(',') if origin.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in env_required('CSRF_TRUSTED_ORIGINS').split(',') if origin.strip()
]

for required_db_setting in ('DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASS'):
    env_required(required_db_setting)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
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

STATIC_ROOT = '/vol/web/static'
MEDIA_ROOT = '/vol/web/media'

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
