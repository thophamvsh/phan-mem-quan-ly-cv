from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse

from .models import User, UserProfile
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserProfileSerializer
)

def health_check(request):
    return JsonResponse({"status": "ok"})


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
            errors = serializer.errors
            error_message = (
                errors.get('non_field_errors', [None])[0]
                or errors.get('username', [None])[0]
                or errors.get('email', [None])[0]
                or errors.get('password', [None])[0]
                or 'Đăng nhập thất bại'
            )
            return Response({
                'ok': False,
                'message': str(error_message),
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)


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
                'success': True,
                'message': 'Đăng xuất thành công'
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Đăng xuất thất bại',
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordAPIView(APIView):
    """API đổi mật khẩu"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
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

            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            
            # Validate new password using system validators
            try:
                validate_password(new_password, request.user)
            except ValidationError as e:
                return Response({
                    'success': False,
                    'message': 'Mật khẩu không đạt yêu cầu bảo mật',
                    'errors': list(e.messages)
                }, status=status.HTTP_400_BAD_REQUEST)

            # Set new password
            request.user.set_password(new_password)
            request.user.save()

            return Response({
                'success': True,
                'message': 'Đổi mật khẩu thành công'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': 'Đổi mật khẩu thất bại',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
