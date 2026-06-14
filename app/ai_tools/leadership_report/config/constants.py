LEADERSHIP_TITLES = {
    "pho tong giam doc",
    "pho tong gd",
    "ptgd",
    "tong giam doc",
    "tong gd",
    "tgd",
}

LEADERSHIP_PRODUCTION_PLANTS = (
    ("songhinh", "Sông Hinh"),
    ("vinhson", "Vĩnh Sơn"),
    ("thuongkontum", "Thượng Kon Tum"),
)

LEADERSHIP_RESERVOIR_STATS = (
    {
        "plant_code": "songhinh",
        "reservoir_key": "songhinh",
        "name": "Sông Hinh",
        "level_field": "cot_g",
        "qve_field": "cot_i",
        "qcm_field": "cot_j",
        "spill_field": "cot_k",
    },
    {
        "plant_code": "vinhson",
        "reservoir_key": "vinhson_a",
        "name": "Vĩnh Sơn A",
        "level_field": "cot_g",
        "qve_field": "cot_i",
        "qcm_field": "cot_j",
        "spill_field": "cot_k",
    },
    {
        "plant_code": "vinhson",
        "reservoir_key": "vinhson_b",
        "name": "Vĩnh Sơn B",
        "level_field": "mucnuoc_thuongluu_ho_b",
        "qve_field": "luuluong_ve_ho_b",
        "qcm_field": None,
        "spill_field": None,
    },
    {
        "plant_code": "vinhson",
        "reservoir_key": "vinhson_c",
        "name": "Vĩnh Sơn C",
        "level_field": "mucnuoc_thuongluu_ho_c",
        "qve_field": "luuluong_ve_ho_c",
        "qcm_field": None,
        "spill_field": None,
    },
    {
        "plant_code": "thuongkontum",
        "reservoir_key": "thuongkontum",
        "name": "Thượng Kon Tum",
        "level_field": "cot_g",
        "qve_field": "cot_i",
        "qcm_field": "cot_j",
        "spill_field": "cot_k",
    },
)

LEADERSHIP_RAINFALL_STATIONS = (
    ("Xa_Ea_M_doan", "Xã Ea M'đoan"),
    ("Thon_10_Xa_Ea_M_Doal", "Thôn 10 - Xã Ea M'Doal"),
    ("UBND_xa_Song_Hinh", "UBND xã Sông Hinh"),
    ("Cu_Kroa", "Cư Kroa"),
    ("Xa_Ea_Trang", "Xã Ea Trang"),
    ("Dap_Tran", "Đập Tràn"),
    ("Ho_A_TD_Vinh_Son", "Hồ A - TĐ Vĩnh Sơn"),
    ("Ho_B_TD_Vinh_Son", "Hồ B - TĐ Vĩnh Sơn"),
    ("Ho_C_TD_Vinh_Son", "Hồ C - TĐ Vĩnh Sơn"),
)

LEADERSHIP_WEATHER_LOCATIONS = (
    {"name": "Sông Hinh", "latitude": 12.92, "longitude": 108.98},
    {"name": "Vĩnh Sơn", "latitude": 14.35, "longitude": 108.77},
    {"name": "Thượng Kon Tum", "latitude": 14.72, "longitude": 108.36},
)

LEADERSHIP_WEEKLY_LIMIT_RESERVOIRS = (
    {
        "plant_code": "songhinh",
        "reservoir_key": "songhinh",
        "name": "Sông Hinh",
        "limit_field": "mucnuoc_gioihan_tuan",
        "level_field": "cot_g",
        "qve_field": "cot_i",
        "qcm_field": "cot_j",
    },
    {
        "plant_code": "vinhson",
        "reservoir_key": "vinhson_a",
        "name": "Vĩnh Sơn A",
        "limit_field": "mucnuoc_gioihan_tuan_ho_a",
        "level_field": "cot_g",
        "qve_field": "cot_i",
        "qcm_field": "cot_j",
    },
    {
        "plant_code": "vinhson",
        "reservoir_key": "vinhson_b",
        "name": "Vĩnh Sơn B",
        "limit_field": "mucnuoc_gioihan_tuan_ho_b",
        "level_field": "mucnuoc_thuongluu_ho_b",
        "qve_field": "luuluong_ve_ho_b",
        "qcm_field": None,
    },
    {
        "plant_code": "thuongkontum",
        "reservoir_key": "thuongkontum",
        "name": "Thượng Kon Tum",
        "limit_field": "mucnuoc_gioihan_tuan",
        "level_field": "cot_g",
        "qve_field": "cot_i",
        "qcm_field": "cot_j",
    },
)
