from celery import shared_task
import logging
from django.db import close_old_connections

logger = logging.getLogger(__name__)


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
