from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.files.storage import default_storage
import uuid
import time
from .models import User, UserProfile
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserProfileSerializer
)


class UserRegistrationAPIView(APIView):
    """API đăng ký user mới"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'ok': True,
                'message': 'Đăng ký thành công',
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'ok': False,
                'message': 'Đăng ký thất bại',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)


class UserLoginAPIView(APIView):
    """API đăng nhập cho user"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # Tạo JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            # Get user profile for complete data
            try:
                user_profile = user.profile
                user_data = UserProfileSerializer(user_profile, context={'request': request}).data
            except:
                # Fallback to UserSerializer if profile doesn't exist
                user_data = UserSerializer(user).data

            return Response({
                'success': True,
                'message': 'Đăng nhập thành công',
                'tokens': {
                    'access': str(access_token),
                    'refresh': str(refresh)
                },
                'user': user_data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'ok': False,
                'message': 'Đăng nhập thất bại',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileAPIView(APIView):
    """API để lấy và cập nhật thông tin profile của user hiện tại"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Lấy thông tin profile của user hiện tại"""
        try:
            serializer = UserProfileSerializer(request.user)
            return Response({
                "ok": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi lấy thông tin profile: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        """Cập nhật thông tin profile của user hiện tại"""
        try:
            serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "ok": True,
                    "message": "Cập nhật profile thành công",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "ok": False,
                    "error": "Dữ liệu không hợp lệ",
                    "details": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi cập nhật profile: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserLogoutAPIView(APIView):
    """API đăng xuất"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Blacklist refresh token
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            return Response({
                'ok': True,
                'message': 'Đăng xuất thành công'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'ok': False,
                'error': f'Lỗi đăng xuất: {str(e)}'
            }, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordAPIView(APIView):
    """API đổi mật khẩu"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            old_password = request.data.get('old_password')
            new_password = request.data.get('new_password')

            if not old_password or not new_password:
                return Response({
                    'ok': False,
                    'error': 'Vui lòng nhập mật khẩu cũ và mật khẩu mới'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not user.check_password(old_password):
                return Response({
                    'ok': False,
                    'error': 'Mật khẩu cũ không đúng'
                }, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(new_password)
            user.save()

            return Response({
                'ok': True,
                'message': 'Đổi mật khẩu thành công'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'ok': False,
                'error': f'Lỗi đổi mật khẩu: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserListAPIView(APIView):
    """API lấy danh sách user (chỉ admin)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Chỉ admin mới có thể xem danh sách user
            if not request.user.is_staff:
                return Response({
                    'ok': False,
                    'error': 'Không có quyền truy cập'
                }, status=status.HTTP_403_FORBIDDEN)

            users = User.objects.all()
            serializer = UserSerializer(users, many=True)
            return Response({
                'ok': True,
                'data': serializer.data,
                'count': users.count()
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'ok': False,
                'error': f'Lỗi lấy danh sách user: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===================== USER PROFILE APIs (giống kho vật tư) =====================

@api_view(['GET'])
@permission_classes([permissions.AllowAny])  # Temporarily allow for testing
def get_user_profile(request):
    """
    Get current user profile
    GET /api/core/auth/profile/
    """
    try:
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'is_mobile_user': True}
        )
        serializer = UserProfileSerializer(profile, context={'request': request})

        # Add cache-busting headers and timestamp
        response = Response({
            'success': True,
            'user': serializer.data,
            'timestamp': profile.updated_at.isoformat() if profile.updated_at else None,
            'cache_bust': int(time.time() * 1000)  # Current timestamp in milliseconds
        })

        # Add cache-busting headers
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        return response
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Lỗi lấy thông tin profile: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([permissions.AllowAny])  # Temporarily allow for testing
def update_user_profile(request):
    """
    Update current user profile
    PUT /api/core/auth/profile/update/
    """
    try:
        profile, created = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'is_mobile_user': True}
        )
        serializer = UserProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()

            # Add cache-busting headers and timestamp
            response = Response({
                'success': True,
                'message': 'Cập nhật thông tin thành công',
                'user': serializer.data,
                'timestamp': profile.updated_at.isoformat() if profile.updated_at else None,
                'cache_bust': int(time.time() * 1000)  # Current timestamp in milliseconds
            })

            # Add cache-busting headers
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

            return response
        else:
            return Response({
                'success': False,
                'message': 'Cập nhật thất bại',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Lỗi cập nhật profile: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])  # Temporarily allow for testing
def change_password(request):
    """
    Change user password
    POST /api/core/auth/change-password/
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

        # Validate new password length (đơn giản hơn)
        if len(new_password) < 4:
            return Response({
                'success': False,
                'message': 'Mật khẩu mới phải có ít nhất 4 ký tự'
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
    POST /api/core/auth/logout/
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
    POST /api/core/auth/upload-avatar/
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
            defaults={'is_mobile_user': True}
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
