import html
import logging
import threading
import requests

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import SuKien, ChiDaoSuKien

logger = logging.getLogger(__name__)


def escape_html(text):
    """
    Escapes special HTML characters so that they are safe for Telegram's HTML parse_mode.
    """
    if not text:
        return ""
    return html.escape(str(text))


def get_user_display_name(user):
    """
    Safely retrieves a display name for the user, since the custom User model
    does not have a get_full_name() method.
    """
    if not user:
        return ""
    # Try getting from profile first
    profile = getattr(user, "profile", None)
    if profile:
        if profile.ho_ten:
            return profile.ho_ten
        if profile.ho or profile.ten:
            return f"{profile.ho or ''} {profile.ten or ''}".strip()
    # Fallback to User model fields
    first_name = getattr(user, "first_name", "")
    last_name = getattr(user, "last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    if full_name:
        return full_name
    return getattr(user, "username", "") or getattr(user, "email", "")


def send_telegram_notification(text):
    """
    Sends a message to the configured Telegram chat using Celery tasks.
    """
    from .tasks import send_telegram_notification_task
    send_telegram_notification_task.delay(text)


@receiver(post_save, sender=SuKien)
def notify_new_sukien(sender, instance, created, **kwargs):
    """
    Sends a Telegram notification when a new SuKien (Event) is created.
    """
    if not created:
        return

    def notify_after_commit():
        try:
            thoi_gian = timezone.localtime(instance.thoi_gian_xay_ra).strftime("%d/%m/%Y %H:%M")
        except Exception:
            thoi_gian = instance.thoi_gian_xay_ra.strftime("%d/%m/%Y %H:%M")

        nha_may_str = instance.nha_may.ten_nha_may if instance.nha_may else "Không rõ"
        thiet_bi_str = instance.thiet_bi.ten if instance.thiet_bi else "Không rõ"
        loai_str = instance.get_loai_display()
        nguoi_tao_str = get_user_display_name(instance.nguoi_tao) if instance.nguoi_tao else "Hệ thống"

        text = (
            f"<b>🔔 CÓ SỰ KIỆN MỚI</b>\n\n"
            f"📍 <b>Nhà máy:</b> {escape_html(nha_may_str)}\n"
            f"⚙️ <b>Hệ thống/Thiết bị:</b> {escape_html(instance.ten_he_thong_thiet_bi)} ({escape_html(thiet_bi_str)})\n"
            f"⚠️ <b>Loại sự kiện:</b> {escape_html(loai_str)}\n"
            f"⏰ <b>Thời gian xảy ra:</b> {escape_html(thoi_gian)}\n"
            f"👤 <b>Người báo cáo:</b> {escape_html(nguoi_tao_str)}\n\n"
            f"🆔 <code>{instance.id}</code>"
        )
        send_telegram_notification(text)

    transaction.on_commit(notify_after_commit)


@receiver(post_save, sender=ChiDaoSuKien)
def notify_new_chidao(sender, instance, created, **kwargs):
    """
    Sends a Telegram notification when a new ChiDaoSuKien (Directive) is created.
    """
    if not created:
        return

    def notify_after_commit():
        su_kien = instance.su_kien
        nha_may_str = su_kien.nha_may.ten_nha_may if su_kien.nha_may else "Không rõ"
        
        # Determine the director user
        nguoi_chi_dao_str = "Lãnh đạo"
        if instance.nguoi_chi_dao:
            nguoi_chi_dao_str = get_user_display_name(instance.nguoi_chi_dao)
        
        chuc_danh_str = f" ({instance.chuc_danh_nguoi_chi_dao})" if instance.chuc_danh_nguoi_chi_dao else ""

        text = (
            f"<b>✍️ CÓ CHỈ ĐẠO MỚI CHO SỰ KIỆN</b>\n\n"
            f"📍 <b>Nhà máy:</b> {escape_html(nha_may_str)}\n"
            f"⚙️ <b>Sự kiện:</b> {escape_html(su_kien.ten_he_thong_thiet_bi)}\n"
            f"👤 <b>Người chỉ đạo:</b> {escape_html(nguoi_chi_dao_str)}{escape_html(chuc_danh_str)}\n\n"
            f"💬 <b>Nội dung chỉ đạo:</b>\n<i>{escape_html(instance.noi_dung)}</i>\n\n"
            f"🆔 Sự kiện: <code>{su_kien.id}</code>"
        )
        send_telegram_notification(text)

    transaction.on_commit(notify_after_commit)
