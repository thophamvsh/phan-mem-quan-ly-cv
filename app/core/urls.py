from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from . import auth_views
from . import profile_views
from . import upload_views

urlpatterns = [
    # ===== Public endpoints =====
    path('auth/register/', auth_views.UserRegistrationAPIView.as_view(), name='user-register'),
    path('auth/login/', auth_views.UserLoginAPIView.as_view(), name='user-login'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # ===== Private endpoints (require authentication in view permissions) =====
    path('profile/', profile_views.UserProfileAPIView.as_view(), name='user-profile'),
    path('users/', profile_views.UserListAPIView.as_view(), name='user-list'),
    
    path('auth/profile/', profile_views.UserProfileAPIView.as_view(), name='get_user_profile'),
    path('auth/profile/update/', profile_views.UserProfileAPIView.as_view(), name='update_user_profile'),
    path('auth/change-password/', auth_views.ChangePasswordAPIView.as_view(), name='change_password'),
    path('auth/upload-avatar/', upload_views.UploadAvatarAPIView.as_view(), name='upload_avatar'),
    path('auth/upload-signature/', upload_views.UploadSignatureAPIView.as_view(), name='upload_signature'),
    path('auth/logout/', auth_views.UserLogoutAPIView.as_view(), name='logout_user'),

    # ===== KHOVATTU compatibility endpoints =====
    path('khovattu/auth/login/', auth_views.UserLoginAPIView.as_view(), name='khovattu-login'),
    path('khovattu/auth/token/', TokenObtainPairView.as_view(), name='khovattu-token'),
    path('khovattu/auth/token/refresh/', TokenRefreshView.as_view(), name='khovattu-token-refresh'),
    path('khovattu/auth/token/verify/', TokenVerifyView.as_view(), name='khovattu-token-verify'),
    path('khovattu/auth/profile/', profile_views.UserProfileAPIView.as_view(), name='khovattu-profile'),
    path('khovattu/auth/profile/update/', profile_views.UserProfileAPIView.as_view(), name='khovattu-profile-update'),
    path('khovattu/auth/change-password/', auth_views.ChangePasswordAPIView.as_view(), name='khovattu-change-password'),
    path('khovattu/auth/upload-avatar/', upload_views.UploadAvatarAPIView.as_view(), name='khovattu-upload-avatar'),
    path('khovattu/auth/upload-signature/', upload_views.UploadSignatureAPIView.as_view(), name='khovattu-upload-signature'),
    path('khovattu/auth/logout/', auth_views.UserLogoutAPIView.as_view(), name='khovattu-logout'),
]
