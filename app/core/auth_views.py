from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.http import JsonResponse
from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from .models import User, UserProfile
from .auth_cookies import delete_refresh_cookie, set_refresh_cookie
from .throttles import LoginRateThrottle, RegistrationRateThrottle, TokenRateThrottle
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserProfileSerializer
)

def health_check(request):
    return JsonResponse({"status": "ok"})


def _serialize_login_user(user, request):
    try:
        return UserProfileSerializer(
            user.profile,
            context={'request': request},
        ).data
    except UserProfile.DoesNotExist:
        return UserSerializer(user).data


def _send_login_signal(request, user):
    from django.contrib.auth.signals import user_logged_in
    user_logged_in.send(sender=user.__class__, request=request, user=user)


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CSRFTokenAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({'csrfToken': get_token(request)})


@method_decorator(csrf_protect, name='dispatch')
class SecureUserLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if not serializer.is_valid():
            errors = serializer.errors
            error_message = (
                errors.get('non_field_errors', [None])[0]
                or errors.get('username', [None])[0]
                or errors.get('email', [None])[0]
                or errors.get('password', [None])[0]
                or 'Đăng nhập thất bại'
            )
            return Response({
                'success': False,
                'message': str(error_message),
                'errors': errors,
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        _send_login_signal(request, user)
        response = Response({
            'success': True,
            'message': 'Đăng nhập thành công',
            'access': str(refresh.access_token),
            'user': _serialize_login_user(user, request),
        }, status=status.HTTP_200_OK)
        return set_refresh_cookie(response, str(refresh))


@method_decorator(csrf_protect, name='dispatch')
class SecureTokenRefreshAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [TokenRateThrottle]

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token cookie is required.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = TokenRefreshSerializer(data={'refresh': refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            response = Response(
                {'detail': 'Refresh token is invalid or expired.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            return delete_refresh_cookie(response)

        token_data = serializer.validated_data
        response = Response(
            {'access': token_data['access']},
            status=status.HTTP_200_OK,
        )
        rotated_refresh = token_data.get('refresh')
        if rotated_refresh:
            set_refresh_cookie(response, rotated_refresh)
        return response


@method_decorator(csrf_protect, name='dispatch')
class SecureUserLogoutAPIView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [TokenRateThrottle]

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_NAME)
        logout_user = None
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                logout_user = User.objects.filter(
                    id=token.get(settings.SIMPLE_JWT['USER_ID_CLAIM']),
                ).first()
                token.blacklist()
            except TokenError:
                pass

        if logout_user:
            from django.contrib.auth.signals import user_logged_out
            user_logged_out.send(
                sender=logout_user.__class__,
                request=request,
                user=logout_user,
            )

        response = Response({
            'success': True,
            'message': 'Đăng xuất thành công',
        }, status=status.HTTP_200_OK)
        return delete_refresh_cookie(response)


class UserRegistrationAPIView(APIView):
    """API đăng ký user mới"""
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegistrationRateThrottle]

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
    throttle_classes = [LoginRateThrottle]

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

            # Trigger login signal manually for JWT login
            from django.contrib.auth.signals import user_logged_in
            user_logged_in.send(sender=user.__class__, request=request, user=user)

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
            # Trigger logout signal manually
            from django.contrib.auth.signals import user_logged_out
            user_logged_out.send(sender=request.user.__class__, request=request, user=request.user)

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
