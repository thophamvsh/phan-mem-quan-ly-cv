from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from nhatkyvanhanh.models import (
    ChiTietMauTrangThaiThietBiCa,
    MauTrangThaiThietBiCa,
    NhomMauTrangThaiThietBiCa,
)
from tochuc.models import NhaMay


class ChiTietMauTrangThaiThietBiCaSerializer(serializers.ModelSerializer):
    ma_thiet_bi = serializers.CharField(source="ma_hien_thi", required=False)
    ghi_chu = serializers.CharField(source="ghi_chu_mac_dinh", required=False, allow_blank=True)

    class Meta:
        model = ChiTietMauTrangThaiThietBiCa
        fields = ["id", "thiet_bi", "ma_hien_thi", "ma_thiet_bi", "trang_thai_mac_dinh", "ghi_chu_mac_dinh", "ghi_chu", "thu_tu"]
        extra_kwargs = {"ma_hien_thi": {"required": False}}

    def validate(self, attrs):
        if not attrs.get("ma_hien_thi"):
            device = attrs.get("thiet_bi")
            attrs["ma_hien_thi"] = device.ma_day_du if device else ""
        if not attrs["ma_hien_thi"].strip():
            raise serializers.ValidationError({"ma_hien_thi": "Mã hiển thị là bắt buộc."})
        return attrs


class NhomMauTrangThaiThietBiCaSerializer(serializers.ModelSerializer):
    thiet_bi = ChiTietMauTrangThaiThietBiCaSerializer(many=True)

    class Meta:
        model = NhomMauTrangThaiThietBiCa
        fields = ["id", "ma_nhom", "tieu_de", "thu_tu", "thiet_bi"]


class MauTrangThaiThietBiCaSerializer(serializers.ModelSerializer):
    groups = NhomMauTrangThaiThietBiCaSerializer(source="nhom_thiet_bi", many=True)
    nha_may_code = serializers.CharField(source="nha_may.ma_nha_may", read_only=True)
    da_duoc_su_dung = serializers.BooleanField(read_only=True)

    class Meta:
        model = MauTrangThaiThietBiCa
        fields = ["id", "nha_may", "nha_may_code", "ten_mau", "phien_ban", "dang_ap_dung", "ghi_chu", "nguoi_tao", "groups", "da_duoc_su_dung", "created_at", "updated_at"]
        read_only_fields = ["phien_ban", "dang_ap_dung", "nguoi_tao", "created_at", "updated_at"]
        validators = []

    def validate_groups(self, groups):
        codes = [group["ma_nhom"].casefold() for group in groups]
        if len(codes) != len(set(codes)):
            raise serializers.ValidationError("Mã nhóm trong mẫu không được trùng.")
        all_devices = []
        for group in groups:
            all_devices.extend(item["ma_hien_thi"].strip().casefold() for item in group["thiet_bi"])
        if len(all_devices) != len(set(all_devices)):
            raise serializers.ValidationError("Thiết bị trong mẫu không được trùng.")
        return groups

    def _create_groups(self, template, groups):
        for group_data in groups:
            devices = group_data.pop("thiet_bi")
            group = NhomMauTrangThaiThietBiCa.objects.create(mau=template, **group_data)
            for device_data in devices:
                detail = ChiTietMauTrangThaiThietBiCa(nhom=group, **device_data)
                try:
                    detail.full_clean()
                except DjangoValidationError as exc:
                    raise serializers.ValidationError(exc.message_dict)
                detail.save()

    @transaction.atomic
    def create(self, validated_data):
        groups = validated_data.pop("nhom_thiet_bi")
        plant = validated_data["nha_may"]
        NhaMay.objects.select_for_update().get(pk=plant.pk)
        next_version = (MauTrangThaiThietBiCa.objects.filter(nha_may=plant).order_by("-phien_ban").values_list("phien_ban", flat=True).first() or 0) + 1
        template = MauTrangThaiThietBiCa.objects.create(phien_ban=next_version, **validated_data)
        self._create_groups(template, groups)
        return template

    @transaction.atomic
    def update(self, instance, validated_data):
        groups = validated_data.pop("nhom_thiet_bi", None)
        validated_data.pop("nha_may", None)
        if groups is not None and (instance.da_duoc_su_dung or instance.dang_ap_dung):
            raise serializers.ValidationError(
                "Mẫu đang áp dụng hoặc đã được sử dụng; hãy tạo phiên bản mới để thay đổi thiết bị."
            )
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if groups is not None:
            instance.nhom_thiet_bi.all().delete()
            self._create_groups(instance, groups)
        return instance
