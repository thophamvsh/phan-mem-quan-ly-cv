from rest_framework.exceptions import PermissionDenied

from core.factory_scope import (
    filter_queryset_by_factory,
    get_user_factory_name,
    has_all_factory_access,
)
from quanlyvanhanh.models import ThietBi, ThongSoToMay
from quanlyvanhanh.serializers import ThongSoToMayCreateSerializer

PARAM_DEVICE_SUFFIX = {
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

# Ánh xạ hậu tố cho các thông số tổ máy Vĩnh Sơn (VS)
VS_PARAM_DEVICE_SUFFIX = {
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

def get_specific_thiet_bi(base_device, param_code):
    """
    base_device: ThietBi object (e.g. SH.TB.H1.GE or SH.TB.H1)
    param_code: string (e.g. "nhiet_do_o_huong_tuabin")
    """
    prefix = ".".join(base_device.ma_day_du.split(".")[:3])  # E.g., "SH.TB.H1" hoặc "VS.TB.H1"
    is_vs = prefix.startswith("VS.")

    if is_vs:
        suffix = VS_PARAM_DEVICE_SUFFIX.get(param_code, ".GE")
        # Trường hợp ngoại lệ cho bộ điều tốc tổ máy H2 Vĩnh Sơn
        if suffix == ".GOV" and ".H2" in prefix:
            suffix = ".GOV(new)"
    else:
        suffix = PARAM_DEVICE_SUFFIX.get(param_code, ".GE")

    target_code = f"{prefix}{suffix}"
    try:
        return ThietBi.objects.get(ma_day_du=target_code)
    except ThietBi.DoesNotExist:
        return base_device



def resolve_scoped_thiet_bi(user, item_data):
    thiet_bi_id = item_data.get("thiet_bi") or item_data.get("thiet_bi_id")
    thiet_bi_ma = item_data.get("thiet_bi_ma") or item_data.get("device_code")
    thiet_bi_queryset = filter_queryset_by_factory(
        ThietBi.objects.all(),
        user,
        "nha_may",
        "string",
    )

    if thiet_bi_id:
        return thiet_bi_queryset.filter(id=thiet_bi_id).first()
    if thiet_bi_ma:
        return thiet_bi_queryset.filter(ma_day_du=thiet_bi_ma).first()
    return None


def bulk_upsert_thong_so_to_may(user, data_list):
    created_count = 0
    updated_count = 0
    deleted_count = 0

    for raw_item in data_list:
        item_data = dict(raw_item)

        if not has_all_factory_access(user):
            item_data["nha_may"] = get_user_factory_name(user)

        thiet_bi_obj = resolve_scoped_thiet_bi(user, item_data)
        if not thiet_bi_obj:
            raise PermissionDenied(
                "Bạn không có quyền nhập thông số cho thiết bị này."
            )

        # Ánh xạ thiết bị con chính xác dựa theo mã thông số
        specific_tb = get_specific_thiet_bi(thiet_bi_obj, item_data.get("ma_thong_so"))

        should_delete = item_data.get("gia_tri") in (None, "")

        item_data["thiet_bi"] = specific_tb.id
        serializer = ThongSoToMayCreateSerializer(data=item_data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        if should_delete:
            deleted_count += ThongSoToMay.objects.filter(
                thiet_bi=validated_data["thiet_bi"],
                ten_thong_so=validated_data["ten_thong_so"],
                thoi_diem_nhap=validated_data["thoi_diem_nhap"],
                ngay_nhap=validated_data["ngay_nhap"],
            ).delete()[0]
            continue

        _, created = ThongSoToMay.objects.update_or_create(
            thiet_bi=validated_data["thiet_bi"],
            ten_thong_so=validated_data["ten_thong_so"],
            thoi_diem_nhap=validated_data["thoi_diem_nhap"],
            ngay_nhap=validated_data["ngay_nhap"],
            defaults=validated_data,
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "deleted": deleted_count,
    }
