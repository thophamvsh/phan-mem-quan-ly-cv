from datetime import date

from django.utils import timezone
from rest_framework import serializers


def _validate_iso_week(year, week):
    try:
        date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise serializers.ValidationError(
            "Năm và tuần ISO không hợp lệ."
        ) from exc


class WeeklySwitchQRResolveQuerySerializer(serializers.Serializer):
    identity = serializers.UUIDField(required=True)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    week = serializers.IntegerField(required=False, min_value=1, max_value=53)
    shift = serializers.ChoiceField(
        choices=("A", "B", "C", "D"),
        required=False,
    )

    def validate(self, attrs):
        if "year" in attrs or "week" in attrs:
            iso = timezone.localdate().isocalendar()
            _validate_iso_week(
                attrs.get("year", iso.year),
                attrs.get("week", iso.week),
            )
        return attrs


class WeeklySwitchQRLookupQuerySerializer(serializers.Serializer):
    code = serializers.CharField(required=True, max_length=255, trim_whitespace=True)
    plant = serializers.CharField(required=False, max_length=30, trim_whitespace=True)

    def validate_code(self, value):
        if len(value) < 2:
            raise serializers.ValidationError("Mã thiết bị phải có ít nhất 2 ký tự.")
        return value


class WeeklySwitchQRSaveItemSerializer(serializers.Serializer):
    row_id = serializers.UUIDField(required=True)
    expected_updated_at = serializers.DateTimeField(required=True)
    trang_thai = serializers.ChoiceField(choices=("lam_viec", "du_phong"))
    ghi_chu = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class WeeklySwitchQRSaveSerializer(serializers.Serializer):
    identity = serializers.UUIDField(required=True)
    log_id = serializers.UUIDField(required=True)
    lan_id = serializers.UUIDField(required=True)
    expected_updated_at = serializers.DateTimeField(required=False)
    trang_thai = serializers.ChoiceField(
        choices=("lam_viec", "du_phong"), required=False
    )
    working_device_id = serializers.IntegerField(required=False, min_value=1)
    items = WeeklySwitchQRSaveItemSerializer(many=True, required=False)
    confirmed = serializers.BooleanField(required=True)
    ghi_chu = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    client_time = serializers.DateTimeField(required=False)

    def validate_confirmed(self, value):
        if not value:
            raise serializers.ValidationError(
                "Bạn phải xác nhận đã chuyển đổi thiết bị trước khi lưu."
            )
        return value

    def validate(self, attrs):
        legacy_fields = {"expected_updated_at", "trang_thai"}
        has_legacy = legacy_fields.issubset(attrs)
        has_group = bool(attrs.get("working_device_id") or attrs.get("items"))
        if not has_legacy and not has_group:
            raise serializers.ValidationError(
                "Vui lòng chọn thiết bị làm việc hoặc nhập trạng thái của cả nhóm."
            )
        return attrs

    def to_internal_value(self, data):
        unexpected_fields = sorted(set(data) - set(self.fields))
        if unexpected_fields:
            raise serializers.ValidationError(
                {
                    "code": "unexpected_fields",
                    "detail": (
                        "Payload chứa trường không được phép cập nhật: "
                        + ", ".join(unexpected_fields)
                    ),
                }
            )
        return super().to_internal_value(data)


class WeeklySwitchQRCreateLanSerializer(serializers.Serializer):
    log_id = serializers.UUIDField(required=True)

    def to_internal_value(self, data):
        unexpected_fields = sorted(set(data) - set(self.fields))
        if unexpected_fields:
            raise serializers.ValidationError(
                {
                    "code": "unexpected_fields",
                    "detail": (
                        "Payload chứa trường không được phép cập nhật: "
                        + ", ".join(unexpected_fields)
                    ),
                }
            )
        return super().to_internal_value(data)
