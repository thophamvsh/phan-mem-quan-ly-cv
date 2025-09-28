# apps/kho/serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from core.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Bang_nha_may, Bang_hinh_anh_vat_tu, Bang_xuat_xu
from core.models import UserProfile


# ===== USER PROFILE SERIALIZERS =====

# UserRegistrationSerializer removed - registration only through Django admin


class UserLoginSerializer(serializers.Serializer):
    """Serializer cho đăng nhập"""
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            # Try to authenticate with username first
            user = authenticate(username=username, password=password)

            # If failed, try with email
            if not user:
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass

            if not user:
                raise serializers.ValidationError('Email/username hoặc mật khẩu không đúng.')
            if not user.is_active:
                raise serializers.ValidationError('Tài khoản đã bị vô hiệu hóa.')

            # Check if user has profile and is mobile user
            try:
                profile = user.profile
                if not profile.is_mobile_user:
                    raise serializers.ValidationError('Tài khoản không được phép đăng nhập từ mobile app.')
            except:
                # Allow login even without profile - will create default profile data
                pass

            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Vui lòng nhập tên đăng nhập và mật khẩu.')


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer cho thông tin user profile"""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    full_name = serializers.CharField(read_only=True)
    nha_may_name = serializers.CharField(read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    avatar_url = serializers.SerializerMethodField()
    chu_ky_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            else:
                from django.conf import settings
                return f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{obj.avatar.url}"
        return None

    def get_chu_ky_url(self, obj):
        if obj.chu_ky:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.chu_ky.url)
            else:
                from django.conf import settings
                return f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{obj.chu_ky.url}"
        return None

    class Meta:
        model = UserProfile
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'full_name',
                 'phone', 'nha_may', 'nha_may_name', 'is_mobile_user', 'avatar', 'avatar_url',
                 'chuc_danh', 'chu_ky', 'chu_ky_url', 'date_joined', 'created_at', 'updated_at')
        read_only_fields = ('id', 'username', 'email', 'full_name',
                           'nha_may_name', 'date_joined', 'created_at', 'updated_at')

    def update(self, instance, validated_data):
        """Override update method to handle user fields"""
        # Extract user data
        user_data = {}
        if 'user' in validated_data:
            user_data = validated_data.pop('user')

        # Update user fields if provided
        if user_data:
            user = instance.user
            if 'first_name' in user_data:
                user.first_name = user_data['first_name']
            if 'last_name' in user_data:
                user.last_name = user_data['last_name']
            user.save()

        # Update profile fields
        return super().update(instance, validated_data)


class NhaMaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Bang_nha_may
        fields = ('id', 'ma_nha_may', 'ten_nha_may')


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


# Import các model cần thiết
from .models import Bang_vi_tri, Bang_vat_tu, Bang_de_nghi_nhap, Bang_de_nghi_xuat, Bang_hinh_anh_vat_tu


class ViTriSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bang_vi_tri
        fields = '__all__'


class VatTuImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        from django.conf import settings
        if obj.hinh_anh:
            return f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{obj.hinh_anh.url}"
        return None

    class Meta:
        model = Bang_hinh_anh_vat_tu
        fields = ['id', 'hinh_anh', 'image_url', 'mo_ta', 'thu_tu', 'is_active', 'created_at', 'updated_at']


class VatTuSerializer(serializers.ModelSerializer):
    nha_may = serializers.CharField(source='bang_nha_may.ma_nha_may', read_only=True)
    ten_nha_may = serializers.CharField(source='bang_nha_may.ten_nha_may', read_only=True)
    vi_tri = serializers.SerializerMethodField()
    xuat_xu = serializers.SerializerMethodField()
    qr_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    additional_images = VatTuImageSerializer(many=True, read_only=True, source='hinh_anh_list')
    all_images = serializers.SerializerMethodField()

    def get_vi_tri(self, obj):
        try:
            if obj.ma_vi_tri:
                return {
                    'ma_vi_tri': obj.ma_vi_tri.ma_vi_tri,
                    'ma_he_thong': obj.ma_vi_tri.ma_he_thong,
                    'ten_he_thong': obj.ma_vi_tri.ma_he_thong,  # Use ma_he_thong as ten_he_thong
                    'kho': obj.ma_vi_tri.kho,
                    'ke': obj.ma_vi_tri.ke,
                    'ngan': obj.ma_vi_tri.ngan,
                    'tang': obj.ma_vi_tri.tang,
                    'mo_ta': obj.ma_vi_tri.mo_ta,
                }
        except Exception as e:
            pass
        return None

    def get_xuat_xu(self, obj):
        try:
            if obj.xuat_xu:
                return {
                    'ma_country': obj.xuat_xu.ma_country,
                    'ten_nuoc': obj.xuat_xu.ten_nuoc,
                    'ten_viet_tat': obj.xuat_xu.ten_viet_tat,
                    'ten_hien_thi': obj.xuat_xu.ten_viet_tat or obj.xuat_xu.ten_nuoc,  # Ưu tiên tên tiếng Việt
                }
        except Exception as e:
            pass
        return None

    def get_qr_url(self, obj):
        from django.conf import settings
        if obj.ma_QR:
            return f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{obj.ma_QR.url}"
        return None

    def get_image_url(self, obj):
        from django.conf import settings
        if obj.hinh_anh_vt:
            return f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{obj.hinh_anh_vt.url}"
        return None

    def get_all_images(self, obj):
        """
        Trả về tất cả hình ảnh của vật tư (hình chính + hình bổ sung)
        """
        from django.conf import settings
        images = []

        # Thêm hình ảnh chính nếu có
        if obj.hinh_anh_vt:
            images.append({
                'id': 'main',
                'image_url': f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{obj.hinh_anh_vt.url}",
                'mo_ta': 'Hình ảnh chính',
                'is_main': True,
                'created_at': None,
                'updated_at': None
            })

        # Thêm các hình ảnh bổ sung
        for img in obj.hinh_anh_list.filter(is_active=True):
            images.append({
                'id': img.id,
                'image_url': f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{img.hinh_anh.url}",
                'mo_ta': img.mo_ta or '',
                'is_main': False,
                'created_at': img.created_at,
                'updated_at': img.updated_at
            })

        return images

    class Meta:
        model = Bang_vat_tu
        fields = '__all__'


class VatTuUpsertSerializer(serializers.ModelSerializer):
    ma_nha_may = serializers.CharField(write_only=True, required=False)

    def validate_ma_nha_may(self, value):
        """Convert ma_nha_may string to bang_nha_may object"""
        if value:
            try:
                from .models import Bang_nha_may
                bang_nha_may = Bang_nha_may.objects.get(ma_nha_may=value.strip())
                return bang_nha_may
            except Bang_nha_may.DoesNotExist:
                raise serializers.ValidationError(f"Nhà máy với mã '{value}' không tồn tại")
        return None

    def validate(self, data):
        """Handle ma_nha_may conversion after validation"""
        ma_nha_may = data.get('ma_nha_may')
        if ma_nha_may:
            # Convert ma_nha_may to bang_nha_may object
            data['bang_nha_may'] = ma_nha_may
        # Always remove ma_nha_may from data as it's not a model field
        data.pop('ma_nha_may', None)
        return data

    class Meta:
        model = Bang_vat_tu
        fields = ['ten_vat_tu', 'don_vi', 'thong_so_ky_thuat', 'ton_kho', 'so_luong_kh',
                 'ma_vi_tri', 'bang_nha_may', 'hinh_anh_vt', 'ma_nha_may']


class DeNghiNhapSerializer(serializers.ModelSerializer):
    nha_may = serializers.CharField(source='vat_tu.bang_nha_may.ma_nha_may', read_only=True)
    ten_nha_may = serializers.CharField(source='vat_tu.bang_nha_may.ten_nha_may', read_only=True)

    class Meta:
        model = Bang_de_nghi_nhap
        fields = '__all__'


class DeNghiNhapPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bang_de_nghi_nhap
        fields = '__all__'


class DeNghiXuatSerializer(serializers.ModelSerializer):
    nha_may = serializers.CharField(source='vat_tu.bang_nha_may.ma_nha_may', read_only=True)
    ten_nha_may = serializers.CharField(source='vat_tu.bang_nha_may.ten_nha_may', read_only=True)

    class Meta:
        model = Bang_de_nghi_xuat
        fields = '__all__'


class DeNghiXuatPatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bang_de_nghi_xuat
        fields = '__all__'


class NhapSerializer(serializers.Serializer):
    pass


class XuatSerializer(serializers.Serializer):
    ma_nha_may = serializers.CharField()
    ma_bravo = serializers.CharField()
    so_luong = serializers.IntegerField()
    ngay = serializers.DateTimeField(required=False)
    ghi_chu = serializers.CharField(required=False, allow_blank=True)


# ===== XUẤT XỨ SERIALIZERS =====

class XuatXuSerializer(serializers.ModelSerializer):
    """Serializer cho xuất xứ"""
    class Meta:
        model = Bang_xuat_xu
        fields = ['ma_country', 'ten_nuoc', 'ten_viet_tat', 'mo_ta']