from celery import shared_task
import logging
from datetime import timedelta
from django.db import close_old_connections
from django.utils import timezone

from thongsothuyvan.google_sheet_services import GoogleSheetHydrologyService

logger = logging.getLogger(__name__)

AUTO_SYNC_USER_EMAIL = "system_auto_sync@example.local"
AUTO_SYNC_USERNAME = "system_auto_sync"


def get_auto_sync_user():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        email=AUTO_SYNC_USER_EMAIL,
        defaults={
            "username": AUTO_SYNC_USERNAME,
            "first_name": "System",
            "last_name": "Auto Sync",
            "is_active": True,
        },
    )
    return user


def can_auto_sync_modify(user, obj):
    created_by_id = getattr(obj, "created_by_id", None)
    return created_by_id is None or created_by_id == getattr(user, "id", None)


def get_missing_thuc_te_sync_range(nhamay, end_date):
    from thongsothuyvan.google_sheet_services import GOOGLE_SHEET_SYNC_START_DATE
    from thongsothuyvan.models import ThongSoThuyVanThucTe

    latest_day = (
        ThongSoThuyVanThucTe.objects.filter(nha_may=nhamay)
        .order_by("-ngay")
        .values_list("ngay", flat=True)
        .first()
    )
    start_date = (latest_day + timedelta(days=1)) if latest_day else GOOGLE_SHEET_SYNC_START_DATE
    if start_date > end_date:
        return None
    return start_date, end_date


@shared_task
def save_all_realtime_snapshots_task():
    """
    Celery task to save all realtime snapshots (hourly).
    """
    logger.info("Celery Task: save_all_realtime_snapshots_task started.")
    try:
        from thongsothuyvan.realtime_services import save_all_realtime_snapshots
        save_all_realtime_snapshots(mark_run=False)
        logger.info("Celery Task: save_all_realtime_snapshots_task completed successfully.")
    except Exception as e:
        logger.exception("Celery Task: save_all_realtime_snapshots_task failed.")
        raise
    finally:
        close_old_connections()


@shared_task
def sync_vrain_daily_rainfall_task():
    """
    Celery task to sync VRAIN daily rainfall data.
    """
    logger.info("Celery Task: sync_vrain_daily_rainfall_task started.")
    try:
        from thongsothuyvan.vrain_services import sync_vrain_daily_rainfall
        sync_vrain_daily_rainfall()
        logger.info("Celery Task: sync_vrain_daily_rainfall_task completed successfully.")
    except Exception as e:
        logger.exception("Celery Task: sync_vrain_daily_rainfall_task failed.")
        raise
    finally:
        close_old_connections()


@shared_task
def sync_missing_thuy_van_thuc_te_daily_task():
    """
    Celery task to sync missing actual hydrology records through yesterday.
    """
    logger.info("Celery Task: sync_missing_thuy_van_thuc_te_daily_task started.")
    try:
        end_date = timezone.localdate() - timedelta(days=1)
        user = get_auto_sync_user()
        service = GoogleSheetHydrologyService()
        results = {}

        for nhamay in ("songhinh", "vinhson"):
            date_range = get_missing_thuc_te_sync_range(nhamay, end_date)
            if not date_range:
                results[nhamay] = {"skipped": True, "reason": "up_to_date"}
                continue

            start_date, range_end_date = date_range
            result = service.sync_thuc_te_range(
                nhamay=nhamay,
                start_date=start_date,
                end_date=range_end_date,
                user=user,
                can_modify=can_auto_sync_modify,
            )
            results[nhamay] = {
                "skipped": False,
                "start_date": start_date.isoformat(),
                "end_date": range_end_date.isoformat(),
                "saved_count": result.saved_count,
                "updated_count": result.updated_count,
                "parsed_count": result.parsed_count,
                "skipped_count": result.skipped_count,
                "source_range": result.source_range,
                "warnings": result.warnings,
            }

        logger.info("Celery Task: sync_missing_thuy_van_thuc_te_daily_task completed: %s", results)
        return results
    except Exception:
        logger.exception("Celery Task: sync_missing_thuy_van_thuc_te_daily_task failed.")
        raise
    finally:
        close_old_connections()
