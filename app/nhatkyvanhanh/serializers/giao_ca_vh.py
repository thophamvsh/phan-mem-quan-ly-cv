from rest_framework import serializers
from nhatkyvanhanh.models import SogiaonhancaVH, ChiTietSoGiaoNhanCaVH, LuuYChiDaoSoGiaoNhanCaVH
from .mixins import UserSummaryMixin

class ChiTietSoGiaoNhanCaVHSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = ChiTietSoGiaoNhanCaVH
        fields = [
            "id",
            "so_giao_nhan_ca",
            "thoi_gian",
            "tieu_de",
            "noi_dung",
            "thu_tu",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so_giao_nhan_ca",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)


class LuuYChiDaoSoGiaoNhanCaVHSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = LuuYChiDaoSoGiaoNhanCaVH
        fields = [
            "id",
            "so_giao_nhan_ca",
            "thoi_gian",
            "noi_dung",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so_giao_nhan_ca",
            "nguoi_tao",
            "nguoi_tao_display",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)


class SogiaonhancaVHSerializer(serializers.ModelSerializer, UserSummaryMixin):
    user_giao_ca_display = serializers.SerializerMethodField()
    user_nhan_ca_display = serializers.SerializerMethodField()
    nguoi_tao_display = serializers.SerializerMethodField()
    hinh_anh_url = serializers.SerializerMethodField()
    chu_ky_user_giao_ca_url = serializers.SerializerMethodField()
    chu_ky_user_nhan_ca_url = serializers.SerializerMethodField()
    da_hoan_thanh = serializers.BooleanField(read_only=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    noi_dung_chi_tiets = ChiTietSoGiaoNhanCaVHSerializer(many=True, read_only=True)
    luu_y_chi_daos = serializers.SerializerMethodField()

    class Meta:
        model = SogiaonhancaVH
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ngay_truc",
            "ca_truc",
            "dia_diem",
            "truc_chinh",
            "truc_phu",
            "truc_ktvh",
            "dieu_do_a0",
            "dieu_do_a3",
            "dieu_do_b3",
            "thoi_gian_bat_dau_ca",
            "thoi_gian_giao_ca",
            "noi_dung_chi_tiets",
            "luu_y_chi_daos",
            "tinh_trang_van_hanh_trong_ca",
            "cac_phuong_tien_trang_bi_ca",
            "luu_y",
            "tong_muc_luc",
            "hinh_anh",
            "hinh_anh_url",
            "chu_ky_user_giao_ca",
            "chu_ky_user_giao_ca_url",
            "chu_ky_user_nhan_ca",
            "chu_ky_user_nhan_ca_url",
            "user_giao_ca",
            "user_giao_ca_display",
            "user_nhan_ca",
            "user_nhan_ca_display",
            "nguoi_tao",
            "nguoi_tao_display",
            "giao_ca_ky_at",
            "nhan_ca_ky_at",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "noi_dung_chi_tiets",
            "luu_y_chi_daos",
            "chu_ky_user_giao_ca",
            "chu_ky_user_giao_ca_url",
            "chu_ky_user_nhan_ca",
            "chu_ky_user_nhan_ca_url",
            "user_giao_ca",
            "user_giao_ca_display",
            "user_nhan_ca",
            "user_nhan_ca_display",
            "nguoi_tao",
            "nguoi_tao_display",
            "trang_thai",
            "da_hoan_thanh",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_luu_y_chi_daos(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return []
        if not user.is_superuser:
            try:
                profile = user.profile
                if not (profile.can_view_shift_handover_directives or profile.can_view_shift_handover_logs):
                    return []
            except Exception:
                return []
        return LuuYChiDaoSoGiaoNhanCaVHSerializer(
            obj.luu_y_chi_daos.all(),
            many=True,
            context=self.context,
        ).data

    def get_user_giao_ca_display(self, obj):
        return self._get_user_display(obj.user_giao_ca)

    def get_user_nhan_ca_display(self, obj):
        return self._get_user_display(obj.user_nhan_ca)

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_hinh_anh_url(self, obj):
        return self._build_file_url(obj.hinh_anh)

    def get_chu_ky_user_giao_ca_url(self, obj):
        return self._build_file_url(obj.chu_ky_user_giao_ca)

    def get_chu_ky_user_nhan_ca_url(self, obj):
        return self._build_file_url(obj.chu_ky_user_nhan_ca)
