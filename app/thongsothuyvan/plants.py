import unicodedata


PLANT_CODE_ALIASES = {
    "sh": "songhinh",
    "songhinh": "songhinh",
    "songhinhhpp": "songhinh",
    "vs": "vinhson",
    "vinhson": "vinhson",
    "vinhsonhpp": "vinhson",
    "tkt": "thuongkontum",
    "tktu": "thuongkontum",
    "th??ngkontum": "thuongkontum",
    "thuongkontum": "thuongkontum",
    "thuongkontumhpp": "thuongkontum",
}

HYDROLOGY_PLANTS = {
    "songhinh": {
        "code": "songhinh",
        "short_code": "SH",
        "name": "Sông Hinh",
        "dashboard_slug": "song-hinh",
        "mnh_endpoint": "song-hinh-mnh",
        "reservoirs": ["songhinh"],
    },
    "vinhson": {
        "code": "vinhson",
        "short_code": "VS",
        "name": "Vĩnh Sơn",
        "dashboard_slug": "vinh-son",
        "mnh_endpoint": "vinhson-ho-a",
        "reservoirs": ["vinhson-ho-a", "vinhson-ho-b", "vinhson-ho-c"],
    },
    "thuongkontum": {
        "code": "thuongkontum",
        "short_code": "TKT",
        "name": "Thượng Kon Tum",
        "dashboard_slug": "thuong-kon-tum",
        "mnh_endpoint": "thuong-kon-tum-mnh",
        "reservoirs": ["thuong-kon-tum"],
    },
}


def normalize_plant_code(value):
    if not value:
        return ""

    ascii_value = str(value).replace("đ", "d").replace("Đ", "D")
    ascii_value = unicodedata.normalize("NFKD", ascii_value)
    ascii_value = "".join(char for char in ascii_value if not unicodedata.combining(char))
    ascii_value = ascii_value.encode("ascii", "ignore").decode("ascii")
    compact = (
        ascii_value
        .strip()
        .lower()
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
    )
    return PLANT_CODE_ALIASES.get(compact, compact)


def is_valid_plant_code(value):
    return normalize_plant_code(value) in HYDROLOGY_PLANTS


def get_hydrology_plants():
    return list(HYDROLOGY_PLANTS.values())
