"""Session generation invalidates access, refresh and Django sessions on lock."""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User


class AccountRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token['session_version'] = user.session_version
        return token


class AccountJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if validated_token.get('session_version', 0) != user.session_version:
            raise AuthenticationFailed('Phiên đăng nhập đã bị thu hồi.')
        profile = getattr(user, 'profile', None)
        if profile:
            profile.apply_role_permissions()
        return user


class AccountTokenObtainPairSerializer(TokenObtainPairSerializer):
    token_class = AccountRefreshToken


class AccountTokenRefreshSerializer(TokenRefreshSerializer):
    token_class = AccountRefreshToken

    def validate(self, attrs):
        token = self.token_class(attrs['refresh'])
        user = User.objects.filter(pk=token.get('user_id'), is_active=True).first()
        if not user or token.get('session_version', 0) != user.session_version:
            raise InvalidToken('Phiên đăng nhập đã bị thu hồi.')
        return super().validate(attrs)
