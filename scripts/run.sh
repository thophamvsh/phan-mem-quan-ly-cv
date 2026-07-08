#!/bin/sh
set -eu

echo "🚀 Starting VSH Project..."

# ----- ENV & defaults -----
: "${DJANGO_SETTINGS_MODULE:=app.settings}"
: "${PORT:=8000}"
: "${WSGI_SERVER:=gunicorn}"   # gunicorn | uwsgi
: "${RUN_MIGRATIONS:=1}"       # 0 to skip migrations during container startup
: "${CREATE_SUPERUSER:=0}"     # 1 để bật tạo superuser tự động
: "${COLLECTSTATIC:=1}"        # 0 để bỏ qua collectstatic (ví dụ trong dev)

# lowercase DEBUG for comparison
DEBUG_LC="$(echo "${DEBUG:-False}" | tr '[:upper:]' '[:lower:]')"

# ----- FS layout -----
mkdir -p /vol/web/static /vol/web/media /vol/web/logs || true

# ----- Wait for DB & migrate -----
echo "⏳ Waiting for database..."
python manage.py wait_for_db

if [ "$RUN_MIGRATIONS" = "1" ]; then
  echo "📊 Applying database migrations..."
  python manage.py migrate --noinput
else
  echo "Skip migrations (RUN_MIGRATIONS=0)"
fi

# ----- Collect static (optional) -----
if [ "$COLLECTSTATIC" = "1" ]; then
  echo "📁 Collecting static files..."
  python manage.py collectstatic --noinput
else
  echo "📁 Skip collectstatic (COLLECTSTATIC=0)"
fi

# ----- Create superuser (optional) -----
# Cấu hình các biến trước khi chạy container để tự tạo:
# DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD
if [ "$CREATE_SUPERUSER" = "1" ] && [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ]; then
  echo "👤 Ensuring superuser exists..."
  python manage.py createsuperuser --noinput || true
else
  echo "👤 Skip creating superuser (CREATE_SUPERUSER=0 or missing DJANGO_SUPERUSER_EMAIL)"
fi

# ----- Start server -----
trap 'echo "🛑 Stopping..."; exit 0' TERM INT

if [ "$DEBUG_LC" = "true" ] || [ "$DEBUG_LC" = "1" ]; then
  echo "🔧 Development mode - Django runserver on 0.0.0.0:${PORT}"
  exec python manage.py runserver 0.0.0.0:"${PORT}"
else
  case "$WSGI_SERVER" in
    uwsgi)
      echo "🚀 Production mode - uWSGI on 0.0.0.0:${PORT}"
      # dùng HTTP mode trực tiếp (đơn giản) hoặc socket + nginx tuỳ kiến trúc của bạn
      exec uwsgi \
        --http 0.0.0.0:"${PORT}" \
        --wsgi-file app/wsgi.py \
        --master --enable-threads \
        --processes "${UWSGI_PROCESSES:-4}" \
        --threads "${UWSGI_THREADS:-2}" \
        --vacuum --die-on-term
      ;;
    *)
      echo "🚀 Production mode - Gunicorn on 0.0.0.0:${PORT}"
      exec gunicorn app.wsgi:application \
        --bind 0.0.0.0:"${PORT}" \
        --workers "${GUNICORN_WORKERS:-3}" \
        --threads "${GUNICORN_THREADS:-2}" \
        --timeout "${GUNICORN_TIMEOUT:-120}" \
        --no-control-socket \
        --access-logfile "-" --error-logfile "-"
      ;;
  esac
fi
