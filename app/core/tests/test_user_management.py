from unittest.mock import patch
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from core.account_auth import AccountRefreshToken
from core.models import User, UserProfile, UserRole, UserRoleDelegation, UserManagementAudit
from core.user_management_policy import MANAGEMENT_PERMISSIONS
from tochuc.models import NhaMay, DonViToChuc, BoPhan, NhanSu

BASE = '/api/user-management/'
PASSWORD = 'Correct-Horse-2026!Battery'


class ManagedUsersTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.sh = NhaMay.objects.create(ma_nha_may='SH', ten_nha_may='Sông Hinh')
        self.vs = NhaMay.objects.create(ma_nha_may='VS', ten_nha_may='Vĩnh Sơn')
        self.role = UserRole.objects.create(name='Vận hành', permissions={'can_view_materials': True})
        self.weak = UserRole.objects.create(name='Chỉ xem', permissions={})
        self.actor = self.make_user('manager', self.sh)
        profile = self.actor.profile
        for name in MANAGEMENT_PERMISSIONS:
            setattr(profile, name, True)
        profile.save()
        for role in (self.role, self.weak):
            UserRoleDelegation.objects.create(delegate=self.actor, nha_may=self.sh, assignable_role=role)
        self.target = self.make_user('target', self.sh, self.role)
        self.other = self.make_user('other', self.vs, self.role)
        self.client.force_authenticate(self.actor)

    def make_user(self, name, plant, role=None):
        user = User.objects.create_user(email=f'{name}@example.com', username=name, password=PASSWORD)
        UserProfile.objects.update_or_create(user=user, defaults={'nha_may': plant, 'role': role})
        return user

    def payload(self, **kwargs):
        return dict(username='newstaff', email='newstaff@example.com', first_name='Nguyễn',
                    last_name='An', password=PASSWORD, password_confirm=PASSWORD,
                    role_id=self.role.pk, **kwargs)

    def post(self, data=None):
        return self.client.post(BASE + 'users/', data or self.payload(), format='json')

    def test_create_hashed_profile_and_audit(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.data)
        user = User.objects.get(pk=response.data['id'])
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(user.profile.nha_may_id, self.sh.pk)
        self.assertTrue(user.profile.can_view_materials)
        self.assertEqual(UserManagementAudit.objects.count(), 1)
        self.assertNotIn(PASSWORD, str(response.data) + str(UserManagementAudit.objects.first().changes))

    def test_each_required_create_permission(self):
        for name in ('can_view_users', 'can_create_users', 'can_assign_user_roles'):
            with self.subTest(name=name):
                setattr(self.actor.profile, name, False)
                self.actor.profile.save()
                self.assertEqual(self.post().status_code, 403)
                setattr(self.actor.profile, name, True)
                self.actor.profile.save()

    def test_reject_privileged_and_unknown_fields(self):
        for key in ('is_staff', 'is_superuser', 'is_all_factories', 'individual_permissions',
                    'can_view_users', 'groups', 'user_permissions', 'created_by', 'unexpected'):
            with self.subTest(key=key):
                self.assertEqual(self.post(self.payload(**{key: True})).status_code, 400)
        self.assertFalse(User.objects.filter(username='newstaff').exists())

    def test_self_profile_all_aliases_reject_privileges(self):
        for url in ('/api/profile/', '/api/v1/auth/profile/', '/api/auth/profile/update/',
                    '/api/khovattu/auth/profile/update/'):
            with self.subTest(url=url):
                response = self.client.patch(url, {'can_view_users': True, 'nha_may': self.vs.pk}, format='json')
                self.assertEqual(response.status_code, 400, response.data)

    def test_self_profile_cannot_change_mobile_access_flag(self):
        response = self.client.patch('/api/profile/', {'is_mobile_user': True}, format='json')
        self.assertEqual(response.status_code, 400, response.data)

    def test_self_profile_can_edit_name(self):
        response = self.client.patch('/api/profile/', {'ho_ten': 'Nguyễn Văn Bình'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_scoped_list_and_objects(self):
        response = self.client.get(BASE + 'users/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.other.pk, [u['id'] for u in response.data['results']])
        self.assertEqual(self.client.get(BASE + f'users/{self.other.pk}/').status_code, 404)
        self.assertEqual(self.post(self.payload(nha_may=self.vs.pk)).status_code, 403)
        self.assertEqual(self.client.get(BASE + f'users/?nha_may={self.vs.pk}').status_code, 403)

    def test_empty_delegation_and_unsafe_role(self):
        UserRoleDelegation.objects.filter(delegate=self.actor).update(is_active=False)
        self.assertEqual(self.post().status_code, 403)
        UserRoleDelegation.objects.filter(delegate=self.actor).update(is_active=True)
        self.role.permissions = {'can_create_users': True}
        self.role.save()
        self.assertEqual(self.post().status_code, 403)

    def test_all_factories_does_not_grant_delegation(self):
        self.actor.profile.is_all_factories = True
        self.actor.profile.save()
        self.assertEqual(self.post(self.payload(nha_may=self.vs.pk)).status_code, 403)

    def test_protected_targets(self):
        url = BASE + f'users/{self.target.pk}/status/'
        for attr in ('is_staff', 'is_superuser'):
            with self.subTest(attr=attr):
                setattr(self.target, attr, True)
                self.target.save()
                self.assertEqual(self.client.post(url, {'is_active': False}).status_code, 403)
                setattr(self.target, attr, False)
                self.target.save()
        self.target.groups.add(Group.objects.create(name='Protected'))
        self.assertEqual(self.client.post(url, {'is_active': False}).status_code, 403)
        self.assertEqual(self.client.post(BASE + f'users/{self.actor.pk}/status/', {'is_active': False}).status_code, 403)

    def test_role_downgrade_clears_stale_flags(self):
        response = self.client.post(BASE + f'users/{self.target.pk}/role/', {'role_id': self.weak.pk})
        self.assertEqual(response.status_code, 200, response.data)
        self.target.profile.refresh_from_db()
        self.assertFalse(self.target.profile.can_view_materials)

    def test_role_definition_change_preserves_individual_not_stale(self):
        profile = self.target.profile
        profile.individual_permissions = {'can_edit_materials': True}
        profile.save()
        self.role.permissions = {}
        self.role.save()
        profile.refresh_from_db()
        self.assertFalse(profile.can_view_materials)
        self.assertTrue(profile.can_edit_materials)
        self.actor.profile.refresh_from_db()
        self.assertTrue(self.actor.profile.can_view_users)  # no-role legacy retained

    def test_rollback_profile_and_audit_failures(self):
        for method in ('core.user_management_views.UserProfile.objects.update_or_create',
                       'core.user_management_views.UserManagementAudit.objects.create'):
            with self.subTest(method=method), patch(method, side_effect=IntegrityError('test')):
                self.assertEqual(self.post().status_code, 400)
                self.assertFalse(User.objects.filter(username='newstaff').exists())

    def test_duplicates_and_bad_password(self):
        payload = self.payload()
        payload['email'] = self.target.email.upper()
        self.assertEqual(self.post(payload).status_code, 400)
        payload = self.payload()
        payload['password'] = payload['password_confirm'] = '123'
        self.assertEqual(self.post(payload).status_code, 400)

    def test_lock_unlock_rejects_old_access_refresh_and_session(self):
        token = AccountRefreshToken.for_user(self.target)
        legacy = RefreshToken.for_user(self.target)
        old_session_hash = self.target.get_session_auth_hash()
        for active in (False, True):
            response = self.client.post(BASE + f'users/{self.target.pk}/status/', {'is_active': active})
            self.assertEqual(response.status_code, 200, response.data)
            client = APIClient()
            for access in (token.access_token, legacy.access_token):
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
                self.assertEqual(client.get('/api/profile/').status_code, 401)
            client.credentials()
            self.assertEqual(client.post('/api/auth/token/refresh/', {'refresh': str(token)}).status_code, 401)
        self.target.refresh_from_db()
        self.assertNotEqual(old_session_hash, self.target.get_session_auth_hash())
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccountRefreshToken.for_user(self.target).access_token}')
        self.assertEqual(client.get('/api/profile/').status_code, 200)

    def test_personnel_link_and_out_of_scope(self):
        unit = DonViToChuc.objects.create(ma_don_vi='SH-NM', ten_don_vi='SH', nha_may=self.sh)
        department = BoPhan.objects.create(don_vi=unit, ma_bo_phan='VH', ten_bo_phan='Vận hành')
        staff = NhanSu.objects.create(don_vi=unit, bo_phan=department, ho_ten='Nguyễn An')
        response = self.post(self.payload(nhan_su_id=staff.pk))
        self.assertEqual(response.status_code, 201, response.data)
        staff.refresh_from_db()
        self.assertEqual(staff.user_id, response.data['id'])
        self.assertEqual(self.client.get(BASE + f'personnel-options/?nha_may={self.sh.pk}').data, [])

    def test_unauthenticated_and_no_hard_delete(self):
        self.assertEqual(self.client.delete(BASE + f'users/{self.target.pk}/').status_code, 405)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(BASE + 'users/').status_code, 401)

    def test_list_query_count_bounded(self):
        for index in range(8):
            self.make_user(f'extra{index}', self.sh, self.role)
        with self.assertNumQueries(5):
            response = self.client.get(BASE + 'users/')
        self.assertEqual(response.status_code, 200)

    def test_public_registration_is_disabled(self):
        client = APIClient()
        self.assertEqual(client.post('/api/auth/register/', self.payload(), format='json').status_code, 403)
        self.assertFalse(User.objects.filter(username='newstaff').exists())

    def test_payload_wrong_shape_rejected(self):
        self.assertEqual(self.client.post(BASE + 'users/', [{'is_staff': True}], format='json').status_code, 400)

    def test_missing_profile_and_factory_fail_closed(self):
        self.actor.profile.nha_may = None
        self.actor.profile.save()
        self.assertEqual(self.post().status_code, 403)
        self.assertEqual(self.client.get(BASE + 'users/').data['count'], 0)

    def test_individual_and_legacy_targets_are_protected(self):
        for changes in ({'individual_permissions': {'can_edit_materials': True}}, {'role': None}):
            with self.subTest(changes=changes):
                for field, value in changes.items():
                    setattr(self.target.profile, field, value)
                self.target.profile.save()
                self.assertEqual(self.client.patch(BASE + f'users/{self.target.pk}/', {'first_name': 'Changed'}).status_code, 403)

    def test_failed_staff_link_keeps_previous_link(self):
        unit = DonViToChuc.objects.create(ma_don_vi='SH-NM', ten_don_vi='SH', nha_may=self.sh)
        department = BoPhan.objects.create(don_vi=unit, ma_bo_phan='VH', ten_bo_phan='Vận hành')
        staff = NhanSu.objects.create(don_vi=unit, bo_phan=department, ho_ten='Nhân sự', user=self.target)
        occupied = NhanSu.objects.create(don_vi=unit, bo_phan=department, ho_ten='Đã liên kết', user=self.actor)
        response = self.client.patch(BASE + f'users/{self.target.pk}/', {'nhan_su_id': occupied.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        staff.refresh_from_db()
        self.assertEqual(staff.user_id, self.target.pk)

    def test_secure_cookie_refresh_after_unlock_is_rejected(self):
        from django.conf import settings
        client = APIClient()
        token = AccountRefreshToken.for_user(self.target)
        for active in (False, True):
            self.client.post(BASE + f'users/{self.target.pk}/status/', {'is_active': active})
        client.cookies[settings.AUTH_COOKIE_NAME] = str(token)
        self.assertEqual(client.post('/api/v1/auth/refresh-secure/').status_code, 401)

    def test_mutation_throttle_and_noop_audit(self):
        from core.user_management_views import ManagementWriteThrottle
        with patch.object(ManagementWriteThrottle, 'rate', '2/min'):
            for _ in range(2):
                self.assertEqual(self.client.post(BASE + f'users/{self.target.pk}/role/', {'role_id': self.role.pk}).status_code, 200)
            self.assertEqual(self.client.post(BASE + f'users/{self.target.pk}/role/', {'role_id': self.role.pk}).status_code, 429)
        self.assertEqual(UserManagementAudit.objects.count(), 0)

    def test_delegation_admin_superuser_only(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from core.admin import UserRoleDelegationAdmin
        model_admin = UserRoleDelegationAdmin(UserRoleDelegation, AdminSite())
        request = RequestFactory().get('/admin/')
        request.user = self.actor
        self.actor.is_staff = True
        self.assertFalse(model_admin.has_change_permission(request))
        self.actor.is_superuser = True
        self.assertTrue(model_admin.has_change_permission(request))

    def test_created_user_can_login_and_receive_management_flags(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        client = APIClient()
        login = client.post('/api/v1/auth/login-secure/',
                            {'username': 'newstaff', 'password': PASSWORD}, format='json')
        self.assertEqual(login.status_code, 200, login.data)
        self.assertTrue(login.data['user']['can_view_materials'])
        self.assertFalse(login.data['user']['can_create_users'])

    def test_role_downgrade_rejects_next_request_with_same_token(self):
        self.role.permissions = {'can_view_shift_handover_logs': True}
        self.role.save()
        token = AccountRefreshToken.for_user(self.target)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.assertEqual(client.get('/api/user-options/').status_code, 200)
        self.assertEqual(self.client.post(BASE + f'users/{self.target.pk}/role/',
                                        {'role_id': self.weak.pk}).status_code, 200)
        self.assertEqual(client.get('/api/user-options/').status_code, 403)

    def test_locked_account_django_session_does_not_revive_after_unlock(self):
        from django.test import Client
        client = Client()
        client.force_login(self.target)
        for active in (False, True):
            self.assertEqual(self.client.post(BASE + f'users/{self.target.pk}/status/',
                                            {'is_active': active}).status_code, 200)
        client.get('/admin/login/')
        self.assertNotIn('_auth_user_id', client.session)

    def test_missing_mutation_permissions_and_scoped_options(self):
        for action, field, data in (
            ('role/', 'can_assign_user_roles', {'role_id': self.weak.pk}),
            ('status/', 'can_manage_user_status', {'is_active': False}),
        ):
            setattr(self.actor.profile, field, False)
            self.actor.profile.save()
            response = self.client.post(BASE + f'users/{self.target.pk}/{action}', data)
            self.assertEqual(response.status_code, 403)
        self.actor.profile.can_edit_users = False
        self.actor.profile.save()
        self.assertEqual(self.client.patch(BASE + f'users/{self.target.pk}/',
                                         {'phone': '0123456789'}).status_code, 403)
        self.assertEqual(self.client.get(BASE + f'personnel-options/?nha_may={self.vs.pk}').status_code, 403)

    def test_contact_edit_is_audited_and_does_not_change_role(self):
        response = self.client.patch(BASE + f'users/{self.target.pk}/',
                                     {'phone': '0123456789', 'chuc_danh': 'Kỹ sư'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['role_id'], self.role.pk)
        self.assertEqual(response.data['phone'], '0123456789')
        audit = UserManagementAudit.objects.get(target=self.target)
        self.assertEqual(audit.action, 'edit')
        self.assertEqual(audit.changes['chuc_danh'][1], 'Kỹ sư')

    def test_permission_audit_is_read_only_unless_apply(self):
        from io import StringIO
        from django.core.management import call_command
        UserProfile.objects.filter(user=self.target).update(can_create_users=True)
        call_command('audit_account_permissions', stdout=StringIO())
        self.target.profile.refresh_from_db()
        self.assertTrue(self.target.profile.can_create_users)
        call_command('audit_account_permissions', apply=True, stdout=StringIO())
        self.target.profile.refresh_from_db()
        self.assertFalse(self.target.profile.can_create_users)
        self.actor.profile.refresh_from_db()
        self.assertTrue(self.actor.profile.can_create_users)

    def test_private_cache_headers_and_validation_language(self):
        response = self.client.get(BASE + 'users/')
        self.assertIn('no-store', response['Cache-Control'])
        payload = self.payload()
        payload.pop('username')
        response = self.post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('This field is required', str(response.data))


from concurrent.futures import ThreadPoolExecutor
from django.db import connections, close_old_connections
from django.test import TransactionTestCase


class ManagedUsersConcurrencyTests(TransactionTestCase):
    setUp = ManagedUsersTests.setUp
    make_user = ManagedUsersTests.make_user
    payload = ManagedUsersTests.payload

    def request_in_thread(self, payload):
        close_old_connections()
        try:
            client = APIClient()
            client.force_authenticate(User.objects.get(pk=self.actor.pk))
            return client.post(BASE + 'users/', payload, format='json').status_code
        finally:
            connections.close_all()

    def test_simultaneous_case_insensitive_username(self):
        one = self.payload()
        two = {**one, 'username': one['username'].upper(), 'email': 'different@example.com'}
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.request_in_thread, [one, two]))
        self.assertEqual(sorted(results), [201, 400])
        self.assertEqual(User.objects.filter(username__iexact=one['username']).count(), 1)

    def test_simultaneous_personnel_link(self):
        unit = DonViToChuc.objects.create(ma_don_vi='SH-NM', ten_don_vi='SH', nha_may=self.sh)
        department = BoPhan.objects.create(don_vi=unit, ma_bo_phan='VH', ten_bo_phan='Vận hành')
        staff = NhanSu.objects.create(don_vi=unit, bo_phan=department, ho_ten='Nhân sự')
        one = self.payload(nhan_su_id=staff.pk)
        two = {**one, 'username': 'second', 'email': 'second@example.com'}
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.request_in_thread, [one, two]))
        self.assertEqual(sorted(results), [201, 400])
        self.assertEqual(UserManagementAudit.objects.count(), 1)
