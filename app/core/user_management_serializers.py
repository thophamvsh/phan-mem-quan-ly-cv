from collections.abc import Mapping
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import User


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError({'detail': 'Dữ liệu phải là một đối tượng JSON.'})
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({
                field: 'Không được gửi trường này.' for field in sorted(unknown)
            })
        return super().to_internal_value(data)


class CreateManagedUserSerializer(StrictSerializer):
    username = serializers.RegexField(r'^[A-Za-z0-9_.@+-]+$', max_length=255)
    email = serializers.EmailField(max_length=255)
    first_name = serializers.CharField(max_length=255)
    last_name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)
    nha_may = serializers.IntegerField(required=False, min_value=1)
    role_id = serializers.IntegerField(min_value=1)
    nhan_su_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    chuc_danh = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Mật khẩu không khớp.'})
        attrs['email'] = attrs['email'].lower()
        user = User(**{key: attrs[key] for key in ('username', 'email', 'first_name', 'last_name')})
        try:
            validate_password(attrs['password'], user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': error.messages})
        return attrs


class EditManagedUserSerializer(StrictSerializer):
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    chuc_danh = serializers.CharField(max_length=100, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=255, required=False)
    last_name = serializers.CharField(max_length=255, required=False)
    nhan_su_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class ChangeRoleSerializer(StrictSerializer):
    role_id = serializers.IntegerField(min_value=1)


class ChangeStatusSerializer(StrictSerializer):
    is_active = serializers.BooleanField()


class OptionsQuerySerializer(StrictSerializer):
    nha_may = serializers.IntegerField(required=False, min_value=1)
