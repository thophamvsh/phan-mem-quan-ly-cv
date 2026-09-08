import re
from datetime import timedelta
from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import UserActivityLog, UserManagementAudit
from .audit_plant_resolver import get_plant_cache, get_plant_details, resolve_plant_id

User = get_user_model()

# Từ điển ánh xạ tên model sang nhãn tiếng Việt chuẩn mực
MODEL_DISPLAY_NAMES = {
    'sogiaonhancavh': 'Sổ giao nhận ca vận hành',
    'chitietsogiaonhancavh': 'Chi tiết ca vận hành',
    'luuychidaosogiaonhancavh': 'Lưu ý chỉ đạo giao ca VH',
    'sogiaonhancahc': 'Sổ giao nhận ca hành chính',
    'chitietsogiaonhancahc': 'Chi tiết ca hành chính',
    'nguoitrucsogiaonhancahc': 'Người trực giao ca HC',
    'sukien': 'Nhật ký sự kiện',
    'dienbiensukien': 'Diễn biến sự kiện',
    'chidaosukien': 'Chỉ đạo sự kiện',
    'khacphucsukien': 'Khắc phục sự kiện',
    'sonhatkyvanhanh': 'Sổ nhật ký vận hành',
    'sonhatkyvanhanhdiesel': 'Sổ nhật ký vận hành Diesel',
    'sobchcsonghinh': 'Sổ BCHC Sông Hinh',
    'soantoandaugio': 'Sổ an toàn đầu giờ',
    'mauchuyendoithietbi': 'Mẫu chuyển đổi thiết bị tuần',
    'sochuyendoithietbituan': 'Sổ chuyển đổi thiết bị tuần',
    'lanchuyendoithietbi': 'Lần chuyển đổi thiết bị tuần',
    'chitietchuyendoithietbi': 'Chi tiết chuyển đổi thiết bị tuần',
    'mauchuyendoitbthang': 'Mẫu chuyển đổi thiết bị tháng',
    'sochuyendoitbthang': 'Sổ chuyển đổi thiết bị tháng',
    'chitietchuyendoitbthang': 'Chi tiết chuyển đổi thiết bị tháng',
    'mautrangthaithietbica': 'Mẫu trạng thái thiết bị ca',
    'nhommautrangthaithietbica': 'Nhóm mẫu trạng thái thiết bị ca',
    'chitietmautrangthaithietbica': 'Chi tiết trạng thái thiết bị ca',
    'mautomluocgiaocavh': 'Mẫu tóm lược giao ca VH',
    'hangmucmautomluocgiaocavh': 'Hạng mục mẫu tóm lược giao ca VH',
    'thietbi': 'Thiết bị vận hành',
    'thongsovanhanh': 'Thông số vận hành',
    'thongsotomay': 'Thông số tổ máy',
    'thongsotram110kv': 'Thông số trạm 110kV',
    'nguongthongso': 'Ngưỡng thông số vận hành',
    'kiptruc': 'Kíp trực ca',
    'thanhvienkiptruc': 'Thành viên kíp trực',
    'mauchukycatruc': 'Mẫu chu kỳ ca trực',
    'lichtrucca': 'Lịch trực ca',
    'ngaytrucca': 'Ngày trực ca',
    'nhamay': 'Danh mục Nhà máy',
    'donvitochuc': 'Đơn vị tổ chức',
    'bophan': 'Bộ phận tổ chức',
    'nhansu': 'Nhân sự',
}

ACTION_DISPLAY_MAP = {
    0: 'Tạo mới',
    1: 'Cập nhật',
    2: 'Xóa',
    3: 'Truy cập',
}

USER_MGT_ACTION_MAP = {
    'create': 'Tạo tài khoản',
    'edit': 'Sửa thông tin',
    'role': 'Đổi vai trò',
    'status': 'Khóa/Mở tài khoản',
}

SENSITIVE_KEY_PATTERN = re.compile(
    r'(^|[_\-.])(password|passwd|pwd|token|secret|jwt|bearer|authorization|credential|api[_-]?key)($|[_\-.])',
    re.IGNORECASE,
)
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+'),
    re.compile(r'(?i)((?:password|passwd|pwd|token|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+'),
    re.compile(r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b'),
)
REDACTED_VALUE = '[ĐÃ ẨN]'


def sanitize_text(value):
    if not isinstance(value, str):
        return value
    cleaned = value
    for pattern in SENSITIVE_TEXT_PATTERNS:
        cleaned = pattern.sub(
            lambda match: f"{match.group(1)}{REDACTED_VALUE}"
            if match.lastindex else REDACTED_VALUE,
            cleaned,
        )
    return cleaned


def sanitize_audit_payload(value, key=None):
    if key is not None and SENSITIVE_KEY_PATTERN.search(str(key)):
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return [REDACTED_VALUE, REDACTED_VALUE]
        return REDACTED_VALUE
    if isinstance(value, dict):
        return {
            item_key: sanitize_audit_payload(item, item_key)
            for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_audit_payload(item) for item in value]
    return sanitize_text(value)


def sanitize_changes(changes):
    if not isinstance(changes, dict):
        return {}
    return sanitize_audit_payload(changes)


def latest_change_value(value):
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[1]
    return value


class AuditFilterSerializer(serializers.Serializer):
    plant_id = serializers.IntegerField(required=False, min_value=1)
    nha_may = serializers.IntegerField(required=False, min_value=1)
    action = serializers.CharField(required=False, allow_blank=True, max_length=32)
    action_type = serializers.CharField(required=False, allow_blank=True, max_length=32)
    model = serializers.CharField(required=False, allow_blank=True, max_length=100)
    model_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    content_type_id = serializers.IntegerField(required=False, min_value=1)
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    search = serializers.CharField(
        required=False, allow_blank=True, max_length=200, trim_whitespace=True
    )

    def validate(self, attrs):
        from_date = attrs.get('from_date')
        to_date = attrs.get('to_date')
        if from_date and to_date:
            if from_date > to_date:
                raise serializers.ValidationError({
                    'to_date': 'Ngày kết thúc phải từ ngày bắt đầu trở đi.'
                })
            if to_date - from_date > timedelta(days=366):
                raise serializers.ValidationError({
                    'to_date': 'Khoảng thời gian tra cứu tối đa là 366 ngày.'
                })
        return attrs


class AuditExportRequestSerializer(AuditFilterSerializer):
    tab = serializers.ChoiceField(
        choices=('activity', 'data', 'data_changes', 'user_management')
    )

    def validate_tab(self, value):
        return 'data' if value == 'data_changes' else value


def format_user_display(user):
    if not user:
        return 'Hệ thống / Vô danh'
    full_name = getattr(user, 'first_name', '') + ' ' + getattr(user, 'last_name', '')
    full_name = full_name.strip()
    if hasattr(user, 'profile') and getattr(user.profile, 'ho_ten', None):
        full_name = user.profile.ho_ten.strip()
    return full_name if full_name else user.username


class UserActivityLogSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    ip_address = serializers.SerializerMethodField()
    user_agent = serializers.SerializerMethodField()
    nha_may_id = serializers.IntegerField(source='nha_may.id', read_only=True)
    nha_may_code = serializers.CharField(source='nha_may.ma_nha_may', read_only=True)
    nha_may_name = serializers.CharField(source='nha_may.ten_nha_may', read_only=True)

    class Meta:
        model = UserActivityLog
        fields = (
            'id', 'user_id', 'username', 'full_name', 'action_type',
            'action_display', 'description', 'ip_address', 'user_agent',
            'nha_may_id', 'nha_may_code', 'nha_may_name', 'timestamp'
        )

    def get_full_name(self, obj):
        return format_user_display(obj.user)

    def get_action_display(self, obj):
        action_map = {
            'LOGIN': 'Đăng nhập',
            'LOGOUT': 'Đăng xuất',
            'LOGIN_FAILED': 'Đăng nhập thất bại',
        }
        return action_map.get(obj.action_type, obj.action_type)

    def get_description(self, obj):
        return sanitize_text(obj.description)

    def get_user_agent(self, obj):
        return sanitize_text(obj.user_agent)

    def get_ip_address(self, obj):
        ip = obj.ip_address or ''
        request = self.context.get('request')
        if not request:
            return ip
        # Nếu user không có quyền xem activity log đầy đủ hoặc không phải superuser, mask IP
        user = request.user
        can_view = bool(user and (user.is_superuser or getattr(user, 'is_staff', False) or
                                  (hasattr(user, 'profile') and user.profile.has_effective_permission('can_view_activity_logs'))))
        if can_view:
            return ip
        # Masking: vd 192.168.1.100 -> 192.168.*.*
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
        return '***.***.***.***' if ip else ''


class DataChangeLogSerializer(serializers.ModelSerializer):
    content_type_id = serializers.IntegerField(source='content_type.id', read_only=True)
    model_name = serializers.CharField(source='content_type.model', read_only=True)
    app_label = serializers.CharField(source='content_type.app_label', read_only=True)
    content_type_display = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()
    actor_id = serializers.IntegerField(source='actor.id', read_only=True)
    actor_username = serializers.CharField(source='actor.username', read_only=True)
    actor_name = serializers.SerializerMethodField()
    plant_id = serializers.SerializerMethodField()
    plant_code = serializers.SerializerMethodField()
    plant_name = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()
    changes_display = serializers.SerializerMethodField()
    object_repr = serializers.SerializerMethodField()

    class Meta:
        model = LogEntry
        fields = (
            'id', 'content_type_id', 'model_name', 'app_label',
            'content_type_display', 'object_pk', 'object_repr',
            'action', 'action_display', 'actor_id', 'actor_username',
            'actor_name', 'plant_id', 'plant_code', 'plant_name',
            'changes', 'changes_display', 'timestamp'
        )

    def get_content_type_display(self, obj):
        model = obj.content_type.model.lower() if obj.content_type else ''
        return MODEL_DISPLAY_NAMES.get(model, obj.content_type.name if obj.content_type else model)

    def get_object_repr(self, obj):
        return sanitize_text(obj.object_repr)

    def get_action_display(self, obj):
        return ACTION_DISPLAY_MAP.get(obj.action, str(obj.action))

    def get_actor_name(self, obj):
        return format_user_display(obj.actor)

    def _get_plant_info(self, obj):
        if not hasattr(obj, '_cached_plant_info'):
            add_data = obj.additional_data or {}
            plant_id = add_data.get('plant_id') if isinstance(add_data, dict) else None
            plant_code = add_data.get('plant_code') if isinstance(add_data, dict) else None

            # Fallback nếu log cũ chưa có snapshot
            if plant_id is None:
                try:
                    target_model = obj.content_type.model_class()
                    if target_model:
                        instance = target_model.objects.filter(pk=obj.object_pk).first()
                        if instance:
                            plant_id = resolve_plant_id(instance)
                except Exception:
                    pass

            if plant_id and not plant_code:
                cache = get_plant_cache()
                plant_code = cache.get(plant_id)

            obj._cached_plant_info = (plant_id, plant_code)
        return obj._cached_plant_info

    def get_plant_id(self, obj):
        return self._get_plant_info(obj)[0]

    def get_plant_code(self, obj):
        return self._get_plant_info(obj)[1]

    def get_plant_name(self, obj):
        plant_id = self.get_plant_id(obj)
        if not plant_id:
            return 'Toàn cục / Không xác định'
        details = get_plant_details(plant_id)
        if details:
            return details['ten_nha_may']
        code = self.get_plant_code(obj)
        return f"Nhà máy ({code})" if code else f"Nhà máy #{plant_id}"

    def get_changes(self, obj):
        return sanitize_changes(obj.changes)

    def get_changes_display(self, obj):
        """Trả về danh sách đối chiếu trường trước/sau cho Modal trực quan"""
        changes = sanitize_changes(obj.changes)
        formatted = []
        for field, diff in changes.items():
            if isinstance(diff, (list, tuple)) and len(diff) == 2:
                old_val, new_val = diff
            else:
                old_val, new_val = None, diff
            formatted.append({
                'field': field,
                'old_value': str(old_val) if old_val is not None else '—',
                'new_value': str(new_val) if new_val is not None else '—',
            })
        return formatted


class UserManagementAuditSerializer(serializers.ModelSerializer):
    actor_id = serializers.IntegerField(source='actor.id', read_only=True)
    actor_username = serializers.CharField(source='actor.username', read_only=True)
    actor_name = serializers.SerializerMethodField()
    target_id = serializers.IntegerField(source='target.id', read_only=True)
    target_username = serializers.CharField(source='target.username', read_only=True)
    target_name = serializers.SerializerMethodField()
    nha_may_id = serializers.IntegerField(source='nha_may.id', read_only=True)
    nha_may_code = serializers.CharField(source='nha_may.ma_nha_may', read_only=True)
    nha_may_name = serializers.CharField(source='nha_may.ten_nha_may', read_only=True)
    action_display = serializers.SerializerMethodField()
    changes = serializers.SerializerMethodField()
    changes_display = serializers.SerializerMethodField()

    class Meta:
        model = UserManagementAudit
        fields = (
            'id', 'actor_id', 'actor_username', 'actor_name',
            'target_id', 'target_username', 'target_name',
            'nha_may_id', 'nha_may_code', 'nha_may_name',
            'action', 'action_display', 'changes', 'changes_display',
            'created_at'
        )

    def get_actor_name(self, obj):
        return format_user_display(obj.actor)

    def get_target_name(self, obj):
        return format_user_display(obj.target)

    def get_action_display(self, obj):
        return USER_MGT_ACTION_MAP.get(obj.action, obj.action)

    def get_changes(self, obj):
        return sanitize_changes(obj.changes)

    def get_changes_display(self, obj):
        """Định dạng mô tả tiếng Việt thân thiện thay vì JSON thô"""
        changes = sanitize_changes(obj.changes)
        action = obj.action

        if action == 'create':
            role_id = latest_change_value(changes.get('role_id'))
            return f"Tạo tài khoản mới (Vai trò ID: {role_id or 'Mặc định'})"

        if action == 'status':
            is_active = latest_change_value(changes.get('is_active'))
            if is_active is not None:
                status_str = "Hoạt động" if is_active else "Bị khóa"
                return f"Đổi trạng thái tài khoản: {status_str}"

        if action == 'role':
            role_id = latest_change_value(changes.get('role_id'))
            return f"Gán vai trò mới (ID vai trò: {role_id})"

        if action == 'edit':
            modified_fields = list(changes.keys())
            if modified_fields:
                return f"Cập nhật thông tin: {', '.join(modified_fields)}"

        return "Cập nhật dữ liệu"
