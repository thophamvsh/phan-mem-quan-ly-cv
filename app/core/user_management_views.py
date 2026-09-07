"""Factory-scoped account administration; no public signup or hard deletes."""
from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import translation
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from tochuc.models import DonViToChuc, NhanSu
from .models import User, UserProfile, UserManagementAudit
from .user_management_policy import ManagementPolicy, has_permission, plant_scope, require_permissions, resolve_plant
from .user_management_serializers import (
    CreateManagedUserSerializer, EditManagedUserSerializer,
    ChangeRoleSerializer, ChangeStatusSerializer, OptionsQuerySerializer,
)


class ManagementWriteThrottle(UserRateThrottle):
    scope = 'user_management'
    rate = '30/min'

    def allow_request(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return super().allow_request(request, view)


class ManagementPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def staff_for_plant(plant):
    # Resolve arbitrary organization depth without per-person ancestry queries.
    units = list(DonViToChuc.objects.values('id', 'nha_may_id', 'don_vi_cha_id'))
    included = {u['id'] for u in units if u['nha_may_id'] == plant.pk}
    while True:
        expanded = included | {u['id'] for u in units if not u['nha_may_id']
                               and u['don_vi_cha_id'] in included}
        if expanded == included:
            break
        included = expanded
    return NhanSu.objects.filter(don_vi_id__in=included)


def link_staff(user, plant, staff_id):
    staff = None
    if staff_id is not None:
        staff = get_object_or_404(staff_for_plant(plant).select_for_update(), pk=staff_id)
        if staff.user_id not in (None, user.pk):
            raise ValidationError({'nhan_su_id': 'Nhân sự đã liên kết tài khoản khác.'})
        if not staff.dang_lam_viec:
            raise ValidationError({'nhan_su_id': 'Nhân sự đã ngừng làm việc.'})
    NhanSu.objects.filter(user=user).exclude(pk=staff_id).update(user=None)
    if staff:
        staff.user = user
        staff.save(update_fields=['user', 'updated_at'])


def serialize_user(user, policy):
    profile = getattr(user, 'profile', None)
    plant = profile.nha_may if profile else None
    role = profile.role if profile else None
    staff = getattr(user, 'nhan_su_ca_truc', None)
    return {
        'id': user.pk, 'username': user.username, 'email': user.email,
        'first_name': user.first_name, 'last_name': user.last_name,
        'full_name': f'{user.first_name} {user.last_name}'.strip(),
        'phone': profile.phone or '' if profile else '',
        'chuc_danh': profile.chuc_danh or '' if profile else '',
        'nha_may': plant.pk if plant else None,
        'nha_may_name': plant.ten_nha_may if plant else '',
        'role_id': role.pk if role else None, 'role_name': role.name if role else '',
        'nhan_su_id': staff.pk if staff else None,
        'nhan_su_name': staff.ho_ten if staff else '',
        'is_active': user.is_active, **policy.capabilities(user),
    }


class AccountAPIResponseMixin:
    def dispatch(self, request, *args, **kwargs):
        with translation.override('vi'):
            return super().dispatch(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        return response


class ManagedUserViewSet(AccountAPIResponseMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ManagementWriteThrottle]
    pagination_class = ManagementPagination
    serializer_class = CreateManagedUserSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_permissions(request.user)
        self.policy = ManagementPolicy(request.user)

    def get_queryset(self):
        return User.objects.filter(profile__nha_may__in=plant_scope(self.request.user)).select_related(
            'profile__nha_may', 'profile__role', 'nhan_su_ca_truc',
        ).prefetch_related('groups', 'user_permissions').order_by('username', 'pk')

    def list(self, request):
        queryset = self.get_queryset()
        query = request.query_params
        for key, lookup in [('nha_may', 'profile__nha_may_id'), ('role_id', 'profile__role_id')]:
            if query.get(key):
                try:
                    value = int(query[key])
                except ValueError:
                    raise ValidationError({key: 'Giá trị không hợp lệ.'})
                if key == 'nha_may':
                    resolve_plant(request.user, value)
                queryset = queryset.filter(**{lookup: value})
        if query.get('is_active'):
            if query['is_active'] not in ('true', 'false'):
                raise ValidationError({'is_active': 'Trạng thái không hợp lệ.'})
            queryset = queryset.filter(is_active=query['is_active'] == 'true')
        if query.get('search'):
            term = query['search'][:255]
            queryset = queryset.filter(Q(username__icontains=term) | Q(email__icontains=term)
                                       | Q(first_name__icontains=term) | Q(last_name__icontains=term))
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response([serialize_user(user, self.policy) for user in page])

    def retrieve(self, request, pk=None):
        return Response(serialize_user(self.get_object(), self.policy))

    def create(self, request):
        require_permissions(request.user, 'can_create_users', 'can_assign_user_roles')
        serializer = CreateManagedUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data.copy()
        plant = resolve_plant(request.user, data.pop('nha_may', None))
        role = self.policy.roles(plant).filter(pk=data.pop('role_id')).first()
        if not role:
            raise PermissionDenied('Bạn không có quyền gán vai trò này.')
        staff_id = data.pop('nhan_su_id', None)
        data.pop('password_confirm')
        contact = {field: data.pop(field) for field in ('phone', 'chuc_danh') if field in data}
        try:
            with transaction.atomic():
                # Serialize case-insensitive uniqueness for this API, without
                # changing identifiers or constraints of existing legacy users.
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', [741903])
                for field in ('username', 'email'):
                    if User.objects.filter(**{f'{field}__iexact': data[field]}).exists():
                        raise ValidationError({field: 'Tên đăng nhập hoặc email đã tồn tại.'})
                user = User.objects.create_user(**data)
                UserProfile.objects.update_or_create(user=user, defaults={
                    **contact,
                    'nha_may': plant, 'role': role, 'individual_permissions': {},
                    'ho_ten': f'{user.first_name} {user.last_name}'.strip(),
                })
                if staff_id is not None:
                    link_staff(user, plant, staff_id)
                UserManagementAudit.objects.create(actor=request.user, target=user, nha_may=plant,
                                                   action='create', changes={'role_id': role.pk, 'nhan_su_id': staff_id})
        except IntegrityError:
            raise ValidationError('Tài khoản hoặc liên kết nhân sự đã tồn tại. Vui lòng tải lại.')
        return Response(serialize_user(self.get_queryset().get(pk=user.pk), self.policy), status=status.HTTP_201_CREATED)

    def _change(self, request, permission, serializer_class, operation):
        require_permissions(request.user, permission)
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                target = self.get_object()
                User.objects.select_for_update().get(pk=target.pk)
                target = self.get_queryset().get(pk=target.pk)
                self.policy.check_target(target)
                changes = operation(target, serializer.validated_data)
                if changes:
                    UserManagementAudit.objects.create(actor=request.user, target=target,
                                                       nha_may=target.profile.nha_may,
                                                       action='edit' if self.action == 'partial_update' else self.action,
                                                       changes=changes)
        except IntegrityError:
            raise ValidationError('Liên kết đã thay đổi. Vui lòng tải lại và thử lại.')
        return Response(serialize_user(self.get_queryset().get(pk=target.pk), self.policy))

    def partial_update(self, request, pk=None):
        def update(target, data):
            before = serialize_user(target, self.policy)
            for field in ('first_name', 'last_name'):
                if field in data:
                    setattr(target, field, data[field])
            target.save(update_fields=['first_name', 'last_name'])
            contact = {field: data[field] for field in ('phone', 'chuc_danh') if field in data}
            if contact:
                for field, value in contact.items():
                    setattr(target.profile, field, value)
                target.profile.save(update_fields=[*contact, 'updated_at'])
            if 'nhan_su_id' in data:
                link_staff(target, target.profile.nha_may, data['nhan_su_id'])
            return {key: [before.get(key), value] for key, value in data.items() if before.get(key) != value}
        return self._change(request, 'can_edit_users', EditManagedUserSerializer, update)

    @action(detail=True, methods=['post'])
    def role(self, request, pk=None):
        def update(target, data):
            role = self.policy.roles(target.profile.nha_may).filter(pk=data['role_id']).first()
            if not role:
                raise PermissionDenied('Bạn không có quyền gán vai trò này.')
            old = target.profile.role_id
            if old == role.pk:
                return {}
            target.profile.role = role
            target.profile.save(update_fields=['role', 'updated_at'])
            return {'role_id': [old, role.pk]}
        return self._change(request, 'can_assign_user_roles', ChangeRoleSerializer, update)

    @action(detail=True, methods=['post'])
    def status(self, request, pk=None):
        def update(target, data):
            old = target.is_active
            if old == data['is_active']:
                return {}
            target.is_active = data['is_active']
            target.session_version += 1
            target.save(update_fields=['is_active', 'session_version'])
            for token in OutstandingToken.objects.filter(user=target):
                BlacklistedToken.objects.get_or_create(token=token)
            return {'is_active': [old, target.is_active]}
        return self._change(request, 'can_manage_user_status', ChangeStatusSerializer, update)


class ManagementOptionsAPIView(AccountAPIResponseMixin, APIView):
    permission_classes = [IsAuthenticated]
    option = 'metadata'

    def get(self, request):
        require_permissions(request.user)
        if self.option == 'metadata':
            users = User.objects.filter(profile__nha_may__in=plant_scope(request.user))
            return Response({
                'plants': list(plant_scope(request.user).values('id', 'ten_nha_may')),
                'roles': list(users.exclude(profile__role=None).values(
                    'profile__role_id', 'profile__role__name').distinct()),
            })
        if self.option == 'roles':
            require_permissions(request.user, 'can_assign_user_roles')
        elif not any(has_permission(request.user, field) for field in ('can_create_users', 'can_edit_users')):
            raise PermissionDenied('Không có quyền lấy danh sách nhân sự.')
        serializer = OptionsQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        plant = resolve_plant(request.user, serializer.validated_data.get('nha_may'))
        if self.option == 'roles':
            return Response(list(ManagementPolicy(request.user).roles(plant).values('id', 'name')))
        return Response(list(staff_for_plant(plant).filter(user=None, dang_lam_viec=True).values(
            'id', 'ma_nhan_vien', 'ho_ten').order_by('ho_ten')))
