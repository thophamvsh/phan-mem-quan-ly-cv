import gzip
import hashlib
import json
import os
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from io import StringIO

from core.models import UserActivityLog, UserManagementAudit
from core.tasks import (
    archive_and_purge_model_logs,
    clear_old_logs_task,
    serialize_model_instance,
)

User = get_user_model()


class AuditTasksAndRetentionTestCase(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.user = User.objects.create_user(
            username="task_test_user",
            email="task_test@example.com",
            password="Vsh@2026StrongPass!"
        )

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_serialize_model_instance(self):
        """Hàm serialize_model_instance trích xuất đúng các trường của model"""
        log = UserActivityLog.objects.create(
            user=self.user,
            action_type="LOGIN",
            description="Test serialization",
            ip_address="192.168.1.100"
        )
        data = serialize_model_instance(log)
        self.assertEqual(data['action_type'], "LOGIN")
        self.assertEqual(data['ip_address'], "192.168.1.100")
        self.assertEqual(data['__username'], "task_test_user")
        self.assertIn('timestamp', data)

        log.description = 'Bearer header.payload.signature password=raw-secret'
        sanitized = serialize_model_instance(log)
        self.assertNotIn('header.payload.signature', sanitized['description'])
        self.assertNotIn('raw-secret', sanitized['description'])

    def test_archive_and_purge_activity_logs(self):
        """Archive-Before-Purge nén dữ liệu cũ, tính SHA-256 và chỉ xóa bản ghi quá hạn"""
        now = timezone.now()
        cutoff = now - timedelta(days=180)

        # 2 log cũ (> 180 ngày)
        old1 = UserActivityLog.objects.create(
            user=self.user, action_type="LOGIN", description="Old 1"
        )
        UserActivityLog.objects.filter(pk=old1.pk).update(timestamp=cutoff - timedelta(days=10))

        old2 = UserActivityLog.objects.create(
            user=self.user, action_type="LOGOUT", description="Old 2"
        )
        UserActivityLog.objects.filter(pk=old2.pk).update(timestamp=cutoff - timedelta(days=5))

        # 1 log mới (< 180 ngày)
        new1 = UserActivityLog.objects.create(
            user=self.user, action_type="LOGIN", description="New 1"
        )
        UserActivityLog.objects.filter(pk=new1.pk).update(timestamp=now - timedelta(days=10))

        with override_settings(AUDIT_ARCHIVE_DIR=self.temp_dir):
            res = archive_and_purge_model_logs(
                model_class=UserActivityLog,
                date_field='timestamp',
                cutoff_date=cutoff,
                archive_prefix='user_activity_logs',
                batch_size=10
            )

        self.assertEqual(res['archived'], 2)
        self.assertEqual(res['deleted'], 2)
        archive_path = res['archive_file']
        self.assertTrue(os.path.exists(archive_path))
        self.assertTrue(archive_path.endswith('.jsonl.gz'))

        # Kiểm tra file .sha256
        sha_path = archive_path + '.sha256'
        self.assertTrue(os.path.exists(sha_path))
        with open(sha_path, 'r', encoding='utf-8') as sf:
            sha_content = sf.read().strip()
        self.assertTrue(sha_content.startswith(res['sha256']))

        # Kiểm tra tính toàn vẹn SHA-256 thực tế của file nén
        hasher = hashlib.sha256()
        with open(archive_path, 'rb') as f:
            hasher.update(f.read())
        self.assertEqual(hasher.hexdigest(), res['sha256'])

        # Đọc giải nén file .jsonl.gz kiểm tra nội dung
        with gzip.open(archive_path, 'rt', encoding='utf-8') as gz:
            lines = [line.strip() for line in gz if line.strip()]
        self.assertEqual(len(lines), 2)
        record1 = json.loads(lines[0])
        self.assertEqual(record1['description'], "Old 1")

        # Kiểm tra trạng thái DB: bản ghi cũ đã xóa, bản ghi mới được giữ nguyên
        self.assertFalse(UserActivityLog.objects.filter(pk=old1.pk).exists())
        self.assertFalse(UserActivityLog.objects.filter(pk=old2.pk).exists())
        self.assertTrue(UserActivityLog.objects.filter(pk=new1.pk).exists())

    def test_archive_and_purge_log_entry(self):
        """Archive-Before-Purge hoạt động chính xác cho django-auditlog LogEntry"""
        now = timezone.now()
        cutoff = now - timedelta(days=365)
        ct = ContentType.objects.get_for_model(User)

        old_entry = LogEntry.objects.create(
            content_type=ct,
            object_pk="1",
            object_repr="Old Entry",
            action=LogEntry.Action.CREATE,
            changes={"username": ["", "old_user"]}
        )
        LogEntry.objects.filter(pk=old_entry.pk).update(timestamp=cutoff - timedelta(days=20))

        new_entry = LogEntry.objects.create(
            content_type=ct,
            object_pk="2",
            object_repr="New Entry",
            action=LogEntry.Action.UPDATE,
            changes={"username": ["old_user", "new_user"]}
        )
        LogEntry.objects.filter(pk=new_entry.pk).update(timestamp=now - timedelta(days=30))

        with override_settings(AUDIT_ARCHIVE_DIR=self.temp_dir):
            res = archive_and_purge_model_logs(
                model_class=LogEntry,
                date_field='timestamp',
                cutoff_date=cutoff,
                archive_prefix='data_audit_logs'
            )

        self.assertEqual(res['archived'], 1)
        self.assertEqual(res['deleted'], 1)
        self.assertFalse(LogEntry.objects.filter(pk=old_entry.pk).exists())
        self.assertTrue(LogEntry.objects.filter(pk=new_entry.pk).exists())

    def test_archive_and_purge_user_management_audit(self):
        """Archive-Before-Purge hoạt động chính xác cho UserManagementAudit"""
        now = timezone.now()
        cutoff = now - timedelta(days=730)

        old_audit = UserManagementAudit.objects.create(
            actor=self.user,
            target=self.user,
            action="create",
            changes={"is_active": True}
        )
        UserManagementAudit.objects.filter(pk=old_audit.pk).update(created_at=cutoff - timedelta(days=50))

        new_audit = UserManagementAudit.objects.create(
            actor=self.user,
            target=self.user,
            action="status",
            changes={"is_active": False}
        )
        UserManagementAudit.objects.filter(pk=new_audit.pk).update(created_at=now - timedelta(days=10))

        with override_settings(AUDIT_ARCHIVE_DIR=self.temp_dir):
            res = archive_and_purge_model_logs(
                model_class=UserManagementAudit,
                date_field='created_at',
                cutoff_date=cutoff,
                archive_prefix='user_management_audit_logs'
            )

        self.assertEqual(res['archived'], 1)
        self.assertEqual(res['deleted'], 1)
        self.assertFalse(UserManagementAudit.objects.filter(pk=old_audit.pk).exists())
        self.assertTrue(UserManagementAudit.objects.filter(pk=new_audit.pk).exists())

    def test_integrity_check_failure_aborts_db_deletion(self):
        """Nếu quá trình archive/đọc lại kiểm tra gặp lỗi, lệnh xóa DB phải bị hủy bỏ hoàn toàn"""
        now = timezone.now()
        cutoff = now - timedelta(days=180)

        log = UserActivityLog.objects.create(
            user=self.user, action_type="LOGIN", description="Preserve me on failure"
        )
        UserActivityLog.objects.filter(pk=log.pk).update(timestamp=cutoff - timedelta(days=10))

        # Giả lập lỗi khi đọc lại file nén để kiểm tra toàn vẹn (corrupted JSON)
        with patch('core.tasks.json.loads', side_effect=ValueError("Simulated corrupted JSON line")):
            with override_settings(AUDIT_ARCHIVE_DIR=self.temp_dir):
                with self.assertRaises(ValueError):
                    archive_and_purge_model_logs(
                        model_class=UserActivityLog,
                        date_field='timestamp',
                        cutoff_date=cutoff,
                        archive_prefix='user_activity_logs'
                    )

        # Dữ liệu trong DB KHÔNG ĐƯỢC PHÉP BỊ XÓA
        self.assertTrue(UserActivityLog.objects.filter(pk=log.pk).exists())

    def test_clear_old_logs_task_execution(self):
        """Tác vụ Celery clear_old_logs_task thực thi an toàn cho cả 3 phân hệ"""
        now = timezone.now()
        cutoff_act = now - timedelta(days=180)

        old_act = UserActivityLog.objects.create(
            user=self.user, action_type="LOGIN", description="Celery Old Act"
        )
        UserActivityLog.objects.filter(pk=old_act.pk).update(timestamp=cutoff_act - timedelta(days=2))

        with override_settings(
            AUDIT_ARCHIVE_DIR=self.temp_dir,
            AUDIT_ARCHIVE_ENABLED=True,
        ):
            result = clear_old_logs_task()

        self.assertIn('deleted_user_activity_logs', result)
        self.assertIn('deleted_audit_logs', result)
        self.assertIn('deleted_user_management_logs', result)
        self.assertEqual(result['deleted_user_activity_logs'], 1)
        self.assertFalse(UserActivityLog.objects.filter(pk=old_act.pk).exists())

    @override_settings(AUDIT_ARCHIVE_ENABLED=False)
    def test_scheduled_archive_is_fail_safe_when_disabled(self):
        old_log = UserActivityLog.objects.create(
            user=self.user, action_type='LOGIN', description='Must remain'
        )
        UserActivityLog.objects.filter(pk=old_log.pk).update(
            timestamp=timezone.now() - timedelta(days=1000)
        )
        result = clear_old_logs_task()
        self.assertTrue(result['disabled'])
        self.assertTrue(UserActivityLog.objects.filter(pk=old_log.pk).exists())

    def test_management_command_rejects_unsafe_numeric_options(self):
        with self.assertRaises(CommandError):
            call_command('archive_and_purge_logs', '--batch-size', '0')
        with self.assertRaises(CommandError):
            call_command('archive_and_purge_logs', '--retention-data', '-1')

    def test_management_command_dry_run(self):
        """Lệnh management archive_and_purge_logs ở chế độ --dry-run không xóa dữ liệu"""
        now = timezone.now()
        cutoff = now - timedelta(days=180)

        old_log = UserActivityLog.objects.create(
            user=self.user, action_type="LOGIN", description="Dry Run Test Log"
        )
        UserActivityLog.objects.filter(pk=old_log.pk).update(timestamp=cutoff - timedelta(days=10))

        out = StringIO()
        call_command('archive_and_purge_logs', '--dry-run', stdout=out)
        output = out.getvalue()

        self.assertIn('DRY-RUN', output)
        self.assertIn('Tìm thấy 1 bản ghi cũ quá hạn', output)
        # Bản ghi vẫn phải tồn tại trong DB
        self.assertTrue(UserActivityLog.objects.filter(pk=old_log.pk).exists())

    def test_management_command_target_filter(self):
        """Lệnh management hỗ trợ tham số --target chỉ xử lý phân hệ chỉ định"""
        out = StringIO()
        call_command('archive_and_purge_logs', '--dry-run', '--target', 'activity', stdout=out)
        output = out.getvalue()

        self.assertIn('UserActivityLog', output)
        self.assertNotIn('LogEntry', output)
        self.assertNotIn('UserManagementAudit', output)
