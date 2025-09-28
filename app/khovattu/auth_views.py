# apps/khovattu/auth_views.py
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import os
import uuid
from .serializers import UserLoginSerializer, UserProfileSerializer
from core.models import UserProfile


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view that returns user profile along with tokens
    """
    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            # Get user profile
            try:
                profile = user.profile
                profile_serializer = UserProfileSerializer(profile)
                user_data = profile_serializer.data
            except UserProfile.DoesNotExist:
                # Fallback if profile doesn't exist
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                    'phone': '',
                    'nha_may': None,
                    'nha_may_name': None,
                    'is_mobile_user': True,
                    'date_joined': user.date_joined,
                    'created_at': None,
                    'updated_at': None
                }

            return Response({
                'success': True,
                'message': 'Đăng nhập thành công',
                'tokens': {
                    'access': str(access_token),
                    'refresh': str(refresh),
                },
                'user': user_data
            }, status=status.HTTP_200_OK)
        else:
            # Extract specific error message from serializer errors
            error_message = 'Đăng nhập thất bại'
            if serializer.errors:
                # Check for non_field_errors first
                if 'non_field_errors' in serializer.errors:
                    non_field_errors = serializer.errors['non_field_errors']
                    if non_field_errors and len(non_field_errors) > 0:
                        error_message = str(non_field_errors[0])
                # Check for specific field errors
                elif 'username' in serializer.errors:
                    error_message = str(serializer.errors['username'][0])
                elif 'password' in serializer.errors:
                    error_message = str(serializer.errors['password'][0])
                # Get first available error message
                else:
                    for field, errors in serializer.errors.items():
                        if errors and len(errors) > 0:
                            error_message = str(errors[0])
                            break

            return Response({
                'success': False,
                'message': error_message,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)


# register_user function removed - registration only through Django admin


@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Temporarily allow for testing
def get_user_profile(request):
    """
    Get current user profile
    GET /api/khovattu/auth/profile/
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = UserProfile.objects.create(
            user=request.user,
            is_mobile_user=True
        )

    serializer = UserProfileSerializer(profile)
    return Response({
        'success': True,
        'user': serializer.data
    })


@api_view(['PUT'])
@permission_classes([permissions.AllowAny])  # Temporarily allow for testing
def update_user_profile(request):
    """
    Update current user profile
    PUT /api/khovattu/auth/profile/
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = UserProfile.objects.create(
            user=request.user,
            is_mobile_user=True
        )

    serializer = UserProfileSerializer(profile, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({
            'success': True,
            'message': 'Cập nhật thông tin thành công',
            'user': serializer.data
        })
    else:
        return Response({
            'success': False,
            'message': 'Cập nhật thất bại',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_nha_may_list(request):
    """
    Get list of factories for registration
    GET /api/khovattu/auth/nha-may/
    """
    from .models import Bang_nha_may
    from .serializers import NhaMaySerializer

    nha_mays = Bang_nha_may.objects.all()
    serializer = NhaMaySerializer(nha_mays, many=True)
    return Response({
        'success': True,
        'nha_mays': serializer.data
    })


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Temporarily allow for testing
def change_password(request):
    """
    Change user password
    POST /api/khovattu/auth/change-password/
    """
    try:
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        # Validate input
        if not old_password or not new_password or not confirm_password:
            return Response({
                'success': False,
                'message': 'Vui lòng nhập đầy đủ thông tin'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if new password matches confirmation
        if new_password != confirm_password:
            return Response({
                'success': False,
                'message': 'Mật khẩu mới và xác nhận mật khẩu không khớp'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check if new password is different from old password
        if old_password == new_password:
            return Response({
                'success': False,
                'message': 'Mật khẩu mới phải khác mật khẩu cũ'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate old password
        if not request.user.check_password(old_password):
            return Response({
                'success': False,
                'message': 'Mật khẩu cũ không đúng'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate new password length
        if len(new_password) < 6:
            return Response({
                'success': False,
                'message': 'Mật khẩu mới phải có ít nhất 6 ký tự'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Set new password
        request.user.set_password(new_password)
        request.user.save()

        return Response({
            'success': True,
            'message': 'Đổi mật khẩu thành công'
        })

    except Exception as e:
        return Response({
            'success': False,
            'message': 'Đổi mật khẩu thất bại',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Temporarily allow for testing
def logout_user(request):
    """
    Logout user by blacklisting the refresh token
    POST /api/khovattu/auth/logout/
    """
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({
                'success': True,
                'message': 'Đăng xuất thành công'
            })
        else:
            return Response({
                'success': False,
                'message': 'Refresh token không được cung cấp'
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': 'Đăng xuất thất bại',
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Temporarily allow for testing
def upload_avatar(request):
    """
    Upload user avatar
    """
    try:
        if 'avatar' not in request.FILES:
            return Response({
                'success': False,
                'message': 'Không có file hình ảnh được gửi'
            }, status=status.HTTP_400_BAD_REQUEST)

        avatar_file = request.FILES['avatar']

        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if avatar_file.content_type not in allowed_types:
            return Response({
                'success': False,
                'message': 'Chỉ chấp nhận file JPG, JPEG, PNG'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size (max 5MB)
        if avatar_file.size > 5 * 1024 * 1024:
            return Response({
                'success': False,
                'message': 'Kích thước file không được vượt quá 5MB'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate unique filename
        file_extension = avatar_file.name.split('.')[-1]
        unique_filename = f"avatar_{request.user.id}_{uuid.uuid4().hex[:8]}.{file_extension}"

        # Save file
        file_path = default_storage.save(f"avatars/{unique_filename}", avatar_file)

        # Get or create user profile
        user_profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'phone': '', 'nha_may_id': 1}
        )

        # Update avatar
        user_profile.avatar = file_path
        user_profile.save()

        # Get full URL
        avatar_url = request.build_absolute_uri(default_storage.url(file_path))

        return Response({
            'success': True,
            'message': 'Cập nhật hình ảnh thành công',
            'avatar_url': avatar_url
        })

    except Exception as e:
        return Response({
            'success': False,
            'message': 'Có lỗi xảy ra khi cập nhật hình ảnh',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
