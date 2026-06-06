from rest_framework.exceptions import PermissionDenied

from core.factory_scope import (
    filter_queryset_by_factory,
    get_user_factory_name,
    has_all_factory_access,
)
from quanlyvanhanh.models import ThietBi, ThongSoVanHanh


def get_scoped_thiet_bi(user, thiet_bi_id=None, thiet_bi_ma=None):
    queryset = filter_queryset_by_factory(
        ThietBi.objects.all(),
        user,
        "nha_may",
        "string",
    )
    if thiet_bi_id:
        return queryset.filter(id=thiet_bi_id).first()
    if thiet_bi_ma:
        return queryset.filter(ma_day_du=thiet_bi_ma).first()
    return None


def bulk_create_thong_so_van_hanh(user, data_list):
    created_count = 0
    updated_count = 0
    deleted_count = 0

    for raw_item in data_list:
        item_data = dict(raw_item)

        if not has_all_factory_access(user):
            item_data["nha_may"] = get_user_factory_name(user)

        thiet_bi_id = item_data.get("thiet_bi") or item_data.get("thiet_bi_id")
        thiet_bi_ma = item_data.get("thiet_bi_ma") or item_data.get("device_code")
        thiet_bi_obj = get_scoped_thiet_bi(user, thiet_bi_id, thiet_bi_ma)
        if not thiet_bi_obj:
            raise PermissionDenied(
                "Ban khong co quyen nhap thong so cho thiet bi nay."
            )

        item_data.pop("thiet_bi", None)
        item_data.pop("thiet_bi_id", None)
        item_data.pop("thiet_bi_ma", None)
        item_data.pop("device_code", None)
        item_data["thiet_bi_id"] = thiet_bi_obj.id

        if item_data.get("gia_tri") in (None, ""):
            deleted_count += ThongSoVanHanh.objects.filter(
                thiet_bi=thiet_bi_obj,
                ten_thong_so=item_data.get("ten_thong_so"),
                thoi_diem_nhap=item_data.get("thoi_diem_nhap"),
            ).delete()[0]
            continue

        _, created = ThongSoVanHanh.objects.update_or_create(
            thiet_bi=thiet_bi_obj,
            ten_thong_so=item_data.get("ten_thong_so"),
            thoi_diem_nhap=item_data.get("thoi_diem_nhap"),
            defaults=item_data,
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
