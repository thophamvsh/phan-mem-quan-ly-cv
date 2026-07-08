from .settings_base import *  # noqa

DEBUG = False

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['localhost']

CORS_ALLOW_ALL_ORIGINS = False

STATIC_ROOT = '/vol/web/static'
MEDIA_ROOT = '/vol/web/media'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
