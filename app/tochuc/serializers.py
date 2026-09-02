from rest_framework import serializers

from .models import BoPhan, DonViToChuc, NhaMay, NhanSu


class NhaMaySerializer(serializers.ModelSerializer):
    class Meta:
        model = NhaMay
        fields = ["id", "ma_nha_may", "ten_nha_may"]


class NhanSuSerializer(serializers.ModelSerializer):
    don_vi_ten = serializers.CharField(
        source="don_vi.ten_don_vi",
        read_only=True,
    )
    bo_phan_ten = serializers.CharField(
        source="bo_phan.ten_bo_phan",
        read_only=True,
    )
    nha_may = serializers.IntegerField(
        source="nha_may_id",
        read_only=True,
    )
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )

    class Meta:
        model = NhanSu
        fields = [
            "id",
            "ma_nhan_vien",
            "ho_ten",
            "nha_may",
            "don_vi",
            "don_vi_ten",
            "bo_phan",
            "bo_phan_ten",
            "user",
            "username",
            "chuc_danh",
            "dien_thoai",
            "tu_ngay",
            "den_ngay",
            "dang_lam_viec",
        ]

    def validate(self, attrs):
        unit = attrs.get(
            "don_vi",
            getattr(self.instance, "don_vi", None),
        )
        department = attrs.get(
            "bo_phan",
            getattr(self.instance, "bo_phan", None),
        )
        if unit and department and department.don_vi_id != unit.id:
            raise serializers.ValidationError(
                {"bo_phan": "Bộ phận phải thuộc đơn vị đã chọn."}
            )
        user = attrs.get("user", getattr(self.instance, "user", None))
        user_plant_id = (
            getattr(getattr(user, "profile", None), "nha_may_id", None)
            if user
            else None
        )
        if user and user_plant_id != unit.nha_may_pham_vi_id:
            raise serializers.ValidationError(
                {"user": "Tài khoản phải thuộc cùng nhà máy với nhân sự."}
            )
        return attrs


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
