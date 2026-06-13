from rest_framework import serializers
from datetime import datetime, timedelta
from bisect import bisect_left
from decimal import Decimal, InvalidOperation
from functools import lru_cache
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
    ThongSoThuyVanCaiDat,
    ThongsoSanxuat,
)


from .hydrology_services import (
    CAPACITY_MODEL_BY_PLANT,
    get_operating_capacity_by_level,
    get_operating_capacity_range,
    get_operating_capacity_by_reservoir_level,
    get_operating_capacity_range_for_reservoir,
    get_settings_week_number,
    get_setting_value,
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
    dung_tich_ho_noi_suy = serializers.SerializerMethodField()
    dung_tich_ho_min = serializers.SerializerMethodField()
    dung_tich_ho_max = serializers.SerializerMethodField()
    dung_tich_ho_b_noi_suy = serializers.SerializerMethodField()
    dung_tich_ho_b_min = serializers.SerializerMethodField()
    dung_tich_ho_b_max = serializers.SerializerMethodField()
    dung_tich_ho_c_noi_suy = serializers.SerializerMethodField()
    dung_tich_ho_c_min = serializers.SerializerMethodField()
    dung_tich_ho_c_max = serializers.SerializerMethodField()

    class Meta:
        model = ThongsoSanxuat
        fields = "__all__"

    def _get_setting_value(self, nha_may, target_date, loai, field, thang=0, tuan=0):
        settings_lookup = self.context.get("settings_lookup")
        if settings_lookup is not None:
            nam = target_date.year
            if loai == ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN:
                # Dùng năm ISO cho cấu hình tuần
                from datetime import timedelta
                monday = target_date - timedelta(days=target_date.weekday())
                nam = monday.isocalendar()[0]

            record = settings_lookup.get(
                (nha_may, nam, loai, thang, tuan),
            )
            if record:
                return getattr(record, field, None)

            # Fallback truy vấn trực tiếp từ database nếu cache settings_lookup không chứa record
            record_db = ThongSoThuyVanCaiDat.objects.filter(
                nha_may=nha_may,
                nam=nam,
                loai=loai,
                thang=thang,
                tuan=tuan,
            ).only(field).first()
            if record_db:
                return getattr(record_db, field, None)

        if not hasattr(self, "_setting_value_cache"):
            self._setting_value_cache = {}

        cache_key = (nha_may, target_date.year, loai, field, thang, tuan)
        if cache_key not in self._setting_value_cache:
            self._setting_value_cache[cache_key] = get_setting_value(
                nha_may,
                target_date,
                loai,
                field,
                thang=thang,
                tuan=tuan,
            )

        return self._setting_value_cache[cache_key]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        target_date = instance.thoi_gian.date() if instance.thoi_gian else None
        if not target_date:
            return data

        annual_value = self._get_setting_value(
            instance.nha_may,
            target_date,
            ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
            "sanluong_kehoach_nam",
        )
        month_value = self._get_setting_value(
            instance.nha_may,
            target_date,
            ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            "sanluong_kehoach_thang",
            thang=target_date.month,
        )
        week_number = get_settings_week_number(target_date)
        weekly_value = self._get_setting_value(
            instance.nha_may,
            target_date,
            ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            "mucnuoc_gioihan_tuan",
            tuan=week_number,
        )
        weekly_ho_a_value = self._get_setting_value(
            instance.nha_may,
            target_date,
            ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            "mucnuoc_gioihan_tuan_ho_a",
            tuan=week_number,
        )
        weekly_ho_b_value = self._get_setting_value(
            instance.nha_may,
            target_date,
            ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            "mucnuoc_gioihan_tuan_ho_b",
            tuan=week_number,
        )

        settings_values = {
            "cot_w": annual_value,
            "sanluong_kh_thang": month_value,
            "mucnuoc_gioihan_tuan": weekly_value,
            "mucnuoc_gioihan_tuan_ho_a": weekly_ho_a_value,
            "mucnuoc_gioihan_tuan_ho_b": weekly_ho_b_value,
        }
        for field, value in settings_values.items():
            if value is not None:
                data[field] = value

        return data

    def get_dung_tich_ho_noi_suy(self, obj):
        model_class = CAPACITY_MODEL_BY_PLANT.get(obj.nha_may)
        if not model_class:
            return None

        capacity = get_operating_capacity_by_level(obj.nha_may, obj.cot_g)
        return round(capacity, 3) if capacity is not None else None

    def get_dung_tich_ho_min(self, obj):
        return get_operating_capacity_range(obj.nha_may)["min"]

    def get_dung_tich_ho_max(self, obj):
        return get_operating_capacity_range(obj.nha_may)["max"]

    def get_dung_tich_ho_b_noi_suy(self, obj):
        if obj.nha_may != "vinhson":
            return None

        capacity = get_operating_capacity_by_reservoir_level(
            "vinhson_b",
            obj.mucnuoc_thuongluu_ho_b,
        )
        return round(capacity, 3) if capacity is not None else None

    def get_dung_tich_ho_b_min(self, obj):
        if obj.nha_may != "vinhson":
            return None

        return get_operating_capacity_range_for_reservoir("vinhson_b")["min"]

    def get_dung_tich_ho_b_max(self, obj):
        if obj.nha_may != "vinhson":
            return None

        return get_operating_capacity_range_for_reservoir("vinhson_b")["max"]

    def get_dung_tich_ho_c_noi_suy(self, obj):
        if obj.nha_may != "vinhson":
            return None

        capacity = get_operating_capacity_by_reservoir_level(
            "vinhson_c",
            obj.mucnuoc_thuongluu_ho_c,
        )
        return round(capacity, 3) if capacity is not None else None

    def get_dung_tich_ho_c_min(self, obj):
        if obj.nha_may != "vinhson":
            return None

        return get_operating_capacity_range_for_reservoir("vinhson_c")["min"]

    def get_dung_tich_ho_c_max(self, obj):
        if obj.nha_may != "vinhson":
            return None

        return get_operating_capacity_range_for_reservoir("vinhson_c")["max"]


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
