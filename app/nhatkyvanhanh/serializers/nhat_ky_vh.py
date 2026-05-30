from rest_framework import serializers
from nhatkyvanhanh.models import Sonhatkyvanhanh, SonhatkyvanhanhDiesel
from .mixins import UserSummaryMixin

class SonhatkyvanhanhSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    nguoi_xac_nhan_display = serializers.SerializerMethodField()
    chu_ky_nguoi_tao_url = serializers.SerializerMethodField()
    chu_ky_nguoi_xac_nhan_url = serializers.SerializerMethodField()
    da_hoan_thanh = serializers.BooleanField(read_only=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()

    class Meta:
        model = Sonhatkyvanhanh
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "thoi_gian_tao",
            "noi_dung_tao",
            "nguoi_tao",
            "nguoi_tao_display",
            "nguoi_xac_nhan",
            "nguoi_xac_nhan_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "chu_ky_nguoi_xac_nhan",
            "chu_ky_nguoi_xac_nhan_url",
            "xac_nhan_at",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "nguoi_tao",
            "nguoi_tao_display",
            "nguoi_xac_nhan",
            "nguoi_xac_nhan_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "chu_ky_nguoi_xac_nhan",
            "chu_ky_nguoi_xac_nhan_url",
            "xac_nhan_at",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_nguoi_xac_nhan_display(self, obj):
        return self._get_user_display(obj.nguoi_xac_nhan)

    def get_chu_ky_nguoi_tao_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_tao)

    def get_chu_ky_nguoi_xac_nhan_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_xac_nhan)


class SonhatkyvanhanhDieselSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    chu_ky_nguoi_tao_url = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()

    class Meta:
        model = SonhatkyvanhanhDiesel
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "thoi_gian",
            "noi_dung",
            "i",
            "u",
            "f",
            "i_sac",
            "u_sac",
            "p",
            "q",
            "chi_so_gio_vh",
            "t_may",
            "muc_dau",
            "ap_luc_dau",
            "ca_truc",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_chu_ky_nguoi_tao_url(self, obj):
        return self._build_file_url(obj.chu_ky_nguoi_tao)
