from rest_framework import serializers
from .models import SonghinhMnh, ThuongKonTumMnh, Vinhson_HoA, Vinhson_HoB, Vinhson_Hoc, ThongsoSanxuat, ThongsoGioPhat


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

class ThongsoGioPhatSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThongsoGioPhat
        fields = "__all__"