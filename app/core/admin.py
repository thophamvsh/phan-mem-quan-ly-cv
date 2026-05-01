from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile


class CustomUserCreationForm(UserCreationForm):
    """Custom form for creating users"""
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'email' in self.fields:
            self.fields['email'].required = True


class CustomUserChangeForm(UserChangeForm):
    """Custom form for changing users"""
    class Meta:
        model = User
        fields = '__all__'


class UserProfileInline(admin.StackedInline):
    """Show profile media and extra fields directly inside User admin."""
    model = UserProfile
    can_delete = False
    fk_name = 'user'
    extra = 0
    readonly_fields = ('created_at', 'updated_at', 'full_name')
    fieldsets = (
        ('Thông tin hồ sơ', {
            'fields': ('full_name', 'ho_ten', 'ho', 'ten', 'phone', 'chuc_danh', 'is_mobile_user')
        }),
        ('Quyền nhật ký sự kiện vận hành', {
            'fields': (
                'can_view_operation_events',
                'can_create_operation_events',
                'can_edit_own_operation_events',
                'can_edit_all_operation_events',
                'can_delete_own_operation_events',
                'can_delete_all_operation_events',
                'can_acknowledge_operation_events',
                'can_process_operation_events',
                'can_confirm_operation_events',
                'can_add_event_developments',
                'can_edit_own_event_developments',
                'can_edit_all_event_developments',
                'can_edit_own_remediations',
                'can_edit_all_remediations',
            ),
            'description': 'Quyền thao tác trên SựKiện, KhắcPhụcSựKiện và DiễnBiếnSựKiện.'
        }),
        ('Quyền sổ giao nhận ca vận hành', {
            'fields': (
                'can_view_shift_handover_logs',
                'can_create_shift_handover_logs',
                'can_receive_shift_handover_logs',
                'can_edit_shift_handover_logs',
                'can_delete_shift_handover_logs',
            ),
            'description': 'Quyền xem, tạo, nhận ca, sửa và xóa Sổ giao nhận ca VH.'
        }),
        ('Quyền sổ giao nhận ca hành chính', {
            'fields': (
                'can_view_admin_shift_handover_logs',
                'can_create_admin_shift_handover_logs',
                'can_receive_admin_shift_handover_logs',
                'can_edit_admin_shift_handover_logs',
                'can_delete_admin_shift_handover_logs',
            ),
            'description': 'Quyền xem, tạo, nhận ca, sửa và xóa Sổ giao nhận ca HC.'
        }),
        ('Quyền sổ nhật ký vận hành', {
            'fields': (
                'can_view_operation_logbooks',
                'can_create_operation_logbooks',
                'can_confirm_operation_logbooks',
                'can_edit_operation_logbooks',
                'can_delete_operation_logbooks',
            ),
            'description': 'Quyền xem, tạo, xác nhận, sửa và xóa Sổ nhật ký vận hành.'
        }),
        ('Quyền sổ nhật ký vận hành Diesel', {
            'fields': (
                'can_view_diesel_operation_logbooks',
                'can_create_diesel_operation_logbooks',
                'can_edit_diesel_operation_logbooks',
                'can_delete_diesel_operation_logbooks',
            ),
            'description': 'Quyền xem, tạo, sửa và xóa Sổ nhật ký vận hành Diesel.'
        }),
        ('Quyền quản lý thiết bị vận hành', {
            'fields': (
                'can_view_equipment',
                'can_create_equipment',
                'can_edit_equipment',
                'can_delete_equipment',
            ),
            'description': 'Quyền xem, thêm, sửa và xóa thiết bị trong Quản lý vận hành.'
        }),
        ('Quyền thông số vận hành', {
            'fields': (
                'can_view_operation_parameters',
                'can_create_operation_parameters',
                'can_edit_operation_parameters',
                'can_delete_operation_parameters',
            ),
            'description': 'Quyền xem, thêm, sửa và xóa thông số vận hành.'
        }),
        ('Hình ảnh', {
            'fields': ('avatar', 'chu_ky')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for custom User model"""
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ('email', 'username', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)
    inlines = [UserProfileInline]

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('username', 'first_name', 'last_name')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for UserProfile model"""
    list_display = ('user', 'full_name', 'phone', 'chuc_danh', 'nha_may', 'is_all_factories', 'is_mobile_user', 'created_at')
    list_filter = ('is_mobile_user', 'is_all_factories', 'nha_may', 'created_at', 'updated_at')
    search_fields = ('user__email', 'user__username', 'user__first_name', 'user__last_name', 'phone', 'chuc_danh', 'nha_may__ma_nha_may', 'nha_may__ten_nha_may')
    readonly_fields = ('created_at', 'updated_at', 'full_name')

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('user', 'ho_ten', 'ho', 'ten', 'phone', 'chuc_danh', 'is_mobile_user')
        }),
        ('Phân quyền nhà máy', {
            'fields': ('nha_may', 'is_all_factories'),
            'description': 'Gán nhà máy cho user. Nếu chọn "Tất cả nhà máy" thì user có quyền truy cập mọi nhà máy.'
        }),
        ('Quyền xem dữ liệu', {
            'fields': ('can_view_materials', 'can_view_inventory', 'can_view_reports'),
            'description': 'Quyền xem các loại dữ liệu khác nhau'
        }),
        ('Quyền thao tác vật tư', {
            'fields': ('can_add_materials', 'can_edit_materials', 'can_delete_materials'),
            'description': 'Quyền thêm, sửa, xóa vật tư'
        }),
        ('Quyền Excel', {
            'fields': ('can_import_excel', 'can_export_excel'),
            'description': 'Quyền import và export dữ liệu Excel'
        }),
        ('Quyền đề nghị xuất', {
            'fields': ('can_create_export_request', 'can_approve_export_request', 'can_view_export_requests'),
            'description': 'Quyền tạo, duyệt và xem đề nghị xuất'
        }),
        ('Quyền đề nghị nhập', {
            'fields': ('can_create_import_request', 'can_approve_import_request', 'can_view_import_requests'),
            'description': 'Quyền tạo, duyệt và xem đề nghị nhập'
        }),
        ('Quyền kiểm kê', {
            'fields': ('can_edit_inventory',),
            'description': 'Quyền sửa thông tin kiểm kê'
        }),
        ('Quyền nhật ký sự kiện vận hành', {
            'fields': (
                'can_view_operation_events',
                'can_create_operation_events',
                'can_edit_own_operation_events',
                'can_edit_all_operation_events',
                'can_delete_own_operation_events',
                'can_delete_all_operation_events',
                'can_acknowledge_operation_events',
                'can_process_operation_events',
                'can_confirm_operation_events',
                'can_add_event_developments',
                'can_edit_own_event_developments',
                'can_edit_all_event_developments',
                'can_edit_own_remediations',
                'can_edit_all_remediations',
            ),
            'description': 'Quyền thao tác trên SựKiện, KhắcPhụcSựKiện và DiễnBiếnSựKiện.'
        }),
        ('Quyền sổ giao nhận ca vận hành', {
            'fields': (
                'can_view_shift_handover_logs',
                'can_create_shift_handover_logs',
                'can_receive_shift_handover_logs',
                'can_edit_shift_handover_logs',
                'can_delete_shift_handover_logs',
            ),
            'description': 'Quyền xem, tạo, nhận ca, sửa và xóa Sổ giao nhận ca VH.'
        }),
        ('Quyền sổ giao nhận ca hành chính', {
            'fields': (
                'can_view_admin_shift_handover_logs',
                'can_create_admin_shift_handover_logs',
                'can_receive_admin_shift_handover_logs',
                'can_edit_admin_shift_handover_logs',
                'can_delete_admin_shift_handover_logs',
            ),
            'description': 'Quyền xem, tạo, nhận ca, sửa và xóa Sổ giao nhận ca HC.'
        }),
        ('Quyền sổ nhật ký vận hành', {
            'fields': (
                'can_view_operation_logbooks',
                'can_create_operation_logbooks',
                'can_confirm_operation_logbooks',
                'can_edit_operation_logbooks',
                'can_delete_operation_logbooks',
            ),
            'description': 'Quyền xem, tạo, xác nhận, sửa và xóa Sổ nhật ký vận hành.'
        }),
        ('Quyền sổ nhật ký vận hành Diesel', {
            'fields': (
                'can_view_diesel_operation_logbooks',
                'can_create_diesel_operation_logbooks',
                'can_edit_diesel_operation_logbooks',
                'can_delete_diesel_operation_logbooks',
            ),
            'description': 'Quyền xem, tạo, sửa và xóa Sổ nhật ký vận hành Diesel.'
        }),
        ('Quyền quản lý thiết bị vận hành', {
            'fields': (
                'can_view_equipment',
                'can_create_equipment',
                'can_edit_equipment',
                'can_delete_equipment',
            ),
            'description': 'Quyền xem, thêm, sửa và xóa thiết bị trong Quản lý vận hành.'
        }),
        ('Quyền thông số vận hành', {
            'fields': (
                'can_view_operation_parameters',
                'can_create_operation_parameters',
                'can_edit_operation_parameters',
                'can_delete_operation_parameters',
            ),
            'description': 'Quyền xem, thêm, sửa và xóa thông số vận hành.'
        }),
        ('Hình ảnh', {
            'fields': ('avatar', 'chu_ky')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Tên đầy đủ'

    def nha_may(self, obj):
        if obj.is_all_factories:
            return "Tất cả nhà máy"
        elif obj.nha_may:
            return f"{obj.nha_may.ma_nha_may} - {obj.nha_may.ten_nha_may}"
        else:
            return "Chưa gán"
    nha_may.short_description = 'Nhà máy'
