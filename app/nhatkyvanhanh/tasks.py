from celery import shared_task
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_telegram_notification_task(self, text):
    """
    Celery task to send a Telegram notification.
    Retries automatically on network or API failures.
    """
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)

    if not token or not chat_id:
        logger.warning("Telegram Bot Token or Chat ID is not configured in Django settings.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            logger.error(f"Telegram API error (status {response.status_code}): {response.text}")
            raise Exception(f"Telegram API error status {response.status_code}")
        else:
            logger.info("Telegram notification sent successfully via Celery.")
    except Exception as e:
        logger.exception("Failed to send Telegram notification due to connection error.")
        raise
