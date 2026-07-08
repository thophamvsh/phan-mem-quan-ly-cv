from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from bisect import bisect_left
from .models import (
    SonghinhMnh,
    ThuongKonTumMnh,
    Vinhson_HoA,
    Vinhson_HoB,
    Vinhson_Hoc,
    ThongSoThuyVanCaiDat,
)

FLOAT_ROUND_DIGITS = 10


def _round_float(value):
    return round(value, FLOAT_ROUND_DIGITS) if isinstance(value, float) else value


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
        (float(row[0]), float(row[1]))
        for row in model_class.objects.order_by("Mucnuoc").values_list(
            "Mucnuoc",
            "dungtich",
        )
    )


@lru_cache(maxsize=16)
def get_capacity_levels_for_reservoir(reservoir_key):
    points = get_capacity_points_for_reservoir(reservoir_key)
    return [point[0] for point in points]


def get_capacity_points_for_plant(nha_may):
    return get_capacity_points_for_reservoir(RESERVOIR_KEY_BY_PLANT.get(nha_may))


def get_capacity_by_reservoir_level(reservoir_key, mucnuoc):
    if mucnuoc is None:
        return None
    try:
        level = float(mucnuoc)
    except (TypeError, ValueError):
        return None

    points = get_capacity_points_for_reservoir(reservoir_key)
    if not points:
        return None

    levels = get_capacity_levels_for_reservoir(reservoir_key)
    upper_index = bisect_left(levels, level)

    if upper_index == 0:
        return points[0][1]
    if upper_index == len(points):
        return points[-1][1]

    lower_level, lower_capacity = points[upper_index - 1]
    upper_level, upper_capacity = points[upper_index]
    if lower_level == upper_level:
        return lower_capacity

    ratio = (level - lower_level) / (upper_level - lower_level)
    capacity = lower_capacity + ratio * (upper_capacity - lower_capacity)
    return _round_float(capacity)


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
        "min_level": points[0][0],
        "min_capacity": points[0][1],
        "max_capacity": points[-1][1],
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

    return _round_float(max(current_capacity - dead_capacity, 0))


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

    return _round_float(max(current_capacity - min_capacity, 0))


def get_operating_capacity_range(nha_may):
    return get_operating_capacity_range_for_reservoir(
        RESERVOIR_KEY_BY_PLANT.get(nha_may),
    )


@lru_cache(maxsize=16)
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


@lru_cache(maxsize=1)
def get_all_weekly_settings_cached():
    from .models import ThongSoThuyVanCaiDat
    return list(
        ThongSoThuyVanCaiDat.objects.filter(
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            tuan_bat_dau__isnull=False,
            tuan_ket_thuc__isnull=False,
        ).only("tuan_bat_dau", "tuan_ket_thuc", "tuan")
    )


@lru_cache(maxsize=1024)
def get_settings_week_number(target_date):
    if not target_date:
        return None
    # 1. Tìm trong danh sách weekly settings được cache trong memory
    for record in get_all_weekly_settings_cached():
        if record.tuan_bat_dau <= target_date <= record.tuan_ket_thuc:
            return record.tuan

    # 2. Fallback sang tính theo ISO week calendar
    monday = target_date - timedelta(days=target_date.weekday())
    _, iso_week, _ = monday.isocalendar()
    return iso_week


@lru_cache(maxsize=1024)
def get_setting_value(nha_may, target_date, loai, field, thang=0, tuan=0):
    nam = target_date.year
    if loai == ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN:
        record = ThongSoThuyVanCaiDat.objects.filter(
            nha_may=nha_may,
            loai=loai,
            tuan_bat_dau__lte=target_date,
            tuan_ket_thuc__gte=target_date,
        ).only(field).first()
        if record:
            return getattr(record, field, None)
        
        # Fallback sang năm ISO của tuần
        monday = target_date - timedelta(days=target_date.weekday())
        nam = monday.isocalendar()[0]

    record = (
        ThongSoThuyVanCaiDat.objects.filter(
            nha_may=nha_may,
            nam=nam,
            loai=loai,
            thang=thang,
            tuan=tuan,
        )
        .only(field)
        .first()
    )
    return getattr(record, field, None) if record else None
