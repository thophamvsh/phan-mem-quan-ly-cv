from django.db import transaction
from rest_framework import serializers

from nhatkyvanhanh.models import HangMucMauTomLuocGiaoCaVH, MauTomLuocGiaoCaVH
from tochuc.models import NhaMay


class HangMucMauTomLuocGiaoCaVHSerializer(serializers.ModelSerializer):
    class Meta:
        model = HangMucMauTomLuocGiaoCaVH
        fields = [
            "id", "ten_hang_muc", "noi_dung_mac_dinh",
            "ghi_chu_mac_dinh", "bat_buoc", "thu_tu",
        ]


class MauTomLuocGiaoCaVHSerializer(serializers.ModelSerializer):
    hang_muc = HangMucMauTomLuocGiaoCaVHSerializer(many=True)
    nha_may_code = serializers.CharField(source="nha_may.ma_nha_may", read_only=True)
    da_duoc_su_dung = serializers.BooleanField(read_only=True)

    class Meta:
        model = MauTomLuocGiaoCaVH
        fields = [
            "id", "nha_may", "nha_may_code", "ten_mau", "phien_ban",
            "dang_ap_dung", "ghi_chu", "nguoi_tao", "hang_muc",
            "da_duoc_su_dung", "created_at", "updated_at",
        ]
        read_only_fields = [
            "phien_ban", "dang_ap_dung", "nguoi_tao", "created_at", "updated_at",
        ]
        validators = []

    def validate_hang_muc(self, items):
        if not items:
            raise serializers.ValidationError("Mẫu phải có ít nhất một hạng mục.")
        names = [item["ten_hang_muc"].strip().casefold() for item in items]
        if any(not name for name in names):
            raise serializers.ValidationError("Tên hạng mục là bắt buộc.")
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Tên hạng mục trong mẫu không được trùng.")
        return items

    @staticmethod
    def _create_items(template, items):
        HangMucMauTomLuocGiaoCaVH.objects.bulk_create([
            HangMucMauTomLuocGiaoCaVH(mau=template, **item)
            for item in items
        ])

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("hang_muc")
        plant = validated_data["nha_may"]
        NhaMay.objects.select_for_update().get(pk=plant.pk)
        latest = (
            MauTomLuocGiaoCaVH.objects.filter(nha_may=plant)
            .order_by("-phien_ban")
            .values_list("phien_ban", flat=True)
            .first()
            or 0
        )
        template = MauTomLuocGiaoCaVH.objects.create(phien_ban=latest + 1, **validated_data)
        self._create_items(template, items)
        return template

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("hang_muc", None)
        validated_data.pop("nha_may", None)
        if items is not None and (instance.da_duoc_su_dung or instance.dang_ap_dung):
            raise serializers.ValidationError(
                "Mẫu đang áp dụng hoặc đã được sử dụng; hãy tạo phiên bản mới để thay đổi hạng mục."
            )
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if items is not None:
            instance.hang_muc.all().delete()
            self._create_items(instance, items)
        return instance
