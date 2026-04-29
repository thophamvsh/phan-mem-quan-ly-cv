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
        ('ThÃ´ng tin há»“ sÆ¡', {
            'fields': ('full_name', 'ho_ten', 'ho', 'ten', 'phone', 'chuc_danh', 'is_mobile_user')
        }),
        ('Quyen nhat ky su kien van hanh', {
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
            'description': 'Quyen thao tac tren SuKien, KhacPhucSuKien va DienBienSuKien.'
        }),
        ('Quyen so giao nhan ca van hanh', {
            'fields': (
                'can_view_shift_handover_logs',
                'can_create_shift_handover_logs',
                'can_receive_shift_handover_logs',
                'can_edit_shift_handover_logs',
                'can_delete_shift_handover_logs',
            ),
            'description': 'Quyen xem, tao, nhan ca, sua va xoa So giao nhan ca VH.'
        }),
        ('Quyen so giao nhan ca hanh chinh', {
            'fields': (
                'can_view_admin_shift_handover_logs',
                'can_create_admin_shift_handover_logs',
                'can_receive_admin_shift_handover_logs',
                'can_edit_admin_shift_handover_logs',
                'can_delete_admin_shift_handover_logs',
            ),
            'description': 'Quyen xem, tao, nhan ca, sua va xoa So giao nhan ca HC.'
        }),
        ('Quyen so nhat ky van hanh', {
            'fields': (
                'can_view_operation_logbooks',
                'can_create_operation_logbooks',
                'can_confirm_operation_logbooks',
                'can_edit_operation_logbooks',
                'can_delete_operation_logbooks',
            ),
            'description': 'Quyen xem, tao, xac nhan, sua va xoa So nhat ky van hanh.'
        }),
        ('Quyen so nhat ky van hanh Diesel', {
            'fields': (
                'can_view_diesel_operation_logbooks',
                'can_create_diesel_operation_logbooks',
                'can_edit_diesel_operation_logbooks',
                'can_delete_diesel_operation_logbooks',
            ),
            'description': 'Quyen xem, tao, sua va xoa So nhat ky van hanh Diesel.'
        }),
        ('HÃ¬nh áº£nh', {
            'fields': ('avatar', 'chu_ky')
        }),
        ('Thá»i gian', {
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
        ('ThÃ´ng tin cÆ¡ báº£n', {
            'fields': ('user', 'ho_ten', 'ho', 'ten', 'phone', 'chuc_danh', 'is_mobile_user')
        }),
        ('PhÃ¢n quyá»n nhÃ  mÃ¡y', {
            'fields': ('nha_may', 'is_all_factories'),
            'description': 'GÃ¡n nhÃ  mÃ¡y cho user. Náº¿u chá»n "Táº¥t cáº£ nhÃ  mÃ¡y" thÃ¬ user cÃ³ quyá»n truy cáº­p má»i nhÃ  mÃ¡y.'
        }),
        ('Quyá»n xem dá»¯ liá»‡u', {
            'fields': ('can_view_materials', 'can_view_inventory', 'can_view_reports'),
            'description': 'Quyá»n xem cÃ¡c loáº¡i dá»¯ liá»‡u khÃ¡c nhau'
        }),
        ('Quyá»n thao tÃ¡c váº­t tÆ°', {
            'fields': ('can_add_materials', 'can_edit_materials', 'can_delete_materials'),
            'description': 'Quyá»n thÃªm, sá»­a, xÃ³a váº­t tÆ°'
        }),
        ('Quyá»n Excel', {
            'fields': ('can_import_excel', 'can_export_excel'),
            'description': 'Quyá»n import vÃ  export dá»¯ liá»‡u Excel'
        }),
        ('Quyá»n Ä‘á» nghá»‹ xuáº¥t', {
            'fields': ('can_create_export_request', 'can_approve_export_request', 'can_view_export_requests'),
            'description': 'Quyá»n táº¡o, duyá»‡t vÃ  xem Ä‘á» nghá»‹ xuáº¥t'
        }),
        ('Quyá»n Ä‘á» nghá»‹ nháº­p', {
            'fields': ('can_create_import_request', 'can_approve_import_request', 'can_view_import_requests'),
            'description': 'Quyá»n táº¡o, duyá»‡t vÃ  xem Ä‘á» nghá»‹ nháº­p'
        }),
        ('Quyá»n kiá»ƒm kÃª', {
            'fields': ('can_edit_inventory',),
            'description': 'Quyá»n sá»­a thÃ´ng tin kiá»ƒm kÃª'
        }),
        ('Quyen nhat ky su kien van hanh', {
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
            'description': 'Quyen thao tac tren SuKien, KhacPhucSuKien va DienBienSuKien.'
        }),
        ('Quyen so giao nhan ca van hanh', {
            'fields': (
                'can_view_shift_handover_logs',
                'can_create_shift_handover_logs',
                'can_receive_shift_handover_logs',
                'can_edit_shift_handover_logs',
                'can_delete_shift_handover_logs',
            ),
            'description': 'Quyen xem, tao, nhan ca, sua va xoa So giao nhan ca VH.'
        }),
        ('Quyen so giao nhan ca hanh chinh', {
            'fields': (
                'can_view_admin_shift_handover_logs',
                'can_create_admin_shift_handover_logs',
                'can_receive_admin_shift_handover_logs',
                'can_edit_admin_shift_handover_logs',
                'can_delete_admin_shift_handover_logs',
            ),
            'description': 'Quyen xem, tao, nhan ca, sua va xoa So giao nhan ca HC.'
        }),
        ('Quyen so nhat ky van hanh', {
            'fields': (
                'can_view_operation_logbooks',
                'can_create_operation_logbooks',
                'can_confirm_operation_logbooks',
                'can_edit_operation_logbooks',
                'can_delete_operation_logbooks',
            ),
            'description': 'Quyen xem, tao, xac nhan, sua va xoa So nhat ky van hanh.'
        }),
        ('Quyen so nhat ky van hanh Diesel', {
            'fields': (
                'can_view_diesel_operation_logbooks',
                'can_create_diesel_operation_logbooks',
                'can_edit_diesel_operation_logbooks',
                'can_delete_diesel_operation_logbooks',
            ),
            'description': 'Quyen xem, tao, sua va xoa So nhat ky van hanh Diesel.'
        }),
        ('HÃ¬nh áº£nh', {
            'fields': ('avatar', 'chu_ky')
        }),
        ('Thá»i gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'TÃªn Ä‘áº§y Ä‘á»§'

    def nha_may(self, obj):
        if obj.is_all_factories:
            return "Táº¥t cáº£ nhÃ  mÃ¡y"
        elif obj.nha_may:
            return f"{obj.nha_may.ma_nha_may} - {obj.nha_may.ten_nha_may}"
        else:
            return "ChÆ°a gÃ¡n"
    nha_may.short_description = 'NhÃ  mÃ¡y'
