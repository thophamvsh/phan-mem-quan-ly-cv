from rest_framework import serializers
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import User, UserProfile


def simple_password_validator(value):
    """Custom password validator - chỉ yêu cầu tối thiểu 4 ký tự"""
    if len(value) < 4:
        raise ValidationError("Mật khẩu phải có ít nhất 4 ký tự.")
    return value


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer cho đăng ký user mới"""
    password = serializers.CharField(write_only=True, validators=[simple_password_validator])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('email', 'password', 'password_confirm', 'first_name', 'last_name')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Mật khẩu không khớp.")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer cho đăng nhập - hỗ trợ cả username và email"""
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False)
    password = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get('email')
        username = attrs.get('username')
        password = attrs.get('password')

        # Hỗ trợ cả email và username
        if email:
            user = authenticate(email=email, password=password)
            login_field = 'email'
        elif username:
            # Nếu username là email format, sử dụng email authentication
            if '@' in username:
                user = authenticate(email=username, password=password)
                login_field = 'email'
            else:
                # Nếu không phải email, tìm user theo username field
                try:
                    user = User.objects.get(username=username)
                    if user.check_password(password):
                        pass  # User found and password correct
                    else:
                        user = None
                except User.DoesNotExist:
                    user = None
                login_field = 'username'
        else:
            raise serializers.ValidationError('Vui lòng nhập email/username và mật khẩu.')

        if not user:
            raise serializers.ValidationError('Email/username hoặc mật khẩu không đúng.')
        if not user.is_active:
            raise serializers.ValidationError('Tài khoản đã bị vô hiệu hóa.')

        attrs['user'] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """Serializer cho thông tin user với thông tin từ profile"""
    username = serializers.CharField(read_only=True)
    full_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    chuc_danh = serializers.SerializerMethodField()
    nha_may = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    is_all_factories = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'full_name', 'avatar', 'avatar_url', 'phone', 'chuc_danh', 'nha_may', 'nha_may_name', 'is_all_factories', 'is_active', 'is_staff', 'is_superuser', 'last_login')
        read_only_fields = ('id', 'email', 'username', 'is_active', 'is_staff', 'is_superuser', 'last_login')

    def get_full_name(self, obj):
        """Lấy full_name từ UserProfile"""
        try:
            profile = obj.profile
            return profile.full_name
        except:
            return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_avatar(self, obj):
        """Lấy avatar path từ UserProfile"""
        try:
            profile = obj.profile
            return profile.avatar.url if profile.avatar else None
        except:
            return None

    def get_avatar_url(self, obj):
        """Lấy avatar URL từ UserProfile"""
        try:
            profile = obj.profile
            return profile.avatar_url
        except:
            return None

    def get_phone(self, obj):
        """Lấy phone từ UserProfile"""
        try:
            profile = obj.profile
            return profile.phone
        except:
            return None

    def get_chuc_danh(self, obj):
        """Lấy chuc_danh từ UserProfile"""
        try:
            profile = obj.profile
            return profile.chuc_danh
        except:
            return None

    def get_nha_may(self, obj):
        """Lấy nha_may ID từ UserProfile"""
        try:
            profile = obj.profile
            return profile.nha_may.id if profile.nha_may else None
        except:
            return None

    def get_nha_may_name(self, obj):
        """Lấy tên nhà máy từ UserProfile"""
        try:
            profile = obj.profile
            return f"{profile.nha_may.ma_nha_may} - {profile.nha_may.ten_nha_may}" if profile.nha_may else None
        except:
            return None

    def get_is_all_factories(self, obj):
        """Lấy is_all_factories từ UserProfile"""
        try:
            profile = obj.profile
            return profile.is_all_factories
        except:
            return False


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer cho thông tin user profile giống kho vật tư"""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    full_name = serializers.CharField(read_only=True)
    ho_ten = serializers.CharField(required=False, help_text="Họ và tên đầy đủ")
    ho = serializers.CharField(required=False, help_text="Họ")
    ten = serializers.CharField(required=False, help_text="Tên")
    avatar_url = serializers.SerializerMethodField()
    chu_ky_url = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    # date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)  # Not available in custom User model

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            else:
                from django.conf import settings
                return f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}{obj.avatar.url}"
        return None

    def get_chu_ky_url(self, obj):
        if obj.chu_ky:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.chu_ky.url)
            else:
                from django.conf import settings
                return f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}{obj.chu_ky.url}"
        return None

    def get_nha_may_name(self, obj):
        """Lấy tên nhà máy"""
        if obj.nha_may:
            return f"{obj.nha_may.ma_nha_may} - {obj.nha_may.ten_nha_may}"
        return None

    class Meta:
        model = UserProfile
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'ho_ten', 'ho', 'ten', 'phone', 'is_mobile_user',
                 'avatar', 'avatar_url', 'chuc_danh', 'chu_ky', 'chu_ky_url', 'nha_may', 'nha_may_name', 'is_all_factories',
                 'created_at', 'updated_at')
        read_only_fields = ('id', 'username', 'email', 'full_name', 'avatar_url', 'chu_ky_url',
                           'created_at', 'updated_at')

    def update(self, instance, validated_data):
        """Override update method to handle user fields and first_name/last_name mapping"""
        # Handle user data (from source='user' fields) - for VshProject
        user_data = validated_data.pop('user', {})
        first_name_from_user = user_data.get('first_name')
        last_name_from_user = user_data.get('last_name')

        # Handle direct first_name/last_name fields - for VshMobile
        first_name_direct = validated_data.pop('first_name', None)
        last_name_direct = validated_data.pop('last_name', None)

        # Use direct fields if available (VshMobile), otherwise use user fields (VshProject)
        first_name = first_name_direct if first_name_direct is not None else first_name_from_user
        last_name = last_name_direct if last_name_direct is not None else last_name_from_user

        if first_name is not None or last_name is not None:
            # Update User model fields
            if first_name is not None:
                instance.user.first_name = first_name
            if last_name is not None:
                instance.user.last_name = last_name
            instance.user.save(update_fields=['first_name', 'last_name'])

            # Update Profile fields to match
            if first_name is not None:
                instance.ho = first_name
            if last_name is not None:
                instance.ten = last_name

            # Update ho_ten
            if first_name is not None and last_name is not None:
                instance.ho_ten = f"{first_name} {last_name}"
            elif first_name is not None:
                instance.ho_ten = first_name
            elif last_name is not None:
                instance.ho_ten = last_name

        # Update other profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Save profile (this will trigger sync in UserProfile.save())
        instance.save()

        return instance


class UserSerializer(serializers.ModelSerializer):
    """Serializer cho thông tin user cơ bản"""
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'last_login')
        read_only_fields = ('id', 'email', 'is_active', 'is_staff', 'is_superuser', 'last_login')
