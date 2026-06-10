from copy import deepcopy


DIEN_CONFIGS = {
    "SH": {
        "title": "BẢNG NHẬP THÔNG SỐ VẬN HÀNH ĐIỆN SÔNG HINH",
        "layout": [
            {
                "group": "TỔ MÁY H1",
                "device_code": "SH.TB.H1",
                "columns": [
                    {"ten": "Điện áp kích từ", "ma": "dien_ap_kich_tu_h1", "don_vi": "V"},
                    {"ten": "Dòng điện kích từ", "ma": "dong_dien_kich_tu_h1", "don_vi": "A"},
                    {"ten": "Điện áp", "ma": "dien_ap_h1", "don_vi": "kV"},
                    {"ten": "Dòng điện", "ma": "dong_dien_h1", "don_vi": "A"},
                    {"ten": "Công suất tác dụng", "ma": "cong_suat_tac_dung_h1", "don_vi": "MW"},
                    {"ten": "Công suất phản kháng", "ma": "cong_suat_phan_khang_h1", "don_vi": "MVar"},
                    {"ten": "Tần số", "ma": "tan_so_h1", "don_vi": "Hz"},
                ],
            },
            {
                "group": "TỔ MÁY H2",
                "device_code": "SH.TB.H2",
                "columns": [
                    {"ten": "Điện áp kích từ", "ma": "dien_ap_kich_tu_h2", "don_vi": "V"},
                    {"ten": "Dòng điện kích từ", "ma": "dong_dien_kich_tu_h2", "don_vi": "A"},
                    {"ten": "Điện áp", "ma": "dien_ap_h2", "don_vi": "kV"},
                    {"ten": "Dòng điện", "ma": "dong_dien_h2", "don_vi": "A"},
                    {"ten": "Công suất tác dụng", "ma": "cong_suat_tac_dung_h2", "don_vi": "MW"},
                    {"ten": "Công suất phản kháng", "ma": "cong_suat_phan_khang_h2", "don_vi": "MVar"},
                    {"ten": "Tần số", "ma": "tan_so_h2", "don_vi": "Hz"},
                ],
            },
            {
                "group": "TRẠM PHÂN PHỐI",
                "device_code": "SH.TB.TPP",
                "columns": [
                    {"ten": "Tổng P máy phát", "ma": "tong_p_may_phat", "don_vi": "MW"},
                    {"ten": "Tổng Q máy phát", "ma": "tong_q_may_phat", "don_vi": "MVar"},
                    {"ten": "Điện áp ĐZ 172", "ma": "dien_ap_172", "don_vi": "kV", "sub_device": "110.172"},
                    {"ten": "Dòng điện ĐZ 172", "ma": "dong_dien_172", "don_vi": "A", "sub_device": "110.172"},
                    {"ten": "Công suất tác dụng ĐZ 172", "ma": "cong_suat_tac_dung_172", "don_vi": "MW", "sub_device": "110.172"},
                    {"ten": "Công suất phản kháng ĐZ 172", "ma": "cong_suat_phan_khang_172", "don_vi": "MVar", "sub_device": "110.172"},
                    {"ten": "Điện áp ĐZ 174", "ma": "dien_ap_174", "don_vi": "kV", "sub_device": "110.174"},
                    {"ten": "Dòng điện ĐZ 174", "ma": "dong_dien_174", "don_vi": "A", "sub_device": "110.174"},
                    {"ten": "Công suất tác dụng ĐZ 174", "ma": "cong_suat_tac_dung_174", "don_vi": "MW", "sub_device": "110.174"},
                    {"ten": "Công suất phản kháng ĐZ 174", "ma": "cong_suat_phan_khang_174", "don_vi": "MVar", "sub_device": "110.174"},
                    {"ten": "Điện áp ĐZ 471", "ma": "dien_ap_471", "don_vi": "kV", "sub_device": "22.471"},
                    {"ten": "Dòng điện ĐZ 471", "ma": "dong_dien_471", "don_vi": "A", "sub_device": "22.471"},
                    {"ten": "Công suất tác dụng ĐZ 471", "ma": "cong_suat_tac_dung_471", "don_vi": "MW", "sub_device": "22.471"},
                    {"ten": "Công suất phản kháng ĐZ 471", "ma": "cong_suat_phan_khang_471", "don_vi": "MVar", "sub_device": "22.471"},
                    {"ten": "Điện áp ĐZ 472", "ma": "dien_ap_472", "don_vi": "kV", "sub_device": "22.472"},
                    {"ten": "Dòng điện ĐZ 472", "ma": "dong_dien_472", "don_vi": "A", "sub_device": "22.472"},
                    {"ten": "Công suất tác dụng ĐZ 472", "ma": "cong_suat_tac_dung_472", "don_vi": "MW", "sub_device": "22.472"},
                    {"ten": "Công suất phản kháng ĐZ 472", "ma": "cong_suat_phan_khang_472", "don_vi": "MVar", "sub_device": "22.472"},
                    {"ten": "Tổng P 22kV", "ma": "tong_p_22kv", "don_vi": "MW"},
                ],
            },
        ],
    },
    "VS": {
        "title": "BẢNG NHẬP THÔNG SỐ VẬN HÀNH ĐIỆN VĨNH SƠN",
        "layout": [
            {
                "group": "MÁY PHÁT H1",
                "device_code": "VS.TB.H1",
                "columns": [
                    {"ten": "Ukt", "ma": "dien_ap_kich_tu_h1", "don_vi": "V"},
                    {"ten": "Ikt", "ma": "dong_dien_kich_tu_h1", "don_vi": "A"},
                    {"ten": "U", "ma": "dien_ap_h1", "don_vi": "kV"},
                    {"ten": "P", "ma": "cong_suat_tac_dung_h1", "don_vi": "MW"},
                    {"ten": "Q", "ma": "cong_suat_phan_khang_h1", "don_vi": "MVar"},
                    {"ten": "f", "ma": "tan_so_h1", "don_vi": "Hz"},
                ],
            },
            {
                "group": "MÁY PHÁT H2",
                "device_code": "VS.TB.H2",
                "columns": [
                    {"ten": "Ukt", "ma": "dien_ap_kich_tu_h2", "don_vi": "V"},
                    {"ten": "Ikt", "ma": "dong_dien_kich_tu_h2", "don_vi": "A"},
                    {"ten": "U", "ma": "dien_ap_h2", "don_vi": "kV"},
                    {"ten": "P", "ma": "cong_suat_tac_dung_h2", "don_vi": "MW"},
                    {"ten": "Q", "ma": "cong_suat_phan_khang_h2", "don_vi": "MVar"},
                    {"ten": "f", "ma": "tan_so_h2", "don_vi": "Hz"},
                ],
            },
            {
                "group": "TRẠM PHÂN PHỐI 110 kV",
                "device_code": "VS.TB.TPP",
                "columns": [
                    {"ten": "I1", "ma": "dong_dien_thanh_cai", "don_vi": "A"},
                    {"ten": "I171", "ma": "dong_dien_171", "don_vi": "A", "sub_device": "171"},
                    {"ten": "P171", "ma": "cong_suat_tac_dung_171", "don_vi": "MW", "sub_device": "171"},
                    {"ten": "Q171", "ma": "cong_suat_phan_khang_171", "don_vi": "MVar", "sub_device": "171"},
                    {"ten": "U171", "ma": "dien_ap_171", "don_vi": "kV", "sub_device": "171"},
                    {"ten": "I2", "ma": "dong_dien_172", "don_vi": "A", "sub_device": "172"},
                    {"ten": "P172", "ma": "cong_suat_tac_dung_172", "don_vi": "MW", "sub_device": "172"},
                    {"ten": "Q172", "ma": "cong_suat_phan_khang_172", "don_vi": "MVar", "sub_device": "172"},
                    {"ten": "U172", "ma": "dien_ap_172", "don_vi": "kV", "sub_device": "172"},
                ],
            },
            {
                "group": "MBA T1, T2",
                "device_code": "VS.TB.TPP",
                "columns": [
                    {"ten": "Nđ\nổ T1", "ma": "nhiet_do_cuon_day_t1", "don_vi": "°C", "sub_device": "T1"},
                    {"ten": "NPA\nT1", "ma": "nac_phan_ap_t1", "don_vi": "", "sub_device": "T1"},
                    {"ten": "Nđ\nổ T2", "ma": "nhiet_do_cuon_day_t2", "don_vi": "°C", "sub_device": "T2"},
                    {"ten": "NPA\nT2", "ma": "nac_phan_ap_t2", "don_vi": "", "sub_device": "T2"},
                ],
            },
            {
                "group": "Áp suất khí máy cắt 110kV",
                "device_code": "VS.TB.TPP",
                "columns": [
                    {"ten": "131", "ma": "ap_suat_khi_131", "don_vi": "MPa", "sub_device": "131"},
                    {"ten": "132", "ma": "ap_suat_khi_132", "don_vi": "MPa", "sub_device": "132"},
                    {"ten": "171", "ma": "ap_suat_khi_171", "don_vi": "MPa", "sub_device": "171"},
                    {"ten": "172", "ma": "ap_suat_khi_172", "don_vi": "MPa", "sub_device": "172"},
                    {"ten": "112", "ma": "ap_suat_khi_112", "don_vi": "MPa", "sub_device": "112"},
                ],
            },
            {
                "group": "MBA tự dùng TD91",
                "device_code": "VS.TB.TD.LV.TD1",
                "columns": [
                    {"ten": "U", "ma": "dien_ap_td91", "don_vi": "V"},
                    {"ten": "I", "ma": "dong_dien_td91", "don_vi": "A"},
                    {"ten": "P", "ma": "cong_suat_td91", "don_vi": "kW"},
                ],
            },
            {
                "group": "MBA tự dùng TD92",
                "device_code": "VS.TB.TD.LV.TD2",
                "columns": [
                    {"ten": "U", "ma": "dien_ap_td92", "don_vi": "V"},
                    {"ten": "I", "ma": "dong_dien_td92", "don_vi": "A"},
                    {"ten": "P", "ma": "cong_suat_td92", "don_vi": "kW"},
                ],
            },
        ],
    },
}


TRAM_CONFIGS = {
    "SH": {
        "title": "THÔNG SỐ TRẠM 110/22KV",
        "columns": [
            {"ten": "Nhiệt độ MBA T1", "ma": "nhiet_do_mba_t1", "don_vi": "°C", "ma_thiet_bi": "SH.TB.TPP.110.T1"},
            {"ten": "Nấc phân áp MBA T1", "ma": "nac_phan_ap_mba_t1", "don_vi": "", "ma_thiet_bi": "SH.TB.TPP.110.T1"},
            {"ten": "Mức dầu MBA T1", "ma": "muc_dau_mba_t1", "don_vi": "", "ma_thiet_bi": "SH.TB.TPP.110.T1"},
            {"ten": "Nhiệt độ MBA T2", "ma": "nhiet_do_mba_t2", "don_vi": "°C", "ma_thiet_bi": "SH.TB.TPP.110.T2"},
            {"ten": "Nấc phân áp MBA T2", "ma": "nac_phan_ap_mba_t2", "don_vi": "", "ma_thiet_bi": "SH.TB.TPP.110.T2"},
            {"ten": "Mức dầu MBA T2", "ma": "muc_dau_mba_t2", "don_vi": "", "ma_thiet_bi": "SH.TB.TPP.110.T2"},
            {"ten": "Nhiệt độ MBA T3", "ma": "nhiet_do_mba_t3", "don_vi": "°C", "ma_thiet_bi": "SH.TB.TPP.22.T3"},
            {"ten": "Mức dầu MBA T3", "ma": "muc_dau_mba_t3", "don_vi": "", "ma_thiet_bi": "SH.TB.TPP.22.T3"},
            {"ten": "Nhiệt độ MBA T4", "ma": "nhiet_do_mba_t4", "don_vi": "°C", "ma_thiet_bi": "SH.TB.TPP.22.T4"},
            {"ten": "Mức dầu MBA T4", "ma": "muc_dau_mba_t4", "don_vi": "", "ma_thiet_bi": "SH.TB.TPP.22.T4"},
            {"ten": "Nấc phân áp MBA TD91", "ma": "nac_phan_ap_mba_td91", "don_vi": "", "ma_thiet_bi": "SH.TB.TD.LV.TD1"},
            {"ten": "Mức dầu MBA TD91", "ma": "muc_dau_mba_td91", "don_vi": "", "ma_thiet_bi": "SH.TB.TD.LV.TD1"},
            {"ten": "Nấc phân áp MBA TD94", "ma": "nac_phan_ap_mba_td94", "don_vi": "", "ma_thiet_bi": "SH.TB.TD.LV.TD2"},
            {"ten": "Mức dầu MBA TD94", "ma": "muc_dau_mba_td94", "don_vi": "", "ma_thiet_bi": "SH.TB.TD.LV.TD2"},
            {"ten": "Áp suất khí MC 171", "ma": "ap_suat_khi_mc_171", "don_vi": "Mpa", "ma_thiet_bi": "SH.TB.TPP.110.171"},
            {"ten": "Áp suất khí MC 172", "ma": "ap_suat_khi_mc_172", "don_vi": "Mpa", "ma_thiet_bi": "SH.TB.TPP.110.172"},
            {"ten": "Áp suất khí MC 173", "ma": "ap_suat_khi_mc_173", "don_vi": "Mpa", "ma_thiet_bi": "SH.TB.TPP.110.173"},
            {"ten": "Áp suất khí MC 174", "ma": "ap_suat_khi_mc_174", "don_vi": "Mpa", "ma_thiet_bi": "SH.TB.TPP.110.174"},
        ],
    },
}


TOMAY_PARAM_DEVICE_SUFFIX = {
    "ap_luc_nuoc": ".GE",
    "ap_luc_chen_truc": ".TuB.SH",
    "luu_luong_chen_truc": ".TuB.SH",
    "luu_luong_o_huong_tuabin": ".TuB.OH",
    "nhiet_do_o_huong_tuabin": ".TuB.OH",
    "luu_luong_o_huong_may_phat": ".GE.OH",
    "nhiet_do_o_huong_may_phat": ".GE.OH",
    "luu_luong_o_do_may_phat": ".GE.OD",
    "nhiet_do_o_do": ".GE.OD",
    "nhiet_do_o_huong_o_do": ".GE.OD.PD",
    "nhiet_do_dau_o_do": ".GE.OD.BD",
    "luu_luong_lam_mat_may_phat": ".GE",
    "nhiet_do_nuoc_lam_mat_may_phat": ".GE",
    "nhiet_do_khi_mat": ".GE",
    "nhiet_do_khi_nong": ".GE",
    "nhiet_do_cuon_day_stato": ".GE",
    "toc_do": ".GOV.TB3",
    "gioi_han_do_mo_canh_huong": ".TuB.CH",
    "do_mo_canh_huong": ".TuB.CH",
    "do_roi_toc": ".TuB.CH",
}


TOMAY_VS_PARAM_DEVICE_SUFFIX = {
    "nhiet_do_dau_o_do": ".GE.OD",
    "nhiet_do_o_do": ".GE.OD",
    "nhiet_do_o_huong_o_do": ".GE.OH",
    "nhiet_do_cuon_day_stato_1": ".GE.STA",
    "nhiet_do_cuon_day_stato_2": ".GE.STA",
    "nhiet_do_loi_sat_stato_1": ".GE.STA",
    "nhiet_do_loi_sat_stato_2": ".GE.STA",
    "nuoc_lam_mat_dau_vao": ".GE.TDN",
    "nuoc_lam_mat_dau_ra": ".GE.TDN",
    "nhiet_do_khi_mat": ".GE.TDN",
    "nhiet_do_dau_o_huong_tuabin": ".TuB.OH",
    "ap_suat_dau_o_huong_tuabin": ".TuB.OH",
    "nhiet_do_o_huong_1_tuabin": ".TuB.OH",
    "nhiet_do_o_huong_2_tuabin": ".TuB.OH",
    "ap_suat_dau_thuy_luc": ".TL",
    "muc_dau_thuy_luc": ".TL",
    "nhiet_do_dau_thuy_luc": ".TL",
    "toc_do": ".GOV",
    "gioi_han_do_mo": ".GOV",
    "do_mo_kim": ".GOV",
    "do_mo_canh_huong": ".GOV",
    "do_giam_toc": ".GOV",
    "do_gia_tang_tan_so": ".GOV",
}


def normalize_factory_code(factory_code, default="SH"):
    return (factory_code or default).strip().upper()


def _clone_dien_config(config, factory_code):
    cloned = deepcopy(config)
    for group in cloned["layout"]:
        group["device_code"] = (
            group["device_code"]
            .replace("SH.TB", f"{factory_code}.TB")
            .replace("VS.TB", f"{factory_code}.TB")
        )
    return cloned


def get_dien_factory_config(factory_code):
    factory_code = normalize_factory_code(factory_code)
    if factory_code in DIEN_CONFIGS:
        return deepcopy(DIEN_CONFIGS[factory_code])

    config = _clone_dien_config(DIEN_CONFIGS["SH"], factory_code)
    config["title"] = f"BẢNG NHẬP THÔNG SỐ VẬN HÀNH ĐIỆN {factory_code}"
    return config


def has_dien_factory_config(factory_code):
    return bool(normalize_factory_code(factory_code))


def get_tram_factory_config(factory_code):
    factory_code = normalize_factory_code(factory_code)
    if factory_code in TRAM_CONFIGS:
        return deepcopy(TRAM_CONFIGS[factory_code])

    config = deepcopy(TRAM_CONFIGS["SH"])
    config["title"] = f"THÔNG SỐ TRẠM 110/22KV {factory_code}"
    for column in config["columns"]:
        column["ma_thiet_bi"] = column["ma_thiet_bi"].replace("SH.TB", f"{factory_code}.TB")
    return config


def get_tomay_device_suffix(factory_code, param_code, machine_code=""):
    factory_code = normalize_factory_code(factory_code)
    machine_code = (machine_code or "").upper()

    if factory_code == "VS":
        suffix = TOMAY_VS_PARAM_DEVICE_SUFFIX.get(param_code, ".GE")
        if suffix == ".GOV" and machine_code == "H2":
            return ".GOV(new)"
        return suffix

    return TOMAY_PARAM_DEVICE_SUFFIX.get(param_code, ".GE")
