from rest_framework import serializers
from nhatkyvanhanh.models import SogiaonhancaHC, ChiTietSoGiaoNhanCaHC, NguoiTrucSoGiaoNhanCaHC
from .mixins import UserSummaryMixin

class ChiTietSoGiaoNhanCaHCSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = ChiTietSoGiaoNhanCaHC
        fields = [
            "id",
            "so_giao_nhan_ca",
            "thoi_gian",
            "thoi_gian_bat_dau",
            "thoi_gian_ket_thuc",
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

    def validate(self, attrs):
        start = attrs.get(
            "thoi_gian_bat_dau",
            getattr(self.instance, "thoi_gian_bat_dau", None),
        )
        end = attrs.get(
            "thoi_gian_ket_thuc",
            getattr(self.instance, "thoi_gian_ket_thuc", None),
        )
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"thoi_gian_ket_thuc": "Thời gian kết thúc phải sau thời gian bắt đầu."}
            )
        return attrs


class NguoiTrucSoGiaoNhanCaHCSerializer(serializers.ModelSerializer, UserSummaryMixin):
    nguoi_tao_display = serializers.SerializerMethodField()

    class Meta:
        model = NguoiTrucSoGiaoNhanCaHC
        fields = [
            "id",
            "so_giao_nhan_ca",
            "thoi_gian",
            "thoi_gian_bat_dau",
            "thoi_gian_ket_thuc",
            "ten_nguoi_truc",
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

    def validate(self, attrs):
        start = attrs.get(
            "thoi_gian_bat_dau",
            getattr(self.instance, "thoi_gian_bat_dau", None),
        )
        end = attrs.get(
            "thoi_gian_ket_thuc",
            getattr(self.instance, "thoi_gian_ket_thuc", None),
        )
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"thoi_gian_ket_thuc": "Thời gian kết thúc phải sau thời gian bắt đầu."}
            )
        shift_log = self.context.get("shift_log") or getattr(
            self.instance, "so_giao_nhan_ca", None
        )
        if shift_log and start and end:
            if (
                shift_log.thoi_gian_bat_dau_ca
                and start < shift_log.thoi_gian_bat_dau_ca
            ) or (shift_log.thoi_gian_giao_ca and end > shift_log.thoi_gian_giao_ca):
                raise serializers.ValidationError(
                    {"thoi_gian_ket_thuc": "Khoảng trực phải nằm trong thời gian của sổ."}
                )
            name = attrs.get(
                "ten_nguoi_truc",
                getattr(self.instance, "ten_nguoi_truc", ""),
            ).strip()
            overlapping = shift_log.nguoi_truc_chi_tiets.filter(
                ten_nguoi_truc__iexact=name,
                thoi_gian_bat_dau__lt=end,
                thoi_gian_ket_thuc__gt=start,
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if name and overlapping.exists():
                raise serializers.ValidationError(
                    {"thoi_gian_bat_dau": "Các khoảng trực của cùng một người không được chồng lấn."}
                )
        return attrs


class SogiaonhancaHCSerializer(serializers.ModelSerializer, UserSummaryMixin):
    user_giao_ca_display = serializers.SerializerMethodField()
    user_nhan_ca_display = serializers.SerializerMethodField()
    nguoi_tao_display = serializers.SerializerMethodField()
    chu_ky_user_giao_ca_url = serializers.SerializerMethodField()
    chu_ky_user_nhan_ca_url = serializers.SerializerMethodField()
    da_hoan_thanh = serializers.BooleanField(read_only=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    nguoi_truc_chi_tiets = NguoiTrucSoGiaoNhanCaHCSerializer(many=True, read_only=True)
    noi_dung_chi_tiets = ChiTietSoGiaoNhanCaHCSerializer(many=True, read_only=True)

    class Meta:
        model = SogiaonhancaHC
        fields = [
            "id",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "lich_truc_nguon",
            "ngay_truc_ca_nguon",
            "phien_ban_lich_nguon",
            "dong_bo_bien_che_at",
            "nguoi_tao_thuoc_bien_che",
            "ngay_truc",
            "dia_diem",
            "nguoi_truc",
            "nguoi_truc_2",
            "nguoi_truc_3",
            "nguoi_truc_chi_tiets",
            "thoi_gian_bat_dau_ca",
            "thoi_gian_giao_ca",
            "noi_dung_chi_tiets",
            "luu_y",
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
            "dong_bo_bien_che_at",
            "nguoi_tao_thuoc_bien_che",
            "nguoi_truc_chi_tiets",
            "noi_dung_chi_tiets",
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
        validators = []

    def validate(self, attrs):
        start = attrs.get(
            "thoi_gian_bat_dau_ca",
            getattr(self.instance, "thoi_gian_bat_dau_ca", None),
        )
        end = attrs.get(
            "thoi_gian_giao_ca",
            getattr(self.instance, "thoi_gian_giao_ca", None),
        )
        if start and end and end <= start:
            raise serializers.ValidationError(
                {
                    "thoi_gian_giao_ca": (
                        "Thời gian giao ca phải sau thời gian bắt đầu ca."
                    )
                }
            )
        source_schedule = attrs.get("lich_truc_nguon", getattr(self.instance, "lich_truc_nguon", None))
        source_day = attrs.get("ngay_truc_ca_nguon", getattr(self.instance, "ngay_truc_ca_nguon", None))
        plant = attrs.get("nha_may", getattr(self.instance, "nha_may", None))
        shift_date = attrs.get("ngay_truc", getattr(self.instance, "ngay_truc", None))
        if bool(source_schedule) != bool(source_day):
            raise serializers.ValidationError(
                {"lich_truc_nguon": "Lịch trực nguồn và ngày trực nguồn phải được chọn cùng nhau."}
            )
        if source_schedule and source_day:
            if source_day.lich_truc_id != source_schedule.id:
                raise serializers.ValidationError(
                    {"ngay_truc_ca_nguon": "Ngày trực nguồn không thuộc lịch đã chọn."}
                )
            if plant and source_schedule.nha_may_id != plant.id:
                raise serializers.ValidationError(
                    {"lich_truc_nguon": "Lịch trực nguồn không thuộc nhà máy của sổ."}
                )
            if shift_date and source_day.ngay != shift_date:
                raise serializers.ValidationError(
                    {"ngay_truc_ca_nguon": "Ngày trực nguồn không trùng ngày trực của sổ."}
                )
        return attrs

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def get_user_giao_ca_display(self, obj):
        return self._get_user_display(obj.user_giao_ca)

    def get_user_nhan_ca_display(self, obj):
        return self._get_user_display(obj.user_nhan_ca)

    def get_nguoi_tao_display(self, obj):
        return self._get_user_display(obj.nguoi_tao)

    def get_chu_ky_user_giao_ca_url(self, obj):
        return self._build_file_url(obj.chu_ky_user_giao_ca)

    def get_chu_ky_user_nhan_ca_url(self, obj):
        return self._build_file_url(obj.chu_ky_user_nhan_ca)
