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


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for custom User model"""
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ('email', 'username', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('email',)

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

    def save_model(self, request, obj, form, change):
        """Override save to sync name with User model"""
        # Save the profile first - this will trigger the sync logic in UserProfile.save()
        super().save_model(request, obj, form, change)

        # Log the change
        self.log_change(request, obj, f"Updated user name to: {obj.user.first_name} {obj.user.last_name}")
