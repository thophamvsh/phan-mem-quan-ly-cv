from rest_framework import serializers
from nhatkyvanhanh.models import SoChuyenDoiTBThang, ChiTietChuyenDoiTBThang, MauChuyenDoiTBThang
from .mixins import UserSummaryMixin

class MauChuyenDoiTBThangSerializer(serializers.ModelSerializer):
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)

    class Meta:
        model = MauChuyenDoiTBThang
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ma_nhom",
            "ten_nhom",
            "don_vi_nhom",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "don_vi",
            "thu_tu_nhom",
            "thu_tu",
            "dang_su_dung",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None


class ChiTietChuyenDoiTBThangSerializer(serializers.ModelSerializer):
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)

    class Meta:
        model = ChiTietChuyenDoiTBThang
        fields = [
            "id",
            "so",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "ma_nhom",
            "ten_nhom",
            "don_vi_nhom",
            "don_vi",
            "dau_thang",
            "cuoi_thang",
            "thuc_hien",
            "ghi_chu",
            "thu_tu_nhom",
            "thu_tu",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "ma_nhom",
            "ten_nhom",
            "don_vi_nhom",
            "don_vi",
            "dau_thang",
            "thuc_hien",
            "thu_tu_nhom",
            "thu_tu",
            "created_at",
            "updated_at",
        ]


class SoChuyenDoiTBThangSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    ca_truc_display = serializers.SerializerMethodField()
    chi_tiets = ChiTietChuyenDoiTBThangSerializer(many=True, read_only=True)

    class Meta:
        model = SoChuyenDoiTBThang
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "nam",
            "thang",
            "ca_truc",
            "ca_truc_display",
            "thang_bat_dau",
            "thang_ket_thuc",
            "nguoi_tao",
            "nguoi_tao_display",
            "chi_tiets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "ca_truc_display",
            "thang_bat_dau",
            "thang_ket_thuc",
            "nguoi_tao",
            "nguoi_tao_display",
            "chi_tiets",
            "created_at",
            "updated_at",
        ]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_ca_truc_display(self, obj):
        return obj.get_ca_truc_display()

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)
