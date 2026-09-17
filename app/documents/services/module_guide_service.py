import hashlib
import logging
import os

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import connection, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

from documents.models import ModuleGuide


logger = logging.getLogger(__name__)


def _queue_rag_sync(guide_id, retired_guide_ids=()):
    try:
        from documents.tasks import (
            retire_module_guide_from_rag,
            sync_module_guide_to_rag,
        )

        for retired_id in retired_guide_ids:
            retire_module_guide_from_rag.delay(retired_id)
        sync_module_guide_to_rag.delay(guide_id)
    except Exception:
        logger.exception("Could not enqueue RAG synchronization for module guide %s.", guide_id)


def _queue_rag_retirement(guide_id):
    try:
        from documents.tasks import retire_module_guide_from_rag

        retire_module_guide_from_rag.delay(guide_id)
    except Exception:
        logger.exception("Could not enqueue RAG retirement for module guide %s.", guide_id)


class ModuleGuideConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Dữ liệu tài liệu vừa thay đổi. Vui lòng tải lại danh sách."
    default_code = "module_guide_conflict"


def _publish_slot_lock_key(guide):
    slot = "|".join(
        (
            guide.module_code,
            str(guide.nha_may_id or 0),
            "1" if guide.is_primary else "0",
            guide.document_kind or "",
            str(guide.order),
        )
    )
    digest = hashlib.sha256(slot.encode("utf-8")).digest()[:8]
    return int.from_bytes(digest, byteorder="big", signed=True)


def _acquire_publish_slot_lock(guide):
    if connection.vendor != "postgresql":
        raise RuntimeError("Phát hành tài liệu yêu cầu PostgreSQL advisory lock.")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_try_advisory_xact_lock(%s)",
            [_publish_slot_lock_key(guide)],
        )
        acquired = cursor.fetchone()[0]
    if not acquired:
        raise ModuleGuideConflict(
            "Một người dùng khác đang phát hành tài liệu cùng vị trí. Vui lòng thử lại."
        )


@transaction.atomic
def publish_module_guide(guide_id, approver_user):
    guide = ModuleGuide.objects.select_for_update().get(pk=guide_id)
    if guide.status == ModuleGuide.STATUS_PUBLISHED:
        return guide
    if guide.status != ModuleGuide.STATUS_DRAFT:
        raise ValidationError("Chỉ có thể phát hành tài liệu dự thảo.")

    _acquire_publish_slot_lock(guide)
    if guide.effective_to and guide.effective_to < timezone.localdate():
        raise ValidationError("Không thể phát hành tài liệu đã hết hiệu lực.")

    current = ModuleGuide.objects.select_for_update().filter(
        module_code=guide.module_code,
        status=ModuleGuide.STATUS_PUBLISHED,
        is_primary=guide.is_primary,
    )
    current = (
        current.filter(nha_may=guide.nha_may)
        if guide.nha_may_id
        else current.filter(nha_may__isnull=True)
    )
    if not guide.is_primary:
        current = current.filter(document_kind=guide.document_kind, order=guide.order)
    retired_guide_ids = list(current.values_list("id", flat=True))
    current.update(
        status=ModuleGuide.STATUS_RETIRED,
        retired_by=approver_user,
        retired_at=timezone.now(),
        retire_reason="Được thay thế bởi phiên bản mới.",
    )

    guide.status = ModuleGuide.STATUS_PUBLISHED
    guide.approved_by = approver_user
    guide.published_at = timezone.now()
    guide.retired_by = None
    guide.retired_at = None
    guide.retire_reason = ""
    guide.save()
    transaction.on_commit(
        lambda: _queue_rag_sync(guide.id, retired_guide_ids)
    )
    return guide


@transaction.atomic
def retire_module_guide(guide_id, retired_by_user, reason):
    guide = ModuleGuide.objects.select_for_update().get(pk=guide_id)
    if guide.status != ModuleGuide.STATUS_PUBLISHED:
        raise ValidationError("Chỉ có thể thu hồi tài liệu đang áp dụng.")
    guide.status = ModuleGuide.STATUS_RETIRED
    guide.retired_by = retired_by_user
    guide.retired_at = timezone.now()
    guide.retire_reason = reason.strip()
    guide.save()
    transaction.on_commit(lambda: _queue_rag_retirement(guide.id))
    return guide


@transaction.atomic
def create_next_version(guide_id, version_label, creator_user):
    source = ModuleGuide.objects.select_for_update().get(pk=guide_id)
    version_label = version_label.strip()
    if not version_label:
        raise ValidationError({"version_label": "Vui lòng nhập ký hiệu phiên bản."})

    duplicate = ModuleGuide.objects.filter(
        module_code=source.module_code,
        nha_may=source.nha_may,
        is_primary=source.is_primary,
        document_kind=source.document_kind,
        order=source.order,
        version_label=version_label,
    ).exists()
    if duplicate:
        raise ValidationError({"version_label": "Ký hiệu phiên bản đã tồn tại."})

    source.file.open("rb")
    try:
        file_content = source.file.read()
    finally:
        source.file.close()

    copy = ModuleGuide(
        module_code=source.module_code,
        nha_may=source.nha_may,
        title=source.title,
        document_kind=source.document_kind,
        is_primary=source.is_primary,
        order=source.order,
        version_label=version_label,
        effective_from=None,
        effective_to=None,
        quick_guide=source.quick_guide,
        created_by=creator_user,
    )
    filename = os.path.basename(source.original_filename or source.file.name)
    copy.file.save(filename, ContentFile(file_content), save=False)
    try:
        copy.save()
    except Exception:
        if copy.file:
            copy.file.storage.delete(copy.file.name)
        raise
    return copy
