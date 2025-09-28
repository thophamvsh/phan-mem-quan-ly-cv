#!/usr/bin/env bash
set -euo pipefail

echo "[run-dev] starting…"

# ===== Defaults & env =====
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-app.settings}"
PORT="${PORT:-8000}"

# ===== FS layout =====
mkdir -p /vol/web/static /vol/web/media /vol/web/logs

# ===== Wait for DB & migrate =====
echo "[run-dev] waiting for database…"
python manage.py wait_for_db

echo "[run-dev] applying migrations…"
python manage.py migrate --noinput

# ===== Optional: collectstatic in dev =====
if [[ "${COLLECTSTATIC:-0}" = "1" ]]; then
  echo "[run-dev] collectstatic…"
  python manage.py collectstatic --noinput
fi

# ===== Optional: create superuser =====
# Set env before running (ví dụ):
#   DJANGO_SUPERUSER_USERNAME=admin
#   DJANGO_SUPERUSER_EMAIL=admin@example.com
#   DJANGO_SUPERUSER_PASSWORD=admin123
if [[ "${DJANGO_SUPERUSER_USERNAME:-}" != "" ]]; then
  echo "[run-dev] creating superuser if missing…"
  python manage.py createsuperuser --noinput || true
fi

# ===== Run server (with optional debugpy) =====
if [[ "${DEBUGPY:-0}" = "1" ]]; then
  DBG_PORT="${DEBUGPY_PORT:-5678}"
  echo "[run-dev] starting with debugpy on ${DBG_PORT}, app on ${PORT}…"
  # debugpy sẽ attach vào manage.py runserver
  exec python -m debugpy --listen 0.0.0.0:"${DBG_PORT}" manage.py runserver 0.0.0.0:"${PORT}"
else
  echo "[run-dev] starting Django runserver on ${PORT}…"
  exec python manage.py runserver 0.0.0.0:"${PORT}"
fi
