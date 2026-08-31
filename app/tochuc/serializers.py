from rest_framework import serializers

from .models import BoPhan, DonViToChuc


class DonViToChucSerializer(serializers.ModelSerializer):
    don_vi_cha_ten = serializers.CharField(
        source="don_vi_cha.ten_don_vi",
        read_only=True,
    )
    nha_may_ten = serializers.CharField(
        source="nha_may.ten_nha_may",
        read_only=True,
    )
    nha_may_pham_vi = serializers.IntegerField(
        source="nha_may_pham_vi_id",
        read_only=True,
    )

    class Meta:
        model = DonViToChuc
        fields = [
            "id",
            "ma_don_vi",
            "ten_don_vi",
            "loai_don_vi",
            "don_vi_cha",
            "don_vi_cha_ten",
            "nha_may",
            "nha_may_ten",
            "nha_may_pham_vi",
            "thu_tu",
            "dang_hoat_dong",
        ]

    def validate(self, attrs):
        parent = attrs.get(
            "don_vi_cha",
            getattr(self.instance, "don_vi_cha", None),
        )
        plant = attrs.get("nha_may", getattr(self.instance, "nha_may", None))
        if parent and plant and parent.nha_may_pham_vi_id not in {
            None,
            plant.id,
        }:
            raise serializers.ValidationError(
                {"don_vi_cha": "Đơn vị cha phải thuộc cùng nhà máy."}
            )
        return attrs


class BoPhanSerializer(serializers.ModelSerializer):
    don_vi_ten = serializers.CharField(
        source="don_vi.ten_don_vi",
        read_only=True,
    )
    nha_may = serializers.IntegerField(
        source="nha_may_pham_vi_id",
        read_only=True,
    )

    class Meta:
        model = BoPhan
        fields = [
            "id",
            "don_vi",
            "don_vi_ten",
            "nha_may",
            "ma_bo_phan",
            "ten_bo_phan",
            "loai_bo_phan",
            "thu_tu",
            "dang_hoat_dong",
        ]
