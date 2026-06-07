from rest_framework.exceptions import PermissionDenied

from core.factory_scope import (
    filter_queryset_by_factory,
    get_user_factory_name,
    has_all_factory_access,
)
from quanlyvanhanh.models import ThietBi, ThongSoTram110KV
from quanlyvanhanh.serializers import ThongSoTram110KVCreateSerializer


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


def bulk_upsert_thong_so_tram_110kv(user, data_list):
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

        should_delete = item_data.get("gia_tri") in (None, "")

        item_data["thiet_bi"] = thiet_bi_obj.id
        serializer = ThongSoTram110KVCreateSerializer(data=item_data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        if should_delete:
            deleted_count += ThongSoTram110KV.objects.filter(
                thiet_bi=validated_data["thiet_bi"],
                ten_thong_so=validated_data["ten_thong_so"],
                thoi_diem_nhap=validated_data["thoi_diem_nhap"],
                ngay_nhap=validated_data["ngay_nhap"],
            ).delete()[0]
            continue

        _, created = ThongSoTram110KV.objects.update_or_create(
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
