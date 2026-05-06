"""
Database models.
"""
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)




class UserManager(BaseUserManager):
    """Manager for users."""


    def create_user(self, email, password=None, username=None, **extra_fields):
        """Create, save and return a new user."""
        if not email:
            raise ValueError('User must have an email address')
        email = self.normalize_email(email)

        # Generate username if not provided
        if not username:
            username = email.split('@')[0]  # Use email prefix as default username

        user = self.model(email=email, username=username, **extra_fields)

        # Validate password using Django's validators
        if password:
            from django.core.exceptions import ValidationError
            from django.contrib.auth.password_validation import validate_password
            try:
                validate_password(password, user)
            except ValidationError as e:
                raise ValueError(f"Password validation failed: {', '.join(e.messages)}")

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a new superuser."""
        user = self.create_user(email, password, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user




class User(AbstractBaseUser, PermissionsMixin):
    """User in the system."""
    email = models.EmailField(max_length=255, unique=True)
    username = models.CharField(max_length=255, unique=True, help_text="Tên đăng nhập", default='')
    first_name = models.CharField(max_length=255, blank=True, help_text="Họ")
    last_name = models.CharField(max_length=255, blank=True, help_text="Tên")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Override save to sync name with UserProfile"""
        sync_from_profile = kwargs.pop('sync_from_profile', False)

        # Save the user first
        super().save(*args, **kwargs)

        if sync_from_profile:
            return

        # Update UserProfile if it exists
        try:
            profile = self.profile

            # Admin inline can attach an unsaved profile instance to the reverse cache.
            # update_fields on an object without pk triggers force_update and crashes.
            if not profile.pk:
                return

            update_fields = []

            # Update profile fields based on User model first_name and last_name
            if self.first_name and self.last_name:
                new_ho_ten = f"{self.first_name} {self.last_name}".strip()
                new_ho = self.first_name
                new_ten = self.last_name
            elif self.first_name:
                new_ho_ten = self.first_name
                new_ho = self.first_name
                new_ten = ""
            elif self.last_name:
                new_ho_ten = self.last_name
                new_ho = ""
                new_ten = self.last_name
            else:
                new_ho_ten = profile.ho_ten
                new_ho = profile.ho
                new_ten = profile.ten

            if profile.ho_ten != new_ho_ten:
                profile.ho_ten = new_ho_ten
                update_fields.append('ho_ten')
            if profile.ho != new_ho:
                profile.ho = new_ho
                update_fields.append('ho')
            if profile.ten != new_ten:
                profile.ten = new_ten
                update_fields.append('ten')

            if update_fields:
                # Save the profile without triggering User save again
                profile.save(sync_from_user=True, update_fields=update_fields + ['updated_at'])
        except UserProfile.DoesNotExist:
            # No profile exists yet, skip sync
            pass


class UserProfile(models.Model):
    """
    Profile model liên kết với custom User model
    Chứa các thông tin bổ sung cho user
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        help_text="Liên kết với User model"
    )
    ho_ten = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Họ và tên đầy đủ của user"
    )
    ho = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Họ của user"
    )
    ten = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Tên của user"
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_mobile_user = models.BooleanField(
        default=True,
        help_text="Đánh dấu user có thể đăng nhập từ mobile app"
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text="Hình ảnh đại diện của user"
    )
    chuc_danh = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Chức danh công việc của user"
    )
    chu_ky = models.ImageField(
        upload_to='signatures/',
        blank=True,
        null=True,
        help_text="Hình ảnh chữ ký của user"
    )
    # Phân quyền nhà máy
    nha_may = models.ForeignKey(
        'khovattu.Bang_nha_may',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Nhà máy mà user được phép truy cập (null = tất cả nhà máy)"
    )
    is_all_factories = models.BooleanField(
        default=False,
        help_text="User có quyền truy cập tất cả nhà máy"
    )

    # Phân quyền chi tiết cho kho
    can_view_materials = models.BooleanField(
        default=True,
        help_text="Có quyền xem danh sách vật tư"
    )
    can_add_materials = models.BooleanField(
        default=False,
        help_text="Có quyền thêm vật tư mới"
    )
    can_edit_materials = models.BooleanField(
        default=False,
        help_text="Có quyền sửa thông tin vật tư"
    )
    can_delete_materials = models.BooleanField(
        default=False,
        help_text="Có quyền xóa vật tư"
    )
    can_import_excel = models.BooleanField(
        default=False,
        help_text="Có quyền import dữ liệu từ Excel"
    )
    can_export_excel = models.BooleanField(
        default=True,
        help_text="Có quyền export dữ liệu ra Excel"
    )
    can_create_export_request = models.BooleanField(
        default=False,
        help_text="Có quyền tạo đề nghị xuất"
    )
    can_approve_export_request = models.BooleanField(
        default=False,
        help_text="Có quyền phê duyệt đề nghị xuất"
    )
    can_create_import_request = models.BooleanField(
        default=False,
        help_text="Có quyền tạo đề nghị nhập"
    )
    can_approve_import_request = models.BooleanField(
        default=False,
        help_text="Có quyền phê duyệt đề nghị nhập"
    )
    can_view_inventory = models.BooleanField(
        default=True,
        help_text="Có quyền xem kiểm kê"
    )
    can_edit_inventory = models.BooleanField(
        default=False,
        help_text="Có quyền sửa thông tin kiểm kê"
    )
    can_view_reports = models.BooleanField(
        default=True,
        help_text="Có quyền xem báo cáo thống kê"
    )
    can_view_import_requests = models.BooleanField(
        default=True,
        help_text="Có quyền xem đề nghị nhập"
    )
    can_view_export_requests = models.BooleanField(
        default=True,
        help_text="Có quyền xem đề nghị xuất"
    )

    # Phan quyen nhat ky van hanh - su kien
    can_view_operation_events = models.BooleanField(
        default=True,
        help_text="Co quyen xem nhat ky su kien van hanh"
    )
    can_create_operation_events = models.BooleanField(
        default=False,
        help_text="Co quyen tao moi su kien van hanh"
    )
    can_edit_own_operation_events = models.BooleanField(
        default=True,
        help_text="Co quyen sua su kien van hanh do minh tao khi chua ghi nhan"
    )
    can_edit_all_operation_events = models.BooleanField(
        default=False,
        help_text="Co quyen sua tat ca su kien van hanh"
    )
    can_delete_own_operation_events = models.BooleanField(
        default=True,
        help_text="Co quyen xoa su kien van hanh do minh tao khi chua khoa"
    )
    can_delete_all_operation_events = models.BooleanField(
        default=False,
        help_text="Co quyen xoa tat ca su kien van hanh"
    )
    can_acknowledge_operation_events = models.BooleanField(
        default=False,
        help_text="Co quyen ghi nhan su kien van hanh"
    )
    can_process_operation_events = models.BooleanField(
        default=False,
        help_text="Co quyen xu ly/khac phuc su kien van hanh"
    )
    can_confirm_operation_events = models.BooleanField(
        default=False,
        help_text="Co quyen xac nhan xu ly su kien van hanh"
    )
    can_add_event_developments = models.BooleanField(
        default=False,
        help_text="Co quyen them dien bien su kien van hanh"
    )
    can_edit_own_event_developments = models.BooleanField(
        default=True,
        help_text="Co quyen sua dien bien su kien do minh tao"
    )
    can_edit_all_event_developments = models.BooleanField(
        default=False,
        help_text="Co quyen sua tat ca dien bien su kien"
    )
    can_edit_own_remediations = models.BooleanField(
        default=True,
        help_text="Co quyen sua noi dung khac phuc do minh tao khi chua xac nhan"
    )
    can_edit_all_remediations = models.BooleanField(
        default=False,
        help_text="Co quyen sua tat ca noi dung khac phuc khi chua xac nhan"
    )

    # Phan quyen nhat ky van hanh - so giao nhan ca
    can_view_shift_handover_logs = models.BooleanField(
        default=True,
        help_text="Co quyen xem so giao nhan ca van hanh"
    )
    can_create_shift_handover_logs = models.BooleanField(
        default=False,
        help_text="Co quyen tao so giao nhan ca van hanh"
    )
    can_receive_shift_handover_logs = models.BooleanField(
        default=False,
        help_text="Co quyen ky nhan ca trong so giao nhan ca van hanh"
    )
    can_edit_shift_handover_logs = models.BooleanField(
        default=False,
        help_text="Co quyen sua so giao nhan ca van hanh"
    )
    can_delete_shift_handover_logs = models.BooleanField(
        default=False,
        help_text="Co quyen xoa so giao nhan ca van hanh"
    )
    can_view_admin_shift_handover_logs = models.BooleanField(
        default=True,
        help_text="Co quyen xem so giao nhan ca hanh chinh"
    )
    can_create_admin_shift_handover_logs = models.BooleanField(
        default=False,
        help_text="Co quyen tao so giao nhan ca hanh chinh"
    )
    can_receive_admin_shift_handover_logs = models.BooleanField(
        default=False,
        help_text="Co quyen ky nhan ca trong so giao nhan ca hanh chinh"
    )
    can_edit_admin_shift_handover_logs = models.BooleanField(
        default=False,
        help_text="Co quyen sua so giao nhan ca hanh chinh"
    )
    can_delete_admin_shift_handover_logs = models.BooleanField(
        default=False,
        help_text="Co quyen xoa so giao nhan ca hanh chinh"
    )
    can_view_operation_logbooks = models.BooleanField(
        default=True,
        help_text="Co quyen xem so nhat ky van hanh"
    )
    can_create_operation_logbooks = models.BooleanField(
        default=False,
        help_text="Co quyen tao so nhat ky van hanh"
    )
    can_confirm_operation_logbooks = models.BooleanField(
        default=False,
        help_text="Co quyen xac nhan so nhat ky van hanh"
    )
    can_edit_operation_logbooks = models.BooleanField(
        default=False,
        help_text="Co quyen sua so nhat ky van hanh"
    )
    can_delete_operation_logbooks = models.BooleanField(
        default=False,
        help_text="Co quyen xoa so nhat ky van hanh"
    )
    can_view_diesel_operation_logbooks = models.BooleanField(
        default=True,
        help_text="Co quyen xem so nhat ky van hanh Diesel"
    )
    can_create_diesel_operation_logbooks = models.BooleanField(
        default=False,
        help_text="Co quyen tao so nhat ky van hanh Diesel"
    )
    can_edit_diesel_operation_logbooks = models.BooleanField(
        default=False,
        help_text="Co quyen sua so nhat ky van hanh Diesel"
    )
    can_delete_diesel_operation_logbooks = models.BooleanField(
        default=False,
        help_text="Co quyen xoa so nhat ky van hanh Diesel"
    )

    # Phan quyen quan ly van hanh - quan ly thiet bi/thong so
    can_view_equipment = models.BooleanField(
        default=True,
        help_text="Co quyen xem danh sach thiet bi van hanh"
    )
    can_create_equipment = models.BooleanField(
        default=False,
        help_text="Co quyen tao thiet bi van hanh"
    )
    can_edit_equipment = models.BooleanField(
        default=False,
        help_text="Co quyen sua thiet bi van hanh"
    )
    can_delete_equipment = models.BooleanField(
        default=False,
        help_text="Co quyen xoa thiet bi van hanh"
    )
    can_view_operation_parameters = models.BooleanField(
        default=True,
        help_text="Co quyen xem thong so van hanh"
    )
    can_create_operation_parameters = models.BooleanField(
        default=False,
        help_text="Co quyen them thong so van hanh"
    )
    can_edit_operation_parameters = models.BooleanField(
        default=False,
        help_text="Co quyen sua thong so van hanh"
    )
    can_delete_operation_parameters = models.BooleanField(
        default=False,
        help_text="Co quyen xoa thong so van hanh"
    )
    can_view_hydrology_data = models.BooleanField(
        default=True,
        help_text="Co quyen xem du lieu thuy van va san xuat"
    )
    can_create_hydrology_data = models.BooleanField(
        default=False,
        help_text="Co quyen them dong bo du lieu thuy van va san xuat"
    )
    can_edit_hydrology_data = models.BooleanField(
        default=False,
        help_text="Co quyen sua du lieu thuy van va san xuat"
    )
    can_delete_hydrology_data = models.BooleanField(
        default=False,
        help_text="Co quyen xoa du lieu thuy van va san xuat"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Hồ sơ người dùng"
        verbose_name_plural = "Hồ sơ người dùng"
        db_table = 'core_user_profile'

    def __str__(self):
        return f"{self.user.email} - {self.user.username}"

    @property
    def full_name(self):
        """Trả về tên đầy đủ của user"""
        if self.ho_ten:
            return self.ho_ten
        elif self.ho and self.ten:
            return f"{self.ho} {self.ten}".strip()
        elif self.ten:
            return self.ten
        else:
            # Use first_name and last_name from User model
            full_name = f"{self.user.first_name} {self.user.last_name}".strip()
            return full_name or self.user.username or self.user.email

    @property
    def avatar_url(self):
        """Trả về URL đầy đủ của avatar"""
        if self.avatar:
            from django.conf import settings
            return f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}{self.avatar.url}"
        return None

    @property
    def chu_ky_url(self):
        """Trả về URL đầy đủ của chữ ký"""
        if self.chu_ky:
            from django.conf import settings
            return f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}{self.chu_ky.url}"
        return None

    def save(self, *args, **kwargs):
        """Override save to sync name with User model"""
        sync_from_user = kwargs.pop('sync_from_user', False)

        # Save the profile first
        super().save(*args, **kwargs)

        if sync_from_user:
            return

        if not self.user_id:
            return

        # Update User model first_name and last_name based on profile fields
        if self.ho_ten:
            # Use ho_ten if available - split into first_name and last_name
            name_parts = self.ho_ten.strip().split(' ', 1)
            if len(name_parts) == 2:
                new_first_name = name_parts[0]
                new_last_name = name_parts[1]
                # Also update ho and ten to match
                self.ho = name_parts[0]
                self.ten = name_parts[1]
            else:
                new_first_name = name_parts[0]
                new_last_name = ""
                self.ho = name_parts[0]
                self.ten = ""
        elif self.ho and self.ten:
            # Use ho + ten if available
            new_first_name = self.ho
            new_last_name = self.ten
        elif self.ten:
            # Use ten if available
            new_first_name = ""
            new_last_name = self.ten
        else:
            new_first_name = self.user.first_name
            new_last_name = self.user.last_name

        update_fields = []
        if self.user.first_name != new_first_name:
            self.user.first_name = new_first_name
            update_fields.append('first_name')
        if self.user.last_name != new_last_name:
            self.user.last_name = new_last_name
            update_fields.append('last_name')

        if not update_fields:
            return

        # Save the user model without triggering UserProfile sync
        if self.user.pk:
            self.user.save(sync_from_profile=True, update_fields=update_fields)
        else:
            self.user.save(sync_from_profile=True)
