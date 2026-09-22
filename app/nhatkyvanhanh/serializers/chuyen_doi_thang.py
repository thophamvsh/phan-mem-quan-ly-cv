from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from django.db import transaction
from django.db.models import Q
from decimal import Decimal, InvalidOperation
from core.factory_scope import get_user_factory, is_device_belong_to_factory
from tochuc.models import NhaMay
from nhatkyvanhanh.models import SoChuyenDoiTBThang, ChiTietChuyenDoiTBThang, MauChuyenDoiTBThang
from .mixins import UserSummaryMixin, FlexibleNhaMayRelatedField

class MauChuyenDoiTBThangSerializer(serializers.ModelSerializer):
    nha_may = FlexibleNhaMayRelatedField(queryset=NhaMay.objects.all(), required=False, allow_null=True)
    ma_hien_thi = serializers.CharField(required=False, allow_blank=True)
    ten_hien_thi = serializers.CharField(required=False, allow_blank=True)
    nha_may_code = serializers.SerializerMethodField()
    nha_may_name = serializers.SerializerMethodField()
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)

    class Meta:
        model = MauChuyenDoiTBThang
        fields = [
            "id",
            "ma_dinh_danh",
            "nha_may",
            "nha_may_code",
            "nha_may_name",
            "ma_nhom",
            "ten_nhom",
            "don_vi_nhom",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "ma_hien_thi",
            "ten_hien_thi",
            "pha",
            "loai_tinh_toan",
            "don_vi",
            "thu_tu_nhom",
            "thu_tu",
            "dang_su_dung",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "ma_dinh_danh",
            "nha_may_code",
            "nha_may_name",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "ma_hien_thi": {"required": False, "allow_blank": True},
            "ten_hien_thi": {"required": False, "allow_blank": True},
        }
        # Conditional database constraints are validated explicitly below.
        # DRF's generated validators otherwise require manual-only fields for
        # linked devices before ``validate()`` can populate their snapshots.
        validators = []

    def get_nha_may_code(self, obj):
        return obj.nha_may.ma_nha_may if obj.nha_may else None

    def get_nha_may_name(self, obj):
        return obj.nha_may.ten_nha_may if obj.nha_may else None

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        request = self.context.get("request")
        nha_may = attrs.get("nha_may", getattr(instance, "nha_may", None))
        if nha_may is None and request:
            nha_may = get_user_factory(request.user)
        if nha_may is None:
            raise serializers.ValidationError({"nha_may": "Vui lòng chọn nhà máy."})

        thiet_bi = attrs.get("thiet_bi", getattr(instance, "thiet_bi", None))
        pha = str(attrs.get("pha", getattr(instance, "pha", "")) or "").strip().upper()
        ma_hien_thi = str(
            attrs.get("ma_hien_thi", getattr(instance, "ma_hien_thi", "")) or ""
        ).strip().upper()
        ten_hien_thi = str(
            attrs.get("ten_hien_thi", getattr(instance, "ten_hien_thi", "")) or ""
        ).strip()

        if thiet_bi:
            if not is_device_belong_to_factory(thiet_bi, nha_may):
                raise serializers.ValidationError(
                    {"thiet_bi": "Thiết bị được chọn không thuộc nhà máy này."}
                )
            ma_hien_thi = (thiet_bi.ma_day_du or thiet_bi.ma).strip().upper()
            ten_hien_thi = thiet_bi.ten.strip()
            duplicate = MauChuyenDoiTBThang.objects.filter(
                nha_may=nha_may, thiet_bi=thiet_bi, pha=pha
            )
        else:
            if not ma_hien_thi or not ten_hien_thi:
                raise serializers.ValidationError(
                    "Thiết bị tự do bắt buộc phải nhập mã và tên hiển thị."
                )
            duplicate = MauChuyenDoiTBThang.objects.filter(
                nha_may=nha_may,
                thiet_bi__isnull=True,
                ma_hien_thi=ma_hien_thi,
                pha=pha,
            )

        if instance:
            duplicate = duplicate.exclude(pk=instance.pk)
        active_duplicate = duplicate.filter(dang_su_dung=True).first()
        if active_duplicate:
            raise serializers.ValidationError(
                {"detail": "Thiết bị và pha này đã có trong mẫu tháng."}
            )

        attrs["nha_may"] = nha_may
        attrs["pha"] = pha
        attrs["ma_hien_thi"] = ma_hien_thi
        attrs["ten_hien_thi"] = ten_hien_thi
        self._inactive_duplicate = duplicate.filter(dang_su_dung=False).first()
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            duplicate = MauChuyenDoiTBThang.objects.select_for_update().filter(
                nha_may=validated_data["nha_may"],
                pha=validated_data.get("pha", ""),
                dang_su_dung=False,
            )
            thiet_bi = validated_data.get("thiet_bi")
            if thiet_bi:
                duplicate = duplicate.filter(thiet_bi=thiet_bi)
            else:
                duplicate = duplicate.filter(
                    thiet_bi__isnull=True,
                    ma_hien_thi=validated_data.get("ma_hien_thi", ""),
                )
            inactive = duplicate.first()
            if inactive:
                for field, value in validated_data.items():
                    if field != "ma_dinh_danh":
                        setattr(inactive, field, value)
                inactive.dang_su_dung = True
                inactive.save()
                return inactive
            return super().create(validated_data)


class ChiTietChuyenDoiTBThangSerializer(serializers.ModelSerializer):
    thiet_bi_ten = serializers.CharField(source="thiet_bi.ten", read_only=True)
    thiet_bi_ma_day_du = serializers.CharField(source="thiet_bi.ma_day_du", read_only=True)
    duoc_sua_so_lieu_nen = serializers.SerializerMethodField()

    class Meta:
        model = ChiTietChuyenDoiTBThang
        fields = [
            "id",
            "ma_dinh_danh",
            "so",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "ma_hien_thi",
            "ten_hien_thi",
            "ma_nhom",
            "ten_nhom",
            "don_vi_nhom",
            "don_vi",
            "pha",
            "loai_tinh_toan",
            "dau_nam",
            "dau_thang",
            "nhap_trong_thang",
            "cuoi_thang",
            "thuc_hien",
            "luy_ke_nam",
            "luy_ke_truoc_so_hoa",
            "duoc_sua_so_lieu_nen",
            "ghi_chu",
            "thu_tu_nhom",
            "thu_tu",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "so",
            "ma_dinh_danh",
            "thiet_bi",
            "thiet_bi_ten",
            "thiet_bi_ma_day_du",
            "ma_hien_thi",
            "ten_hien_thi",
            "ma_nhom",
            "ten_nhom",
            "don_vi_nhom",
            "don_vi",
            "pha",
            "loai_tinh_toan",
            "thuc_hien",
            "luy_ke_nam",
            "thu_tu_nhom",
            "thu_tu",
            "created_at",
            "updated_at",
            "duoc_sua_so_lieu_nen",
        ]

    @staticmethod
    def _has_previous_digitized_row(instance):
        if not instance or not instance.so_id or not instance.ma_dinh_danh:
            return False
        return ChiTietChuyenDoiTBThang.objects.filter(
            ma_dinh_danh=instance.ma_dinh_danh,
            so__nha_may=instance.so.nha_may,
        ).filter(
            Q(so__nam__lt=instance.so.nam)
            | Q(so__nam=instance.so.nam, so__thang__lt=instance.so.thang)
        ).exists()

    def get_duoc_sua_so_lieu_nen(self, obj):
        cache = self.context.setdefault("monthly_baseline_edit_cache", {})
        key = (obj.so_id, obj.ma_dinh_danh)
        if key not in cache:
            cache[key] = not self._has_previous_digitized_row(obj)
        return cache[key]

    def validate(self, attrs):
        instance = self.instance

        if instance and self._has_previous_digitized_row(instance):
            protected_fields = ("dau_nam", "luy_ke_truoc_so_hoa")
            changed = [
                field
                for field in protected_fields
                if field in attrs and attrs[field] != getattr(instance, field)
            ]
            if changed:
                raise serializers.ValidationError(
                    {
                        field: "Số liệu nền chỉ được sửa ở tháng đầu tiên được số hóa."
                        for field in changed
                    }
                )

        def decimal_value(field):
            value = attrs.get(field, getattr(instance, field, 0) if instance else 0)
            try:
                return Decimal(str(value or 0))
            except (InvalidOperation, TypeError, ValueError):
                raise serializers.ValidationError({field: "Giá trị số không hợp lệ."})

        dau_thang = decimal_value("dau_thang")
        nhap = decimal_value("nhap_trong_thang")
        cuoi_thang = decimal_value("cuoi_thang")
        loai = getattr(instance, "loai_tinh_toan", "counter") if instance else "counter"
        if loai == "fuel" and dau_thang + nhap - cuoi_thang < 0:
            raise serializers.ValidationError(
                {"cuoi_thang": "Tồn cuối không được lớn hơn tồn đầu cộng lượng nhập."}
            )
        if loai != "fuel" and cuoi_thang < dau_thang:
            raise serializers.ValidationError(
                {"cuoi_thang": "Chỉ số cuối tháng không được nhỏ hơn chỉ số đầu tháng."}
            )
        return attrs


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
