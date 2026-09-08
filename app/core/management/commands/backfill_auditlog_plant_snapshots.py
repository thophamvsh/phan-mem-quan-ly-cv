from auditlog.models import LogEntry
from django.core.management.base import BaseCommand
from django.db import transaction

from core.audit_plant_resolver import resolve_plant_and_code


class Command(BaseCommand):
    help = 'Điền snapshot plant_id cho các bản ghi LogEntry cũ chưa có thông tin nhà máy.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Thực hiện ghi thay đổi vào cơ sở dữ liệu (mặc định dry-run chỉ kiểm kê)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=500,
            help='Số lượng bản ghi xử lý trong mỗi đợt (mặc định 500)',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        batch_size = options['batch_size']

        self.stdout.write(f"Bắt đầu rà soát LogEntry (apply={apply_changes})...")

        total_entries = LogEntry.objects.count()
        self.stdout.write(f"Tổng số LogEntry trong DB: {total_entries}")

        updated_count = 0
        unresolved_count = 0
        already_has_plant = 0

        # Lọc các LogEntry chưa có plant_id trong additional_data
        # Note: Do additional_data là JSONField, ta duyệt theo batch
        entries = LogEntry.objects.select_related('content_type').order_by('id')

        batch_updates = []

        for entry in entries.iterator(chunk_size=batch_size):
            data = entry.additional_data or {}
            if isinstance(data, dict) and 'plant_id' in data and data['plant_id'] is not None:
                already_has_plant += 1
                continue

            # Thử resolve từ đối tượng gốc
            plant_id = None
            plant_code = None

            try:
                model_class = entry.content_type.model_class() if entry.content_type else None
                if model_class:
                    instance = model_class.objects.filter(pk=entry.object_pk).first()
                    if instance:
                        plant_id, plant_code = resolve_plant_and_code(instance)
            except Exception:
                pass

            if plant_id is not None:
                new_data = dict(data) if isinstance(data, dict) else {}
                new_data['plant_id'] = plant_id
                new_data['plant_code'] = plant_code
                entry.additional_data = new_data
                batch_updates.append(entry)
                updated_count += 1
            else:
                unresolved_count += 1

            if len(batch_updates) >= batch_size:
                if apply_changes:
                    with transaction.atomic():
                        LogEntry.objects.bulk_update(batch_updates, ['additional_data'])
                batch_updates = []
                self.stdout.write(f"Đã xử lý {updated_count + unresolved_count + already_has_plant}/{total_entries}...")

        # Flush batch cuối cùng
        if batch_updates and apply_changes:
            with transaction.atomic():
                LogEntry.objects.bulk_update(batch_updates, ['additional_data'])

        self.stdout.write(self.style.SUCCESS(
            f"Hoàn thành rà soát LogEntry:\n"
            f"- Đã có sẵn snapshot: {already_has_plant}\n"
            f"- Tìm và bổ sung snapshot thành công: {updated_count}\n"
            f"- Không xác định được (đối tượng đã xóa hoặc unscoped): {unresolved_count}\n"
            f"- Chế độ áp dụng: {'ĐÃ LƯU VÀO DB' if apply_changes else 'DRY-RUN (chưa ghi DB, dùng --apply để lưu)'}"
        ))
