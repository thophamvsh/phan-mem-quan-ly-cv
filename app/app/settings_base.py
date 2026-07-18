import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


load_env_file(BASE_DIR.parent / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

KHO_BACKEND_BASE_URL = os.environ.get("KHO_BACKEND_BASE_URL", "http://localhost:8000")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AI_TOOLS_PROVIDER = os.environ.get("AI_TOOLS_PROVIDER", "openai")
AI_TOOLS_OPENAI_MODEL = os.environ.get("AI_TOOLS_OPENAI_MODEL", "gpt-4o-mini")
AI_TOOLS_DEEPSEEK_MODEL = os.environ.get("AI_TOOLS_DEEPSEEK_MODEL", "deepseek-chat")
AI_TOOLS_ANTHROPIC_MODEL = os.environ.get("AI_TOOLS_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

DOCUMENTS_USE_CELERY = env_bool("DOCUMENTS_USE_CELERY", False)
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TIMEZONE = os.environ.get("CELERY_TIMEZONE", "Asia/Ho_Chi_Minh")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.environ.get("CELERY_TASK_TIME_LIMIT", "1800"))
# Cài đặt thời gian lưu trữ log (theo ngày). Mặc định là 180 ngày. Các log cũ hơn sẽ bị xóa tự động.
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "180"))

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "save-realtime-snapshots-hourly": {
        "task": "thongsothuyvan.tasks.save_all_realtime_snapshots_task",
        "schedule": crontab(minute=5),
    },
    "sync-vrain-rainfall-daily": {
        "task": "thongsothuyvan.tasks.sync_vrain_daily_rainfall_task",
        "schedule": crontab(hour=7, minute=0),
    },
    "sync-missing-thuy-van-thuc-te-daily": {
        "task": "thongsothuyvan.tasks.sync_missing_thuy_van_thuc_te_daily_task",
        "schedule": crontab(hour=8, minute=0),
    },
    "clear-old-logs-daily": {
        "task": "core.tasks.clear_old_logs_task",
        "schedule": crontab(hour=2, minute=0),
    },
}

INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'import_export',
    'django.contrib.postgres',
    'core',
    'khovattu',
    'nhatkyvanhanh',
    'quanlyvanhanh',
    'thongsothuyvan.apps.ThongsothuyvanConfig',
    'ai_tools.apps.AiToolsConfig',
    'documents.apps.DocumentsConfig',
    'drf_spectacular',
    'auditlog',
]
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.DRFAuthenticationMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'
ASGI_APPLICATION = 'app.asgi.application'

if os.environ.get('DB_HOST') and not env_bool('SQLITE'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'NAME': os.environ.get('DB_NAME', 'devdb'),
            'USER': os.environ.get('DB_USER', 'devuser'),
            'PASSWORD': os.environ.get('DB_PASS', 'changeme'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'core.User'

CORS_ALLOW_CREDENTIALS = env_bool('CORS_ALLOW_CREDENTIALS', True)
CORS_ALLOW_ALL_ORIGINS = env_bool('CORS_ALLOW_ALL_ORIGINS', False)
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if origin.strip()
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'URL_FORMAT_OVERRIDE': None,
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# =============================
# Telegram Notifications
# =============================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# =============================
# AI Tools Configurations
# =============================
AI_TOOLS_RATED_POWER_MAP = {
    "SH": 37.0,   # Sông Hinh: 37 MW/tổ máy
    "VS": 33.0,   # Vĩnh Sơn: 33 MW/tổ máy
    "TKT": 110.0, # Thượng Kon Tum: 110 MW/tổ máy
}

AI_TOOLS_RAINFALL_STATIONS = {
    "songhinh": [
        "Xa_Ea_M_doan",
        "Thon_10_Xa_Ea_M_Doal",
        "UBND_xa_Song_Hinh",
        "Cu_Kroa",
        "Xa_Ea_Trang",
        "Dap_Tran",
    ],
    "vinhson": [
        "Ho_A_TD_Vinh_Son",
        "Ho_B_TD_Vinh_Son",
        "Ho_C_TD_Vinh_Son",
    ],
}

# Nang gioi han parameter gui len tu form Django Admin de tránh loi TooManyFieldsSent khi xử lý bảng dữ liệu lớn
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000


