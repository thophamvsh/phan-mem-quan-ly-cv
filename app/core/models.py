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
        # Save the user first
        super().save(*args, **kwargs)

        # Update UserProfile if it exists
        try:
            profile = self.profile
            # Update profile fields based on User model first_name and last_name
            if self.first_name and self.last_name:
                # Update ho_ten with combined name
                profile.ho_ten = f"{self.first_name} {self.last_name}".strip()
                # Update ho and ten
                profile.ho = self.first_name
                profile.ten = self.last_name
            elif self.first_name:
                # Only first_name provided
                profile.ho_ten = self.first_name
                profile.ho = self.first_name
                profile.ten = ""
            elif self.last_name:
                # Only last_name provided
                profile.ho_ten = self.last_name
                profile.ho = ""
                profile.ten = self.last_name

            # Save the profile without triggering User save again
            profile.save(update_fields=['ho_ten', 'ho', 'ten', 'updated_at'])
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
        # Save the profile first
        super().save(*args, **kwargs)

        # Check if this is a sync from User model (to avoid infinite loop)
        if kwargs.get('update_fields'):
            # This is a sync from User model, don't sync back
            return

        # Update User model first_name and last_name based on profile fields
        if self.ho_ten:
            # Use ho_ten if available - split into first_name and last_name
            name_parts = self.ho_ten.strip().split(' ', 1)
            if len(name_parts) == 2:
                self.user.first_name = name_parts[0]
                self.user.last_name = name_parts[1]
                # Also update ho and ten to match
                self.ho = name_parts[0]
                self.ten = name_parts[1]
            else:
                self.user.first_name = name_parts[0]
                self.user.last_name = ""
                self.ho = name_parts[0]
                self.ten = ""
        elif self.ho and self.ten:
            # Use ho + ten if available
            self.user.first_name = self.ho
            self.user.last_name = self.ten
        elif self.ten:
            # Use ten if available
            self.user.first_name = ""
            self.user.last_name = self.ten

        # Save the user model without triggering UserProfile sync
        self.user.save(update_fields=['first_name', 'last_name'])


