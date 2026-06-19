from django.test import TestCase, RequestFactory, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from rest_framework.test import APIClient
from core.models import UserActivityLog
from auditlog.models import LogEntry
from quanlyvanhanh.models import ThietBi
from nhatkyvanhanh.models import SoBCHCSongHinh
import datetime

class UserLoggingTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(
            email='testlogger@example.com',
            username='testlogger',
            password='Password123!'
        )
        self.factory = RequestFactory()
        self.client = APIClient()

    def test_login_signal_creates_activity_log(self):
        request = self.factory.post('/api/auth/login/', HTTP_USER_AGENT='TestAgent')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        
        user_logged_in.send(sender=self.User, request=request, user=self.user)
        
        logs = UserActivityLog.objects.filter(user=self.user, action_type='LOGIN')
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.ip_address, '1.2.3.4')
        self.assertEqual(log.user_agent, 'TestAgent')
        self.assertEqual(log.description, 'Người dùng đăng nhập thành công')

    def test_logout_signal_creates_activity_log(self):
        request = self.factory.post('/api/auth/logout/', HTTP_USER_AGENT='TestAgent')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        
        user_logged_out.send(sender=self.User, request=request, user=self.user)
        
        logs = UserActivityLog.objects.filter(user=self.user, action_type='LOGOUT')
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.ip_address, '1.2.3.4')
        self.assertEqual(log.description, 'Người dùng đăng xuất khỏi hệ thống')

    def test_login_failed_signal_creates_activity_log(self):
        request = self.factory.post('/api/auth/login/', HTTP_USER_AGENT='TestAgent')
        request.META['REMOTE_ADDR'] = '1.2.3.4'
        
        user_login_failed.send(
            sender=self.User,
            credentials={'username': 'testlogger@example.com'},
            request=request
        )
        
        logs = UserActivityLog.objects.filter(action_type='LOGIN_FAILED')
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertIsNone(log.user)
        self.assertEqual(log.ip_address, '1.2.3.4')
        self.assertIn('testlogger@example.com', log.description)

    def test_api_login_and_logout_triggers_logging(self):
        # 1. Test API Login
        response = self.client.post('/api/auth/login/', {
            'username': 'testlogger@example.com',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 200)
        
        # Verify login log was created
        login_logs = UserActivityLog.objects.filter(user=self.user, action_type='LOGIN')
        self.assertEqual(login_logs.count(), 1)
        
        # Get token for logout
        tokens = response.data['tokens']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + tokens['access'])
        
        # 2. Test API Logout
        response_logout = self.client.post('/api/auth/logout/', {
            'refresh_token': tokens['refresh']
        })
        if response_logout.status_code != 200:
            print("LOGOUT ERROR DATA:", response_logout.data)
        self.assertEqual(response_logout.status_code, 200)
        
        # Verify logout log was created
        logout_logs = UserActivityLog.objects.filter(user=self.user, action_type='LOGOUT')
        self.assertEqual(logout_logs.count(), 1)


class AuditLogTests(TestCase):
    databases = {"default"}

    def test_creating_and_modifying_thiet_bi_creates_audit_log(self):
        tb = ThietBi.objects.create(
            ten='Thiết bị đo nhiệt độ',
            ma='TBDTND',
            ma_day_du='TBDTND'
        )
        
        logs = LogEntry.objects.get_for_object(tb)
        self.assertEqual(logs.count(), 1)
        create_log = logs.first()
        self.assertEqual(create_log.action, LogEntry.Action.CREATE)
        
        tb.ten = 'Thiết bị đo nhiệt độ phòng'
        tb.save()
        
        logs = LogEntry.objects.get_for_object(tb)
        self.assertEqual(logs.count(), 2)
        update_log = logs.order_by('-timestamp').first()
        self.assertEqual(update_log.action, LogEntry.Action.UPDATE)
        
        changes = update_log.changes_dict
        self.assertIn('ten', changes)
        self.assertEqual(changes['ten'], ['Thiết bị đo nhiệt độ', 'Thiết bị đo nhiệt độ phòng'])

    def test_sobchcsonghinh_deletion_creates_audit_log(self):
        bchc = SoBCHCSongHinh.objects.create(
            ngay_dong_bo=datetime.date(2026, 6, 19),
            muc_nuoc_quy_trinh="Quy trình 209m"
        )
        
        logs = LogEntry.objects.get_for_object(bchc)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().action, LogEntry.Action.CREATE)
        
        bchc_id = bchc.id
        bchc.delete()
        
        delete_logs = LogEntry.objects.filter(
            object_pk=str(bchc_id),
            action=LogEntry.Action.DELETE
        )
        self.assertEqual(delete_logs.count(), 1)

    def test_drf_jwt_request_records_correct_audit_actor(self):
        user_model = get_user_model()
        user_hoaxh = user_model.objects.create_superuser(
            email='hoaxh@example.com',
            username='hoaxh',
            password='Password123!'
        )
        
        client = APIClient()
        response = client.post('/api/auth/login/', {
            'username': 'hoaxh@example.com',
            'password': 'Password123!'
        })
        self.assertEqual(response.status_code, 200)
        tokens = response.data['tokens']
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + tokens['access'])

        payload = {
            'ten': 'Thiết bị test audit actor',
            'ma': 'TBTAA',
            'ma_day_du': 'TBTAA'
        }
        response_create = client.post('/api/quanlyvanhanh/thiet-bi/', payload)
        self.assertEqual(response_create.status_code, 201)

        tb = ThietBi.objects.get(ma='TBTAA')

        logs = LogEntry.objects.get_for_object(tb)
        self.assertEqual(logs.count(), 1)
        create_log = logs.first()
        self.assertEqual(create_log.actor, user_hoaxh)

    @override_settings(LOG_RETENTION_DAYS=30)
    def test_clear_old_logs_task_deletes_older_logs_only(self):
        from core.tasks import clear_old_logs_task
        from django.utils import timezone
        from datetime import timedelta
        
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email='cleaner@example.com',
            username='cleaner',
            password='Password123!'
        )

        # 1. Create logs
        # Log 1: new activity log (10 days old)
        new_activity_log = UserActivityLog.objects.create(
            user=user,
            action_type="LOGIN",
            description="New Login"
        )
        UserActivityLog.objects.filter(pk=new_activity_log.pk).update(timestamp=timezone.now() - timedelta(days=10))

        # Log 2: old activity log (40 days old)
        old_activity_log = UserActivityLog.objects.create(
            user=user,
            action_type="LOGIN",
            description="Old Login"
        )
        UserActivityLog.objects.filter(pk=old_activity_log.pk).update(timestamp=timezone.now() - timedelta(days=40))

        # Log 3: new audit log (10 days old)
        tb_new = ThietBi.objects.create(ten="New TB", ma="TBN", ma_day_du="TBN")
        new_audit_log = LogEntry.objects.get_for_object(tb_new).first()
        LogEntry.objects.filter(pk=new_audit_log.pk).update(timestamp=timezone.now() - timedelta(days=10))

        # Log 4: old audit log (40 days old)
        tb_old = ThietBi.objects.create(ten="Old TB", ma="TBO", ma_day_du="TBO")
        old_audit_log = LogEntry.objects.get_for_object(tb_old).first()
        LogEntry.objects.filter(pk=old_audit_log.pk).update(timestamp=timezone.now() - timedelta(days=40))

        # 2. Run Celery task
        result = clear_old_logs_task()

        # 3. Assertions
        # Check returned deleted counts
        self.assertEqual(result['deleted_user_activity_logs'], 1)
        self.assertEqual(result['deleted_audit_logs'], 1)

        # Check logs remaining in DB
        self.assertTrue(UserActivityLog.objects.filter(pk=new_activity_log.pk).exists())
        self.assertFalse(UserActivityLog.objects.filter(pk=old_activity_log.pk).exists())

        self.assertTrue(LogEntry.objects.filter(pk=new_audit_log.pk).exists())
        self.assertFalse(LogEntry.objects.filter(pk=old_audit_log.pk).exists())





