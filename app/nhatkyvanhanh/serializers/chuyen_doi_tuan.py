from rest_framework import serializers
from quanlyvanhanh.models import ThietBi
from nhatkyvanhanh.models import SoChuyenDoiThietBiTuan, LanChuyenDoiThietBi, ChiTietChuyenDoiThietBi, MauChuyenDoiThietBi
from .mixins import UserSummaryMixin

class MauChuyenDoiThietBiSerializer(serializers.ModelSerializer):
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)
    to_may_display = serializers.SerializerMethodField()

    class Meta:
        model = MauChuyenDoiThietBi
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "to_may",
            "to_may_display",
            "nhom_thiet_bi",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "thu_tu",
            "dang_su_dung",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["nha_may_code", "nha_may_name", "thiet_bi_ten", "thiet_bi_ma_day_du", "to_may_display", "created_at", "updated_at"]

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_to_may_display(self, obj):
        return obj.get_to_may_display()


class ChiTietChuyenDoiThietBiSerializer(serializers.ModelSerializer):
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)
    to_may_display = serializers.SerializerMethodField()
    trang_thai_display = serializers.SerializerMethodField()

    class Meta:
        model = ChiTietChuyenDoiThietBi
        fields = [
            "id",
            "lan_chuyen_doi",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "to_may",
            "to_may_display",
            "nhom_thiet_bi",
            "trang_thai",
            "trang_thai_display",
            "ghi_chu",
            "thu_tu",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "lan_chuyen_doi",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "to_may",
            "to_may_display",
            "nhom_thiet_bi",
            "thu_tu",
            "trang_thai_display",
            "created_at",
            "updated_at",
        ]

    def get_to_may_display(self, obj):
        return obj.get_to_may_display()

    def get_trang_thai_display(self, obj):
        return obj.get_trang_thai_display() if obj.trang_thai else ""


class LanChuyenDoiThietBiSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_thuc_hien_display = serializers.SerializerMethodField()
    chi_tiets = ChiTietChuyenDoiThietBiSerializer(many=True, read_only=True)

    class Meta:
        model = LanChuyenDoiThietBi
        fields = [
            "id",
            "so",
            "thoi_gian",
            "nguoi_thuc_hien",
            "nguoi_thuc_hien_display",
            "ghi_chu_chung",
            "chi_tiets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["so", "nguoi_thuc_hien", "nguoi_thuc_hien_display", "chi_tiets", "created_at", "updated_at"]

    def get_nguoi_thuc_hien_display(self, obj):
        return self._get_user_display(obj.nguoi_thuc_hien)


class SoChuyenDoiThietBiTuanSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    ca_truc_display = serializers.SerializerMethodField()
    lan_chuyen_dois = LanChuyenDoiThietBiSerializer(many=True, read_only=True)

    class Meta:
        model = SoChuyenDoiThietBiTuan
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "nam",
            "tuan",
            "ca_truc",
            "ca_truc_display",
            "tuan_bat_dau",
            "tuan_ket_thuc",
            "nguoi_tao",
            "nguoi_tao_display",
            "lan_chuyen_dois",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "ca_truc_display",
            "tuan_bat_dau",
            "tuan_ket_thuc",
            "nguoi_tao",
            "nguoi_tao_display",
            "lan_chuyen_dois",
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
