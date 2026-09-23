from rest_framework import serializers


class MonthlySwitchQRResolveQuerySerializer(serializers.Serializer):
    identity = serializers.UUIDField(required=True)
    year = serializers.IntegerField(required=False, min_value=2000, max_value=2100)
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)


class MonthlySwitchQRSaveSerializer(serializers.Serializer):
    identity = serializers.UUIDField(required=True)
    log_id = serializers.UUIDField(required=True)
    expected_updated_at = serializers.DateTimeField(required=True)
    cuoi_thang = serializers.DecimalField(
        max_digits=18,
        decimal_places=3,
        required=False,
    )
    nhap_trong_thang = serializers.DecimalField(
        max_digits=18,
        decimal_places=3,
        required=False,
    )
    ghi_chu = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    client_time = serializers.DateTimeField(required=False)

    def to_internal_value(self, data):
        allowed_fields = set(self.fields)
        unexpected_fields = sorted(set(data) - allowed_fields)
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

    def validate(self, attrs):
        if not any(
            field in attrs
            for field in ("cuoi_thang", "nhap_trong_thang", "ghi_chu")
        ):
            raise serializers.ValidationError(
                {
                    "detail": "Vui lòng nhập ít nhất một giá trị cần cập nhật.",
                    "code": "empty_update",
                }
            )
        return attrs
