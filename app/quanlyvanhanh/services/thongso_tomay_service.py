from rest_framework.exceptions import PermissionDenied

from core.factory_scope import (
    filter_queryset_by_factory,
    get_user_factory_name,
    has_all_factory_access,
)
from quanlyvanhanh.models import ThietBi, ThongSoToMay
from quanlyvanhanh.serializers import ThongSoToMayCreateSerializer
from quanlyvanhanh.configs.operation_configs import (
    TOMAY_PARAM_DEVICE_SUFFIX,
    TOMAY_VS_PARAM_DEVICE_SUFFIX,
    get_tomay_device_suffix,
)

PARAM_DEVICE_SUFFIX = TOMAY_PARAM_DEVICE_SUFFIX
VS_PARAM_DEVICE_SUFFIX = TOMAY_VS_PARAM_DEVICE_SUFFIX


def get_specific_thiet_bi(base_device, param_code):
    """
    base_device: ThietBi object (e.g. SH.TB.H1.GE or SH.TB.H1)
    param_code: string (e.g. "nhiet_do_o_huong_tuabin")
    """
    parts = base_device.ma_day_du.split(".")
    prefix = ".".join(parts[:3])  # E.g., "SH.TB.H1" or "VS.TB.H1"
    factory_code = parts[0] if parts else ""
    machine_code = parts[2] if len(parts) > 2 else ""
    suffix = get_tomay_device_suffix(factory_code, param_code, machine_code)

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
            delete_qs = ThongSoToMay.objects.filter(
                thiet_bi=validated_data["thiet_bi"],
                ten_thong_so=validated_data["ten_thong_so"],
                thoi_diem_nhap=validated_data["thoi_diem_nhap"],
                ngay_nhap=validated_data["ngay_nhap"],
            )
            if not user.is_superuser:
                forbidden_exists = delete_qs.filter(nguoi_nhap__isnull=False).exclude(nguoi_nhap=user).exists()
                if forbidden_exists:
                    raise PermissionDenied("Bạn không có quyền xóa thông số này vì nó được nhập bởi người dùng khác.")
            deleted_count += delete_qs.delete()[0]
            continue

        existing_obj = ThongSoToMay.objects.filter(
            thiet_bi=validated_data["thiet_bi"],
            ten_thong_so=validated_data["ten_thong_so"],
            thoi_diem_nhap=validated_data["thoi_diem_nhap"],
            ngay_nhap=validated_data["ngay_nhap"],
        ).first()

        if existing_obj:
            if not user.is_superuser and existing_obj.nguoi_nhap and existing_obj.nguoi_nhap != user:
                raise PermissionDenied("Bạn không có quyền sửa thông số này vì nó được nhập bởi người dùng khác.")

        validated_data["nguoi_nhap"] = user

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
