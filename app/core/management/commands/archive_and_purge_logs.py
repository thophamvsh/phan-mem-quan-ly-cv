from datetime import timedelta

from auditlog.models import LogEntry
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import DataSyncAudit, UserActivityLog, UserManagementAudit
from core.tasks import archive_and_purge_model_logs


class Command(BaseCommand):
    help = (
        "Kiểm kê, nén lưu trữ file .jsonl.gz (Archive-Before-Purge) "
        "và dọn dẹp các bản ghi nhật ký kiểm toán quá hạn retention policy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Chỉ kiểm kê số lượng bản ghi quá hạn, không tạo file archive và không xóa trong database.',
        )
        parser.add_argument(
            '--target',
            type=str,
            choices=['all', 'activity', 'data', 'sync', 'user'],
            default='all',
            help='Chỉ định phân hệ log cần xử lý: all, activity, data, sync hoặc user (mặc định: all)',
        )
        parser.add_argument(
            '--retention-activity',
            type=int,
            default=None,
            help='Ghi đè số ngày lưu trữ cho Nhật ký truy cập (UserActivityLog, mặc định 90 ngày)',
        )
        parser.add_argument(
            '--retention-data',
            type=int,
            default=None,
            help='Ghi đè số ngày lưu trữ cho Vết thay đổi dữ liệu (LogEntry, mặc định 180 ngày)',
        )
        parser.add_argument(
            '--retention-user',
            type=int,
            default=None,
            help='Ghi đè số ngày lưu trữ cho Quản trị tài khoản (UserManagementAudit, mặc định 730 ngày)',
        )
        parser.add_argument(
            '--retention-sync',
            type=int,
            default=None,
            help='Ghi đè số ngày lưu trữ cho Phiên đồng bộ dữ liệu (mặc định 90 ngày)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Kích thước lô xử lý mỗi đợt nén xuất dữ liệu (mặc định 1000)',
        )
        parser.add_argument(
            '--max-records',
            type=int,
            default=None,
            help='Số bản ghi tối đa xử lý cho mỗi loại log trong một lần chạy.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target = options['target']
        batch_size = options['batch_size']
        max_records = options['max_records']
        if max_records is None:
            max_records = getattr(settings, 'AUDIT_PURGE_MAX_RECORDS_PER_RUN', 10000)
        if batch_size < 1 or batch_size > 10000:
            raise CommandError('--batch-size phải nằm trong khoảng 1 đến 10000.')
        if max_records < 1 or max_records > 1000000:
            raise CommandError('--max-records phải nằm trong khoảng 1 đến 1000000.')
        for option_name in (
            'retention_activity', 'retention_data', 'retention_sync', 'retention_user',
        ):
            value = options[option_name]
            if value is not None and (value < 1 or value > 36500):
                flag = option_name.replace('_', '-')
                raise CommandError(f'--{flag} phải nằm trong khoảng 1 đến 36500 ngày.')

        mode_str = "DRY-RUN (CHỈ KIỂM KÊ, KHÔNG THAY ĐỔI DỮ LIỆU)" if dry_run else "THỰC THI LƯU TRỮ VÀ DỌN DẸP CHÍNH THỨC"

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.WARNING(f"TIẾN TRÌNH LƯU TRỮ VÀ DỌN DẸP LOG KIỂM TOÁN (ARCHIVE-BEFORE-PURGE)"))
        self.stdout.write(f"Chế độ: {mode_str}")
        self.stdout.write(f"Mục tiêu: {target}")
        self.stdout.write("=" * 80)

        targets_to_run = []
        if target in ('all', 'activity'):
            targets_to_run.append('activity')
        if target in ('all', 'data'):
            targets_to_run.append('data')
        if target in ('all', 'sync'):
            targets_to_run.append('sync')
        if target in ('all', 'user'):
            targets_to_run.append('user')

        total_archived = 0
        total_deleted = 0

        for tgt in targets_to_run:
            if tgt == 'activity':
                retention = options['retention_activity'] or getattr(
                    settings, 'ACTIVITY_LOG_RETENTION_DAYS', 90
                )
                cutoff = timezone.now() - timedelta(days=retention)
                self.stdout.write(f"\n[1] Xử lý Nhật ký truy cập (UserActivityLog):")
                self.stdout.write(f"    - Thời hạn retention: {retention} ngày (mốc cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S')})")

                res = archive_and_purge_model_logs(
                    model_class=UserActivityLog,
                    date_field='timestamp',
                    cutoff_date=cutoff,
                    archive_prefix='user_activity_logs',
                    batch_size=batch_size,
                    max_records=max_records,
                    dry_run=dry_run
                )
                self._report_result(res, dry_run)
                total_archived += res['archived']
                total_deleted += res['deleted']

            elif tgt == 'data':
                retention = options['retention_data'] or getattr(
                    settings, 'DATA_AUDIT_RETENTION_DAYS', 180
                )
                cutoff = timezone.now() - timedelta(days=retention)
                self.stdout.write(f"\n[2] Xử lý Vết thay đổi dữ liệu (django-auditlog LogEntry):")
                self.stdout.write(f"    - Thời hạn retention: {retention} ngày (mốc cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S')})")

                res = archive_and_purge_model_logs(
                    model_class=LogEntry,
                    date_field='timestamp',
                    cutoff_date=cutoff,
                    archive_prefix='data_audit_logs',
                    batch_size=batch_size,
                    max_records=max_records,
                    dry_run=dry_run
                )
                self._report_result(res, dry_run)
                total_archived += res['archived']
                total_deleted += res['deleted']

            elif tgt == 'sync':
                retention = options['retention_sync'] or getattr(
                    settings, 'DATA_SYNC_AUDIT_RETENTION_DAYS', 90
                )
                cutoff = timezone.now() - timedelta(days=retention)
                self.stdout.write("\n[3] Xử lý Phiên đồng bộ dữ liệu (DataSyncAudit):")
                self.stdout.write(f"    - Thời hạn retention: {retention} ngày (mốc cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S')})")

                res = archive_and_purge_model_logs(
                    model_class=DataSyncAudit,
                    date_field='started_at',
                    cutoff_date=cutoff,
                    archive_prefix='data_sync_audit_logs',
                    batch_size=batch_size,
                    max_records=max_records,
                    dry_run=dry_run
                )
                self._report_result(res, dry_run)
                total_archived += res['archived']
                total_deleted += res['deleted']

            elif tgt == 'user':
                retention = options['retention_user'] or getattr(
                    settings, 'USER_MANAGEMENT_AUDIT_RETENTION_DAYS', 730
                )
                cutoff = timezone.now() - timedelta(days=retention)
                self.stdout.write(f"\n[4] Xử lý Nhật ký quản trị tài khoản (UserManagementAudit):")
                self.stdout.write(f"    - Thời hạn retention: {retention} ngày (mốc cutoff: {cutoff.strftime('%Y-%m-%d %H:%M:%S')})")

                res = archive_and_purge_model_logs(
                    model_class=UserManagementAudit,
                    date_field='created_at',
                    cutoff_date=cutoff,
                    archive_prefix='user_management_audit_logs',
                    batch_size=batch_size,
                    max_records=max_records,
                    dry_run=dry_run
                )
                self._report_result(res, dry_run)
                total_archived += res['archived']
                total_deleted += res['deleted']

        self.stdout.write("\n" + "=" * 80)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[HOÀN TẤT KIỂM KÊ] Tổng cộng {total_archived} bản ghi quá hạn sẵn sàng để lưu trữ."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"[HOÀN TẤT THÀNH CÔNG] Đã nén archive an toàn {total_archived} bản ghi "
                    f"và giải phóng {total_deleted} bản ghi trong database."
                )
            )
        self.stdout.write("=" * 80)

    def _report_result(self, res, dry_run):
        if dry_run:
            self.stdout.write(f"    -> Tìm thấy {res['archived']} bản ghi cũ quá hạn.")
        else:
            if res['archived'] == 0:
                self.stdout.write(f"    -> Không có bản ghi nào quá hạn cần xử lý.")
            else:
                self.stdout.write(self.style.SUCCESS(f"    -> Đã nén thành công {res['archived']} bản ghi."))
                self.stdout.write(f"       + File archive: {res['archive_file']}")
                self.stdout.write(f"       + SHA-256: {res['sha256']}")
                self.stdout.write(f"       + Đã xóa trong DB: {res['deleted']} bản ghi.")
                if res.get('remaining'):
                    self.stdout.write(
                        f"       + Còn {res['remaining']} bản ghi quá hạn, sẽ xử lý ở lần chạy tiếp theo."
                    )
