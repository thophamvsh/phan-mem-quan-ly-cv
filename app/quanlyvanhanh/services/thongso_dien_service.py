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

        base_lookup = {
            "thiet_bi": thiet_bi_obj,
            "thoi_diem_nhap": item_data.get("thoi_diem_nhap"),
        }
        code_lookup = dict(base_lookup)
        name_lookup = dict(base_lookup)

        if item_data.get("ma_thong_so"):
            code_lookup["ma_thong_so"] = item_data.get("ma_thong_so")
        if item_data.get("ten_thong_so"):
            name_lookup["ten_thong_so"] = item_data.get("ten_thong_so")

        if item_data.get("gia_tri") in (None, ""):
            delete_qs = ThongSoVanHanh.objects.none()
            if item_data.get("ma_thong_so"):
                delete_qs = delete_qs | ThongSoVanHanh.objects.filter(**code_lookup)
            if item_data.get("ten_thong_so"):
                delete_qs = delete_qs | ThongSoVanHanh.objects.filter(**name_lookup)
            if not user.is_superuser:
                forbidden_exists = delete_qs.filter(nguoi_nhap__isnull=False).exclude(nguoi_nhap=user).exists()
                if forbidden_exists:
                    raise PermissionDenied("Bạn không có quyền xóa một số thông số vận hành vì chúng được nhập bởi người dùng khác.")
            deleted_count += delete_qs.delete()[0]
            continue

        code_qs = ThongSoVanHanh.objects.none()
        if item_data.get("ma_thong_so"):
            code_qs = ThongSoVanHanh.objects.filter(**code_lookup)

        name_obj = None
        if item_data.get("ten_thong_so"):
            name_obj = ThongSoVanHanh.objects.filter(**name_lookup).first()

        target_obj = name_obj or code_qs.first()
        if target_obj:
            if not user.is_superuser and target_obj.nguoi_nhap and target_obj.nguoi_nhap != user:
                raise PermissionDenied("Bạn không có quyền sửa thông số này vì nó được nhập bởi người dùng khác.")
            item_data["nguoi_nhap"] = user
            ThongSoVanHanh.objects.filter(pk=target_obj.pk).update(**item_data)
            updated_count += 1

            duplicate_qs = code_qs.exclude(pk=target_obj.pk)
            if not user.is_superuser:
                forbidden_dup = duplicate_qs.filter(nguoi_nhap__isnull=False).exclude(nguoi_nhap=user).exists()
                if forbidden_dup:
                    raise PermissionDenied("Bạn không có quyền xóa một số bản ghi trùng lặp vì chúng được nhập bởi người dùng khác.")
            deleted_count += duplicate_qs.delete()[0]
        else:
            item_data["nguoi_nhap"] = user
            ThongSoVanHanh.objects.create(**item_data)
            created_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "deleted": deleted_count,
    }
