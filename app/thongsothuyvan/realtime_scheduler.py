import logging
import os
import sys
import threading
import time

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_lock = threading.Lock()

DEFAULT_HOURLY_GRACE_MINUTES = 5
DEFAULT_VRAIN_INTERVAL_SECONDS = 60 * 60
DEFAULT_POLL_SECONDS = 60
SKIP_COMMANDS = {
    "collectstatic",
    "check",
    "createsuperuser",
    "makemigrations",
    "migrate",
    "save_realtime_snapshots",
    "shell",
    "showmigrations",
    "test",
    "wait_for_db",
}


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def should_start_realtime_scheduler():
    # Disable the custom background thread scheduler if Celery is enabled,
    # as Celery Beat will handle the periodic snapshots instead.
    if getattr(settings, "DOCUMENTS_USE_CELERY", False):
        return False

    if not _env_bool("REALTIME_SNAPSHOT_SCHEDULER_ENABLED", True):
        return False

    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command in SKIP_COMMANDS:
        return False

    if command == "runserver" and os.environ.get("RUN_MAIN") != "true":
        return False

    return True


def _scheduler_loop():
    hourly_grace_minutes = _env_int(
        "REALTIME_SNAPSHOT_HOURLY_GRACE_MINUTES",
        getattr(
            settings,
            "REALTIME_SNAPSHOT_HOURLY_GRACE_MINUTES",
            DEFAULT_HOURLY_GRACE_MINUTES,
        ),
    )
    poll_seconds = _env_int(
        "REALTIME_SNAPSHOT_POLL_SECONDS",
        getattr(settings, "REALTIME_SNAPSHOT_POLL_SECONDS", DEFAULT_POLL_SECONDS),
    )
    vrain_enabled = _env_bool("VRAIN_DAILY_SYNC_ENABLED", True)
    vrain_interval_seconds = _env_int(
        "VRAIN_DAILY_SYNC_INTERVAL_SECONDS",
        getattr(settings, "VRAIN_DAILY_SYNC_INTERVAL_SECONDS", DEFAULT_VRAIN_INTERVAL_SECONDS),
    )
    last_vrain_sync_at = 0

    logger.info(
        "Realtime snapshot scheduler started: hourly_grace=%sm poll=%ss vrain_enabled=%s vrain_interval=%ss",
        hourly_grace_minutes,
        poll_seconds,
        vrain_enabled,
        vrain_interval_seconds,
    )

    while True:
        try:
            close_old_connections()
            from .realtime_services import (
                claim_realtime_snapshot_hourly_slot,
                save_all_realtime_snapshots,
            )

            if claim_realtime_snapshot_hourly_slot(
                grace_minutes=hourly_grace_minutes
            ):
                save_all_realtime_snapshots(mark_run=False)

            now = time.time()
            if vrain_enabled and now - last_vrain_sync_at >= vrain_interval_seconds:
                from .vrain_services import sync_vrain_daily_rainfall

                last_vrain_sync_at = now
                sync_vrain_daily_rainfall()
        except Exception:
            logger.exception("Realtime snapshot scheduler failed")
        finally:
            close_old_connections()
            time.sleep(max(10, poll_seconds))


def start_realtime_scheduler():
    global _scheduler_started

    if not should_start_realtime_scheduler():
        return

    with _scheduler_lock:
        if _scheduler_started:
            return

        thread = threading.Thread(
            target=_scheduler_loop,
            name="realtime-snapshot-scheduler",
            daemon=True,
        )
        thread.start()
        _scheduler_started = True
