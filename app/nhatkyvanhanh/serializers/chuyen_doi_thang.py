from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from tochuc.models import NhaMay
from nhatkyvanhanh.models import SoChuyenDoiTBThang, ChiTietChuyenDoiTBThang, MauChuyenDoiTBThang
from .mixins import UserSummaryMixin, FlexibleNhaMayRelatedField

class MauChuyenDoiTBThangSerializer(serializers.ModelSerializer):
    nha_may = FlexibleNhaMayRelatedField(queryset=NhaMay.objects.all(), required=False, allow_null=True)
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
            "thuc_hien",
            "thu_tu_nhom",
            "thu_tu",
            "created_at",
            "updated_at",
        ]


class SoChuyenDoiTBThangSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nha_may = FlexibleNhaMayRelatedField(queryset=NhaMay.objects.all(), required=False, allow_null=True)
    nguoi_tao_display = serializers.SerializerMethodField()
    chu_ky_nguoi_tao = serializers.SerializerMethodField()
    chu_ky_nguoi_tao_url = serializers.SerializerMethodField()
    nguoi_duyet_display = serializers.SerializerMethodField()
    chu_ky_nguoi_duyet = serializers.SerializerMethodField()
    chu_ky_nguoi_duyet_url = serializers.SerializerMethodField()
    trang_thai_display = serializers.SerializerMethodField()
    da_khoa = serializers.SerializerMethodField()
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    ca_truc_display = serializers.SerializerMethodField()
    chi_tiets = ChiTietChuyenDoiTBThangSerializer(many=True, read_only=True)

    def to_internal_value(self, data):
        if not data.get("nha_may"):
            request = self.context.get("request")
            if request and hasattr(request, "user"):
                from core.factory_scope import get_user_factory
                factory = get_user_factory(request.user)
                if factory:
                    data = data.copy() if hasattr(data, "copy") else dict(data)
                    data["nha_may"] = factory.id
                else:
                    from nhatkyvanhanh.views.helpers import _get_song_hinh_factory
                    sh = _get_song_hinh_factory()
                    if sh:
                        data = data.copy() if hasattr(data, "copy") else dict(data)
                        data["nha_may"] = sh.id
        return super().to_internal_value(data)

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
            "trang_thai",
            "trang_thai_display",
            "da_khoa",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "nguoi_duyet",
            "nguoi_duyet_display",
            "duyet_at",
            "ghi_chu_duyet",
            "chu_ky_nguoi_duyet",
            "chu_ky_nguoi_duyet_url",
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
            "trang_thai",
            "trang_thai_display",
            "da_khoa",
            "nguoi_tao",
            "nguoi_tao_display",
            "chu_ky_nguoi_tao",
            "chu_ky_nguoi_tao_url",
            "nguoi_duyet",
            "nguoi_duyet_display",
            "duyet_at",
            "chu_ky_nguoi_duyet",
            "chu_ky_nguoi_duyet_url",
            "chi_tiets",
            "created_at",
            "updated_at",
        ]
        validators = [
            UniqueTogetherValidator(
                queryset=SoChuyenDoiTBThang.objects.all(),
                fields=["nha_may", "nam", "thang"],
                message="Sổ chuyển đổi thiết bị tháng của nhà máy, năm và tháng này đã tồn tại.",
            )
        ]

    def get_chu_ky_nguoi_tao(self, obj):
        if obj.chu_ky_nguoi_tao:
            request = self.context.get("request")
            url = obj.chu_ky_nguoi_tao.url
            return request.build_absolute_uri(url) if request else url
        return self._get_user_signature_url(obj.nguoi_tao)

    def get_chu_ky_nguoi_tao_url(self, obj):
        return self.get_chu_ky_nguoi_tao(obj)

    def get_nguoi_duyet_display(self, obj):
        return self._get_user_display(obj.nguoi_duyet)

    def get_chu_ky_nguoi_duyet(self, obj):
        if obj.chu_ky_nguoi_duyet:
            request = self.context.get("request")
            url = obj.chu_ky_nguoi_duyet.url
            return request.build_absolute_uri(url) if request else url
        return self._get_user_signature_url(obj.nguoi_duyet)

    def get_chu_ky_nguoi_duyet_url(self, obj):
        return self.get_chu_ky_nguoi_duyet(obj)

    def get_trang_thai_display(self, obj):
        return obj.get_trang_thai_display() if obj.trang_thai else "Chờ duyệt"

    def get_da_khoa(self, obj):
        return bool(obj.da_khoa)

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_ca_truc_display(self, obj):
        return obj.get_ca_truc_display()

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)
