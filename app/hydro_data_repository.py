import unicodedata

from django.utils.dateparse import parse_date

from thongsothuyvan.models import (
    SonghinhMnh,
    ThuongKonTumMnh,
    TramDoMuaVrain,
    Vinhson_HoA,
    Vinhson_HoB,
    Vinhson_Hoc,
)


RESERVOIR_MODELS = {
    "song hinh": SonghinhMnh,
    "songhinh": SonghinhMnh,
    "sh": SonghinhMnh,
    "thuong kon tum": ThuongKonTumMnh,
    "thuong kontum": ThuongKonTumMnh,
    "tkt": ThuongKonTumMnh,
    "vinh son": Vinhson_HoA,
    "vinhson": Vinhson_HoA,
    "vinh son a": Vinhson_HoA,
    "vs a": Vinhson_HoA,
    "vsa": Vinhson_HoA,
    "ho a": Vinhson_HoA,
    "vinh son b": Vinhson_HoB,
    "vs b": Vinhson_HoB,
    "vsb": Vinhson_HoB,
    "ho b": Vinhson_HoB,
    "vinh son c": Vinhson_Hoc,
    "vs c": Vinhson_Hoc,
    "vsc": Vinhson_Hoc,
    "ho c": Vinhson_Hoc,
}


def normalize_reservoir_name(name):
    normalized = (name or "").replace("-", " ").replace("_", " ")
    normalized = " ".join(normalized.split())
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return normalized.lower().strip()


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _model_for_reservoir(reservoir):
    return RESERVOIR_MODELS.get(normalize_reservoir_name(reservoir), SonghinhMnh)


def get_table_name(reservoir="Song Hinh"):
    return _model_for_reservoir(reservoir)._meta.db_table


def build_unified_response(target_level, volume, method, reservoir="Song Hinh", H1=None, V1=None, H2=None, V2=None, difference=None):
    response = {
        "reservoir": reservoir,
        "table": get_table_name(reservoir),
        "target_level_m": target_level,
        "method": method,
        "volume_mcm": volume,
        "H": target_level,
        "V": volume,
    }
    if H1 is not None and V1 is not None and H2 is not None and V2 is not None:
        response["bounds"] = {"H1": H1, "V1": V1, "H2": H2, "V2": V2}
        response.update({"H1": H1, "V1": V1, "H2": H2, "V2": V2})
    if difference is not None:
        response["difference_m"] = difference
    return response


def _record_to_dict(record):
    return {
        "Mucnuoc": safe_float(record.Mucnuoc),
        "Dungtich": safe_float(record.dungtich),
    }


def query_exact_water_level(water_level, reservoir="Song Hinh"):
    model = _model_for_reservoir(reservoir)
    record = model.objects.filter(Mucnuoc=water_level).order_by("Mucnuoc").first()
    return _record_to_dict(record) if record else None


def query_nearby_water_levels(target_level, limit=5, reservoir="Song Hinh"):
    model = _model_for_reservoir(reservoir)
    below = list(model.objects.filter(Mucnuoc__lte=target_level).order_by("-Mucnuoc")[:limit])
    above = list(model.objects.filter(Mucnuoc__gte=target_level).order_by("Mucnuoc")[:limit])
    seen = set()
    rows = []
    for record in below + above:
        level = safe_float(record.Mucnuoc)
        if level in seen:
            continue
        seen.add(level)
        rows.append(_record_to_dict(record))
    return rows


def get_volume_for_water_level(water_level, reservoir="Song Hinh"):
    record = query_exact_water_level(water_level, reservoir)
    return record.get("Dungtich") if record else None


def interpolate_water_volume(target_level, reservoir="Song Hinh"):
    target_level = safe_float(target_level)
    exact = query_exact_water_level(target_level, reservoir)
    if exact:
        h = exact["Mucnuoc"]
        v = exact["Dungtich"]
        return build_unified_response(h, v, "exact", reservoir, h, v, h, v)

    candidates = query_nearby_water_levels(target_level, limit=10, reservoir=reservoir)
    if not candidates:
        return None

    below = [row for row in candidates if row["Mucnuoc"] <= target_level]
    above = [row for row in candidates if row["Mucnuoc"] > target_level]
    if not below or not above:
        closest = min(candidates, key=lambda row: abs(row["Mucnuoc"] - target_level))
        difference = abs(closest["Mucnuoc"] - target_level)
        return build_unified_response(
            target_level,
            closest["Dungtich"],
            "nearest",
            reservoir,
            closest["Mucnuoc"],
            closest["Dungtich"],
            closest["Mucnuoc"],
            closest["Dungtich"],
            difference,
        )

    point_below = max(below, key=lambda row: row["Mucnuoc"])
    point_above = min(above, key=lambda row: row["Mucnuoc"])
    h1 = point_below["Mucnuoc"]
    v1 = point_below["Dungtich"]
    h2 = point_above["Mucnuoc"]
    v2 = point_above["Dungtich"]
    volume = v1 + (v2 - v1) * (target_level - h1) / (h2 - h1)
    return build_unified_response(target_level, volume, "interpolated", reservoir, h1, v1, h2, v2)


def query_rainfall_data(start_date=None, end_date=None, limit=1000):
    queryset = TramDoMuaVrain.objects.all().order_by("Thoi_gian")
    parsed_start = parse_date(start_date) if start_date else None
    parsed_end = parse_date(end_date) if end_date else None
    if parsed_start:
        queryset = queryset.filter(Thoi_gian__date__gte=parsed_start)
    if parsed_end:
        queryset = queryset.filter(Thoi_gian__date__lte=parsed_end)

    rows = []
    for record in queryset[:limit]:
        rows.append(
            {
                "Thoi_gian": record.Thoi_gian.date().isoformat(),
                "Xa_Ea_M_doan": record.Xa_Ea_M_doan,
                "Thon_10_Xa_Ea_M_Doal": record.Thon_10_Xa_Ea_M_Doal,
                "UBND_xa_Song_Hinh": record.UBND_xa_Song_Hinh,
                "Cu_Kroa": record.Cu_Kroa,
                "Xa_Ea_Trang": record.Xa_Ea_Trang,
                "Dap_Tran": record.Dap_Tran,
                "Ho_B_TD_Vinh_Son": record.Ho_B_TD_Vinh_Son,
                "Ho_A_TD_Vinh_Son": record.Ho_A_TD_Vinh_Son,
                "Ho_C_TD_Vinh_Son": record.Ho_C_TD_Vinh_Son,
            }
        )
    return rows


def validate_connection():
    return True
