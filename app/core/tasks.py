from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from core.models import UserActivityLog
from auditlog.models import LogEntry
import logging

logger = logging.getLogger(__name__)

@shared_task
def clear_old_logs_task():
    retention_days = getattr(settings, 'LOG_RETENTION_DAYS', 180)
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    # 1. Clear user activity logs
    deleted_user_logs, _ = UserActivityLog.objects.filter(timestamp__lt=cutoff_date).delete()
    logger.info(f"Cleared {deleted_user_logs} user activity logs older than {retention_days} days (cutoff: {cutoff_date})")
    
    # 2. Clear auditlog entries
    deleted_audit_logs, _ = LogEntry.objects.filter(timestamp__lt=cutoff_date).delete()
    logger.info(f"Cleared {deleted_audit_logs} django-auditlog entries older than {retention_days} days (cutoff: {cutoff_date})")
    
    return {
        'deleted_user_activity_logs': deleted_user_logs,
        'deleted_audit_logs': deleted_audit_logs
    }
