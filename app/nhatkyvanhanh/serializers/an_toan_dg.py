from rest_framework import serializers
from nhatkyvanhanh.models import SoAnToanDauGio
from .mixins import UserSummaryMixin

class SoAnToanSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_dong_bo_display = serializers.SerializerMethodField()
    chu_ky_nguoi_dong_bo_url = serializers.SerializerMethodField()
    ca_truc_display = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()

    class Meta:
        model = SoAnToanDauGio
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ngay_dong_bo",
            "ca_truc",
            "ca_truc_display",
            "tinh_trang_an_toan",
            "nguoi_dong_bo",
            "nguoi_dong_bo_display",
            "chu_ky_nguoi_dong_bo",
            "chu_ky_nguoi_dong_bo_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "nguoi_dong_bo",
            "nguoi_dong_bo_display",
            "chu_ky_nguoi_dong_bo",
            "chu_ky_nguoi_dong_bo_url",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_ca_truc_display(self, obj):
        return obj.get_ca_truc_display()

    def get_nguoi_dong_bo_display(self, obj):
        return self._get_user_display(obj.nguoi_dong_bo)

    def get_chu_ky_nguoi_dong_bo_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_dong_bo)
