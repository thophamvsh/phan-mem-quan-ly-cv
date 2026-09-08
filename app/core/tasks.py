import datetime
import gzip
import hashlib
import json
import logging
import os
import uuid
from datetime import timedelta

from auditlog.models import LogEntry
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import DataSyncAudit, UserActivityLog, UserManagementAudit
from core.audit_serializers import sanitize_audit_payload

logger = logging.getLogger(__name__)


def serialize_model_instance(obj):
    """
    Tuần tự hóa một đối tượng model thành dictionary chuẩn để lưu trữ file jsonl.
    """
    data = {}
    for field in obj._meta.fields:
        val = getattr(obj, field.attname)
        if isinstance(val, (datetime.date, datetime.datetime)):
            data[field.attname] = val.isoformat()
        elif isinstance(val, uuid.UUID):
            data[field.attname] = str(val)
        else:
            data[field.attname] = val
    if hasattr(obj, 'user') and obj.user:
        data['__username'] = getattr(obj.user, 'username', '')
    if hasattr(obj, 'actor') and obj.actor:
        data['__actor_username'] = getattr(obj.actor, 'username', '')
    if hasattr(obj, 'target') and obj.target:
        data['__target_username'] = getattr(obj.target, 'username', '')
    return sanitize_audit_payload(data)


def archive_and_purge_model_logs(
    model_class,
    date_field,
    cutoff_date,
    archive_prefix,
    batch_size=1000,
    max_records=None,
    dry_run=False
):
    """
    Thực hiện quy trình Archive-Before-Purge:
    1. Lọc bản ghi < cutoff_date.
    2. Nén vào file .jsonl.gz.
    3. Kiểm tra tính toàn vẹn: Checksum SHA-256 + Đọc lại giải nén đếm số dòng.
    4. Xóa bản ghi trong database qua transaction.atomic().
    Nếu bước 2 hoặc 3 có bất kỳ lỗi nào, hủy bỏ xóa trong DB và dọn dẹp file tạm.
    """
    filter_kwargs = {f"{date_field}__lt": cutoff_date}
    candidates = model_class.objects.filter(**filter_kwargs)
    total_candidates = candidates.count()
    max_records = max_records or getattr(
        settings, 'AUDIT_PURGE_MAX_RECORDS_PER_RUN', 10000
    )

    if total_candidates == 0:
        logger.info(f"[{archive_prefix}] Không có bản ghi nào cũ hơn {cutoff_date} để lưu trữ/dọn dẹp.")
        return {
            'archived': 0,
            'deleted': 0,
            'archive_file': None,
            'sha256': None,
            'dry_run': dry_run,
        }

    if dry_run:
        logger.info(f"[{archive_prefix} - DRY RUN] Tìm thấy {total_candidates} bản ghi cũ hơn {cutoff_date}.")
        return {
            'archived': total_candidates,
            'deleted': 0,
            'archive_file': None,
            'sha256': None,
            'dry_run': True,
        }

    archive_dir = getattr(
        settings,
        'AUDIT_ARCHIVE_DIR',
        os.path.join(settings.BASE_DIR, 'cold_storage', 'audit_archives')
    )
    os.makedirs(archive_dir, exist_ok=True)

    date_str = cutoff_date.strftime('%Y%m%d')
    now_str = timezone.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"{archive_prefix}_before_{date_str}_{now_str}.jsonl.gz"
    filepath = os.path.join(archive_dir, filename)
    temp_filepath = filepath + '.tmp'

    archived_ids = list(
        candidates.order_by(date_field, 'pk')
        .values_list('pk', flat=True)[:max_records]
    )
    written_count = 0

    try:
        # Bước 1: Ghi và nén file gzip theo batch. Danh sách khóa chính
        # hỗ trợ cả integer và UUID.
        with gzip.open(temp_filepath, 'wt', encoding='utf-8') as gz_out:
            for index in range(0, len(archived_ids), batch_size):
                id_chunk = archived_ids[index:index + batch_size]
                objects_by_id = model_class.objects.in_bulk(id_chunk)
                batch = [objects_by_id[pk] for pk in id_chunk if pk in objects_by_id]
                for obj in batch:
                    record_dict = serialize_model_instance(obj)
                    gz_out.write(json.dumps(record_dict, ensure_ascii=False) + '\n')
                    written_count += 1

        if written_count != len(archived_ids) or written_count == 0:
            raise ValueError(
                f"Số lượng bản ghi xuất ({written_count}) không khớp với danh sách IDs ({len(archived_ids)})"
            )

        # Bước 2: Kiểm tra toàn vẹn file nén (Checksum SHA-256 + đọc lại đếm dòng)
        sha256_hash = hashlib.sha256()
        with open(temp_filepath, 'rb') as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        hex_digest = sha256_hash.hexdigest()

        verified_line_count = 0
        with gzip.open(temp_filepath, 'rt', encoding='utf-8') as gz_in:
            for line in gz_in:
                if line.strip():
                    json.loads(line)
                    verified_line_count += 1

        if verified_line_count != written_count:
            raise ValueError(
                f"Kiểm tra toàn vẹn file nén thất bại: Đã ghi {written_count} dòng "
                f"nhưng chỉ đọc lại được {verified_line_count} dòng."
            )

        # Chốt file nén chính thức và ghi kèm checksum .sha256
        os.replace(temp_filepath, filepath)
        sha_filepath = filepath + '.sha256'
        with open(sha_filepath, 'w', encoding='utf-8') as sf:
            sf.write(f"{hex_digest}  {filename}\n")

        logger.info(
            f"[{archive_prefix}] Đã archive thành công {written_count} bản ghi "
            f"vào file {filename} (SHA-256: {hex_digest})."
        )

    except Exception as e:
        logger.error(f"[{archive_prefix}] Lỗi trong quá trình archive: {str(e)}. HỦY BỎ XÓA DATABASE!")
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except OSError:
                pass
        raise

    # Bước 3: Xóa an toàn theo từng transaction nhỏ để không giữ khóa DB
    # trong suốt toàn bộ quá trình dọn dẹp.
    deleted_count = 0
    try:
        for i in range(0, len(archived_ids), batch_size):
            chunk = archived_ids[i:i + batch_size]
            with transaction.atomic():
                cnt, _ = model_class.objects.filter(pk__in=chunk).delete()
                deleted_count += cnt

        logger.info(f"[{archive_prefix}] Đã xóa thành công {deleted_count} bản ghi trong database.")
    except Exception as e:
        logger.critical(
            f"[{archive_prefix}] Lỗi khi xóa bản ghi khỏi database: {str(e)}. "
            f"File archive đã được lưu tại {filepath}."
        )
        raise

    return {
        'archived': written_count,
        'deleted': deleted_count,
        'archive_file': filepath,
        'sha256': hex_digest,
        'remaining': max(total_candidates - written_count, 0),
        'dry_run': False,
    }


@shared_task
def clear_old_logs_task():
    """
    Celery task định kỳ dọn dẹp và nén lưu trữ (Archive-Before-Purge)
    các loại nhật ký kiểm toán quá hạn retention policy.
    """
    if not getattr(settings, 'AUDIT_ARCHIVE_ENABLED', False):
        logger.warning(
            'Automatic audit archive/purge is disabled. Set '
            'AUDIT_ARCHIVE_ENABLED=true only after configuring durable storage.'
        )
        return {'disabled': True, 'archived': 0, 'deleted': 0}

    # 1. UserActivityLog
    batch_size = getattr(settings, 'AUDIT_PURGE_BATCH_SIZE', 1000)
    max_records = getattr(settings, 'AUDIT_PURGE_MAX_RECORDS_PER_RUN', 10000)

    retention_activity = getattr(settings, 'ACTIVITY_LOG_RETENTION_DAYS', 90)
    cutoff_activity = timezone.now() - timedelta(days=retention_activity)
    res_activity = archive_and_purge_model_logs(
        model_class=UserActivityLog,
        date_field='timestamp',
        cutoff_date=cutoff_activity,
        archive_prefix='user_activity_logs', batch_size=batch_size,
        max_records=max_records,
    )

    # 2. Django-auditlog LogEntry
    retention_data = getattr(settings, 'DATA_AUDIT_RETENTION_DAYS', 180)
    cutoff_data = timezone.now() - timedelta(days=retention_data)
    res_data = archive_and_purge_model_logs(
        model_class=LogEntry,
        date_field='timestamp',
        cutoff_date=cutoff_data,
        archive_prefix='data_audit_logs', batch_size=batch_size,
        max_records=max_records,
    )

    # 3. UserManagementAudit
    retention_user = getattr(settings, 'USER_MANAGEMENT_AUDIT_RETENTION_DAYS', 730)
    cutoff_user = timezone.now() - timedelta(days=retention_user)
    res_user = archive_and_purge_model_logs(
        model_class=UserManagementAudit,
        date_field='created_at',
        cutoff_date=cutoff_user,
        archive_prefix='user_management_audit_logs', batch_size=batch_size,
        max_records=max_records,
    )

    retention_sync = getattr(settings, 'DATA_SYNC_AUDIT_RETENTION_DAYS', 90)
    cutoff_sync = timezone.now() - timedelta(days=retention_sync)
    res_sync = archive_and_purge_model_logs(
        model_class=DataSyncAudit,
        date_field='started_at',
        cutoff_date=cutoff_sync,
        archive_prefix='data_sync_audit_logs', batch_size=batch_size,
        max_records=max_records,
    )

    return {
        'deleted_user_activity_logs': res_activity['deleted'],
        'deleted_audit_logs': res_data['deleted'],
        'deleted_user_management_logs': res_user['deleted'],
        'deleted_data_sync_logs': res_sync['deleted'],
        'details': {
            'user_activity_logs': res_activity,
            'data_audit_logs': res_data,
            'user_management_audit_logs': res_user,
            'data_sync_audit_logs': res_sync,
        }
    }
