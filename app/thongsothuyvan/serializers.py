from rest_framework import serializers
from datetime import datetime
from .models import (
    SongHinhRealtimeSnapshot,
    SonghinhMnh,
    ThuongKonTumMnh,
    VinhSonRealtimeSnapshot,
    Vinhson_HoA,
    Vinhson_HoB,
    Vinhson_Hoc,
    MucnuocQuytrinh,
    ThongsoGioPhat,
    ThongsoSanxuat,
)


class SonghinhMnhSerializer(serializers.ModelSerializer):
    class Meta:
        model = SonghinhMnh
        fields = "__all__"


class ThuongKonTumMnhSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThuongKonTumMnh
        fields = "__all__"


class Vinhson_HoASerializer(serializers.ModelSerializer):
    class Meta:
        model = Vinhson_HoA
        fields = "__all__"


class Vinhson_HoBSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vinhson_HoB
        fields = "__all__"


class Vinhson_HocSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vinhson_Hoc
        fields = "__all__"

class ThongsoSanxuatSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThongsoSanxuat
        fields = "__all__"


class MucnuocQuytrinhSerializer(serializers.ModelSerializer):
    class Meta:
        model = MucnuocQuytrinh
        fields = "__all__"

    def validate(self, attrs):
        for field_name in ("ngay_bat_dau", "ngay_ket_thuc"):
            value = attrs.get(field_name, getattr(self.instance, field_name, None))
            if not value:
                continue
            try:
                datetime.strptime(value, "%d/%m")
            except ValueError as exc:
                raise serializers.ValidationError(
                    {field_name: "Ngày phải có định dạng dd/MM."}
                ) from exc
        return attrs


class ThongsoGioPhatSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThongsoGioPhat
        fields = "__all__"


class SongHinhRealtimeSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = SongHinhRealtimeSnapshot
        fields = "__all__"


class VinhSonRealtimeSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = VinhSonRealtimeSnapshot
        fields = "__all__"
