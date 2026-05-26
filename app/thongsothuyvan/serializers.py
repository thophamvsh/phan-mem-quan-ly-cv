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


CAPACITY_MODEL_BY_PLANT = {
    "songhinh": SonghinhMnh,
    "vinhson": Vinhson_HoA,
    "thuongkontum": ThuongKonTumMnh,
}

CAPACITY_MODEL_BY_RESERVOIR = {
    "songhinh": SonghinhMnh,
    "vinhson_a": Vinhson_HoA,
    "vinhson_b": Vinhson_HoB,
    "vinhson_c": Vinhson_Hoc,
    "thuongkontum": ThuongKonTumMnh,
}

RESERVOIR_KEY_BY_PLANT = {
    "songhinh": "songhinh",
    "vinhson": "vinhson_a",
    "thuongkontum": "thuongkontum",
}

OPERATING_LEVEL_RANGE_BY_PLANT = {
    "songhinh": (196, 209),
    "vinhson": (765, 775),
    "thuongkontum": (1135, 1160),
}

OPERATING_LEVEL_RANGE_BY_RESERVOIR = {
    "songhinh": (196, 209),
    "vinhson_a": (765, 775),
    "vinhson_b": (813.6, 826),
    "vinhson_c": (971.3, 981),
    "thuongkontum": (1135, 1160),
}


@lru_cache(maxsize=16)
def get_capacity_points_for_reservoir(reservoir_key):
    model_class = CAPACITY_MODEL_BY_RESERVOIR.get(reservoir_key)
    if not model_class:
        return ()

    return tuple(
        (record.Mucnuoc, record.dungtich)
        for record in model_class.objects.order_by("Mucnuoc").only(
            "Mucnuoc",
            "dungtich",
        )
    )


def get_capacity_points_for_plant(nha_may):
    return get_capacity_points_for_reservoir(RESERVOIR_KEY_BY_PLANT.get(nha_may))


def get_capacity_by_reservoir_level(reservoir_key, mucnuoc):
    try:
        level = Decimal(str(mucnuoc))
    except (InvalidOperation, TypeError, ValueError):
        return None

    points = get_capacity_points_for_reservoir(reservoir_key)
    if not points:
        return None

    levels = [point[0] for point in points]
    upper_index = bisect_left(levels, level)

    if upper_index == 0:
        return float(points[0][1])
    if upper_index == len(points):
        return float(points[-1][1])

    lower_level, lower_capacity = points[upper_index - 1]
    upper_level, upper_capacity = points[upper_index]
    if lower_level == upper_level:
        return float(lower_capacity)

    ratio = (level - lower_level) / (upper_level - lower_level)
    capacity = lower_capacity + ratio * (upper_capacity - lower_capacity)
    return float(capacity)


def get_capacity_by_level(nha_may, mucnuoc):
    return get_capacity_by_reservoir_level(
        RESERVOIR_KEY_BY_PLANT.get(nha_may),
        mucnuoc,
    )


@lru_cache(maxsize=16)
def get_capacity_bounds_for_reservoir(reservoir_key):
    points = get_capacity_points_for_reservoir(reservoir_key)
    if not points:
        return {"min_level": None, "min_capacity": None, "max_capacity": None}

    return {
        "min_level": float(points[0][0]),
        "min_capacity": float(points[0][1]),
        "max_capacity": float(points[-1][1]),
    }


def get_capacity_bounds_for_plant(nha_may):
    return get_capacity_bounds_for_reservoir(RESERVOIR_KEY_BY_PLANT.get(nha_may))


def get_dead_capacity(nha_may, dead_level):
    if dead_level is not None:
        capacity = get_capacity_by_level(nha_may, dead_level)
        if capacity is not None:
            return capacity

    return get_capacity_bounds_for_plant(nha_may)["min_capacity"]


def get_useful_capacity_by_level(nha_may, mucnuoc, dead_level):
    current_capacity = get_capacity_by_level(nha_may, mucnuoc)
    dead_capacity = get_dead_capacity(nha_may, dead_level)
    if current_capacity is None or dead_capacity is None:
        return None

    return max(current_capacity - dead_capacity, 0)


def get_operating_capacity_by_level(nha_may, mucnuoc):
    return get_operating_capacity_by_reservoir_level(
        RESERVOIR_KEY_BY_PLANT.get(nha_may),
        mucnuoc,
    )


def get_operating_capacity_by_reservoir_level(reservoir_key, mucnuoc):
    level_range = OPERATING_LEVEL_RANGE_BY_RESERVOIR.get(reservoir_key)
    if not level_range:
        level_range = (
            get_capacity_bounds_for_reservoir(reservoir_key)["min_level"],
            None,
        )

    min_level, _ = level_range
    current_capacity = get_capacity_by_reservoir_level(reservoir_key, mucnuoc)
    min_capacity = get_capacity_by_reservoir_level(reservoir_key, min_level)
    if current_capacity is None or min_capacity is None:
        return None

    return max(current_capacity - min_capacity, 0)


def get_operating_capacity_range(nha_may):
    return get_operating_capacity_range_for_reservoir(
        RESERVOIR_KEY_BY_PLANT.get(nha_may),
    )


def get_operating_capacity_range_for_reservoir(reservoir_key):
    level_range = OPERATING_LEVEL_RANGE_BY_RESERVOIR.get(reservoir_key)
    if not level_range:
        bounds = get_capacity_bounds_for_reservoir(reservoir_key)
        min_capacity = bounds["min_capacity"]
        max_capacity = bounds["max_capacity"]
        if min_capacity is None or max_capacity is None:
            return {"min": None, "max": None}

        return {"min": 0, "max": round(max(max_capacity - min_capacity, 0), 3)}

    min_level, max_level = level_range
    min_capacity = get_capacity_by_reservoir_level(reservoir_key, min_level)
    max_capacity = get_capacity_by_reservoir_level(reservoir_key, max_level)
    if min_capacity is None or max_capacity is None:
        return {"min": None, "max": None}

    return {"min": 0, "max": round(max(max_capacity - min_capacity, 0), 3)}


def get_settings_week_number(target_date):
    current = target_date.replace(month=1, day=1)
    end_of_year = target_date.replace(month=12, day=31)
    week_number = 1

    while current <= end_of_year:
        if week_number == 1:
            week_start = current
        else:
            week_start = current + timedelta(days=(7 - current.weekday()) % 7)
        if week_start > end_of_year:
            break
        week_end = min(week_start + timedelta(days=6), end_of_year)
        if week_start <= target_date <= week_end:
            return week_number
        current = week_end + timedelta(days=1)
        week_number += 1

    return 0


def get_setting_value(nha_may, target_date, loai, field, thang=0, tuan=0):
    record = (
        ThongSoThuyVanCaiDat.objects.filter(
            nha_may=nha_may,
            nam=target_date.year,
            loai=loai,
            thang=thang,
            tuan=tuan,
        )
        .only(field)
        .first()
    )
    return getattr(record, field, None) if record else None


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

        fallback_values = {
            "cot_w": annual_value,
            "sanluong_kh_thang": month_value,
            "mucnuoc_gioihan_tuan": weekly_value,
            "mucnuoc_gioihan_tuan_ho_a": weekly_ho_a_value,
            "mucnuoc_gioihan_tuan_ho_b": weekly_ho_b_value,
        }
        for field, value in fallback_values.items():
            if data.get(field) is None and value is not None:
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
