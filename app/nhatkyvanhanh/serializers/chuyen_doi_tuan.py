from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from tochuc.models import NhaMay
from quanlyvanhanh.models import ThietBi
from nhatkyvanhanh.models import SoChuyenDoiThietBiTuan, LanChuyenDoiThietBi, ChiTietChuyenDoiThietBi, MauChuyenDoiThietBi
from .mixins import UserSummaryMixin, FlexibleNhaMayRelatedField

class MauChuyenDoiThietBiSerializer(serializers.ModelSerializer):
    nha_may = FlexibleNhaMayRelatedField(queryset=NhaMay.objects.all(), required=False, allow_null=True)
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
    trang_thai_tuan_truoc = serializers.SerializerMethodField()
    trang_thai_tuan_truoc_display = serializers.SerializerMethodField()

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
            "trang_thai_tuan_truoc",
            "trang_thai_tuan_truoc_display",
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
            "trang_thai_tuan_truoc",
            "trang_thai_tuan_truoc_display",
            "created_at",
            "updated_at",
        ]

    def _get_prev_status_info(self, obj):
        if not obj or not obj.thiet_bi_id:
            return {}
        context_map = self.context.get("tuan_truoc_status_map")
        if context_map is not None:
            return context_map.get(str(obj.thiet_bi_id), {})

        lan = getattr(obj, "lan_chuyen_doi", None)
        so = getattr(lan, "so", None) if lan else None
        if not so:
            return {}

        if not hasattr(lan, "_cached_prev_status_map"):
            from nhatkyvanhanh.views.helpers import _get_previous_weekly_switch_log
            prev_so = _get_previous_weekly_switch_log(so)
            lan._cached_prev_status_map = {}
            if prev_so:
                prev_lan = prev_so.lan_chuyen_dois.order_by("-thoi_gian", "-created_at").first()
                if prev_lan:
                    for ct in prev_lan.chi_tiets.all():
                        lan._cached_prev_status_map[str(ct.thiet_bi_id)] = {
                            "trang_thai": ct.trang_thai,
                            "trang_thai_display": ct.get_trang_thai_display() if ct.trang_thai else "",
                        }
        return getattr(lan, "_cached_prev_status_map", {}).get(str(obj.thiet_bi_id), {})

    def get_to_may_display(self, obj):
        return obj.get_to_may_display()

    def get_trang_thai_display(self, obj):
        return obj.get_trang_thai_display() if obj.trang_thai else ""

    def get_trang_thai_tuan_truoc(self, obj):
        return self._get_prev_status_info(obj).get("trang_thai", "")

    def get_trang_thai_tuan_truoc_display(self, obj):
        return self._get_prev_status_info(obj).get("trang_thai_display", "")


class LanChuyenDoiThietBiSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_thuc_hien_display = serializers.SerializerMethodField()
    chu_ky_nguoi_thuc_hien = serializers.SerializerMethodField()
    chu_ky_nguoi_thuc_hien_url = serializers.SerializerMethodField()
    chi_tiets = ChiTietChuyenDoiThietBiSerializer(many=True, read_only=True)

    class Meta:
        model = LanChuyenDoiThietBi
        fields = [
            "id",
            "so",
            "thoi_gian",
            "nguoi_thuc_hien",
            "nguoi_thuc_hien_display",
            "chu_ky_nguoi_thuc_hien",
            "chu_ky_nguoi_thuc_hien_url",
            "ghi_chu_chung",
            "chi_tiets",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so",
            "nguoi_thuc_hien",
            "nguoi_thuc_hien_display",
            "chu_ky_nguoi_thuc_hien",
            "chu_ky_nguoi_thuc_hien_url",
            "chi_tiets",
            "created_at",
            "updated_at",
        ]

    def get_nguoi_thuc_hien_display(self, obj):
        return self._get_user_display(obj.nguoi_thuc_hien)

    def get_chu_ky_nguoi_thuc_hien(self, obj):
        return self._get_user_signature_url(obj.nguoi_thuc_hien)

    def get_chu_ky_nguoi_thuc_hien_url(self, obj):
        return self._get_user_signature_url(obj.nguoi_thuc_hien)


class SoChuyenDoiThietBiTuanSerializer(serializers.ModelSerializer, UserSummaryMixin):
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
    lan_chuyen_dois = LanChuyenDoiThietBiSerializer(many=True, read_only=True)
    tuan_truoc_info = serializers.SerializerMethodField()

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
            "lan_chuyen_dois",
            "tuan_truoc_info",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "nha_may_code",
            "nha_may_name",
            "ca_truc_display",
            "tuan_bat_dau",
            "tuan_ket_thuc",
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
            "lan_chuyen_dois",
            "tuan_truoc_info",
            "created_at",
            "updated_at",
        ]
        validators = [
            UniqueTogetherValidator(
                queryset=SoChuyenDoiThietBiTuan.objects.all(),
                fields=["nha_may", "nam", "tuan", "ca_truc"],
                message="Sổ chuyển đổi thiết bị tuần của nhà máy, năm, tuần và ca trực này đã tồn tại.",
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

    def get_tuan_truoc_info(self, obj):
        from nhatkyvanhanh.views.helpers import _get_previous_weekly_switch_log
        prev_so = _get_previous_weekly_switch_log(obj)
        if not prev_so:
            return None
        prev_lan = prev_so.lan_chuyen_dois.order_by("-thoi_gian", "-created_at").first()
        status_map = {}
        if prev_lan:
            for ct in prev_lan.chi_tiets.select_related("thiet_bi").all():
                status_map[str(ct.thiet_bi_id)] = {
                    "trang_thai": ct.trang_thai,
                    "trang_thai_display": ct.get_trang_thai_display() if ct.trang_thai else "",
                    "thiet_bi_ten": ct.thiet_bi.ten if ct.thiet_bi else ct.thiet_bi_ten,
                    "thiet_bi_ma_day_du": ct.thiet_bi.ma_day_du if ct.thiet_bi else ct.thiet_bi_ma_day_du,
                }
        return {
            "id": prev_so.id,
            "nam": prev_so.nam,
            "tuan": prev_so.tuan,
            "tuan_bat_dau": prev_so.tuan_bat_dau,
            "tuan_ket_thuc": prev_so.tuan_ket_thuc,
            "status_map": status_map,
        }

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_ca_truc_display(self, obj):
        return obj.get_ca_truc_display()

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)
