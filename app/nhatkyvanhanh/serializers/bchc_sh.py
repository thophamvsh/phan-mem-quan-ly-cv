from rest_framework import serializers
from nhatkyvanhanh.models import SoBCHCSongHinh
from .mixins import UserSummaryMixin

class SoBCHCSongHinhSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_dong_bo_display = serializers.SerializerMethodField()
    chu_ky_nguoi_dong_bo_url = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()

    class Meta:
        model = SoBCHCSongHinh
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ngay_dong_bo",
            "muc_nuoc_quy_trinh",
            "muc_nuoc_quy_trinh_tu",
            "muc_nuoc_quy_trinh_den",
            "muc_nuoc_ho",
            "luu_luong_ve_ho",
            "luu_luong_xa_tran",
            "luu_luong_chay_may",
            "luu_luong_chay_may_qt",
            "nguyen_nhan_khong_dap_ung",
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

    def get_nguoi_dong_bo_display(self, obj):
        return self._get_user_display(obj.nguoi_dong_bo)

    def get_chu_ky_nguoi_dong_bo_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_dong_bo)
