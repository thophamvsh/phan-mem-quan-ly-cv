from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from . import views

urlpatterns = [
    # Authentication URLs
    path('auth/register/', views.UserRegistrationAPIView.as_view(), name='user-register'),
    path('auth/login/', views.UserLoginAPIView.as_view(), name='user-login'),
    path('auth/logout/', views.UserLogoutAPIView.as_view(), name='user-logout'),

    # JWT Token URLs
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # User Profile URLs
    path('profile/', views.UserProfileAPIView.as_view(), name='user-profile'),
    path('users/', views.UserListAPIView.as_view(), name='user-list'),

    # ===== NEW PROFILE APIs (giống kho vật tư) =====
    path('auth/profile/', views.get_user_profile, name='get_user_profile'),
    path('auth/profile/update/', views.update_user_profile, name='update_user_profile'),
    path('auth/change-password/', views.change_password, name='change_password'),
    path('auth/upload-avatar/', views.upload_avatar, name='upload_avatar'),
    path('auth/logout/', views.logout_user, name='logout_user'),

    # ===== KHOVATTU COMPATIBILITY URLs (cho VshProject) =====
    path('khovattu/auth/login/', views.UserLoginAPIView.as_view(), name='khovattu-login'),
    path('khovattu/auth/token/', TokenObtainPairView.as_view(), name='khovattu-token'),
    path('khovattu/auth/token/refresh/', TokenRefreshView.as_view(), name='khovattu-token-refresh'),
    path('khovattu/auth/token/verify/', TokenVerifyView.as_view(), name='khovattu-token-verify'),
    path('khovattu/auth/profile/', views.get_user_profile, name='khovattu-profile'),
    path('khovattu/auth/profile/update/', views.update_user_profile, name='khovattu-profile-update'),
    path('khovattu/auth/change-password/', views.change_password, name='khovattu-change-password'),
    path('khovattu/auth/upload-avatar/', views.upload_avatar, name='khovattu-upload-avatar'),
    path('khovattu/auth/logout/', views.logout_user, name='khovattu-logout'),
]
