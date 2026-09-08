import logging
from auditlog.signals import post_log
from django.apps import apps
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Cache tên và mã nhà máy để tối ưu hiệu năng
_PLANT_CACHE = {}
_PLANT_DETAILS_CACHE = {}


def get_plant_cache():
    if not _PLANT_CACHE:
        try:
            NhaMay = apps.get_model('tochuc', 'NhaMay')
            for nm in NhaMay.objects.all():
                _PLANT_CACHE[nm.id] = nm.ma_nha_may
        except Exception:
            pass
    return _PLANT_CACHE


def refresh_plant_cache():
    global _PLANT_CACHE, _PLANT_DETAILS_CACHE
    _PLANT_CACHE = {}
    _PLANT_DETAILS_CACHE = {}
    return get_plant_cache()


def get_plant_details(plant_id):
    if not plant_id:
        return None
    if plant_id not in _PLANT_DETAILS_CACHE:
        try:
            NhaMay = apps.get_model('tochuc', 'NhaMay')
            plant = NhaMay.objects.filter(pk=plant_id).values(
                'id', 'ma_nha_may', 'ten_nha_may'
            ).first()
            _PLANT_DETAILS_CACHE[plant_id] = plant
        except Exception:
            return None
    return _PLANT_DETAILS_CACHE.get(plant_id)


def resolve_plant_id(instance, visited=None, depth=0):
    """
    Xác định plant_id (ID nhà máy) của một instance nghiệp vụ.
    Quy tắc:
    1. Kiểm tra trường direct nha_may_id hoặc nha_may_pham_vi_id.
    2. Nếu instance là bản thân model NhaMay -> trả về instance.id.
    3. Kiểm tra các khóa ngoại cha theo danh sách quan hệ phân cấp.
    4. Trả về None nếu không xác định được (coi là unscoped/toàn cục).
    """
    if not instance or not hasattr(instance, '_meta'):
        return None
    if depth > 8:
        return None
    if visited is None:
        visited = set()
    identity = (
        getattr(instance._meta, 'label_lower', instance.__class__.__name__),
        getattr(instance, 'pk', None) or id(instance),
    )
    if identity in visited:
        return None
    visited.add(identity)

    # 1. Trực tiếp có nha_may_id
    if hasattr(instance, 'nha_may_id') and instance.nha_may_id is not None:
        return instance.nha_may_id

    # 2. Trực tiếp có nha_may_pham_vi_id (áp dụng cho DonViToChuc)
    if hasattr(instance, 'nha_may_pham_vi_id') and instance.nha_may_pham_vi_id is not None:
        return instance.nha_may_pham_vi_id

    # 3. Model chính là NhaMay
    if instance.__class__.__name__ == 'NhaMay':
        return instance.pk

    # 4. Kiểm tra các quan hệ cha đã biết
    parent_attrs = (
        'so_giao_nhan_ca',
        'so_giao_nhan_ca_hc',
        'su_kien',
        'so_chuyen_doi',
        'lan_chuyen_doi',
        'kip_truc',
        'lich_truc',
        'ngay_truc',
        'don_vi',
        'bo_phan',
        'mau',
        'nhom',
    )

    for attr in parent_attrs:
        parent = getattr(instance, attr, None)
        if parent is not None:
            plant_id = resolve_plant_id(parent, visited=visited, depth=depth + 1)
            if plant_id is not None:
                return plant_id

    # 5. Nếu không khớp thuộc tính cha cụ thể, duyệt các trường ForeignKey có thể liên kết
    try:
        for field in instance._meta.fields:
            if field.is_relation and field.many_to_one and not field.name.startswith('created_by') and not field.name.startswith('nguoi_'):
                if field.name not in parent_attrs and field.name != 'nha_may':
                    related_obj = getattr(instance, field.name, None)
                    if related_obj and hasattr(related_obj, 'nha_may_id') and related_obj.nha_may_id is not None:
                        return related_obj.nha_may_id
    except Exception:
        pass

    return None


@receiver(post_save, sender='tochuc.NhaMay', dispatch_uid='core.refresh_plant_cache_on_save')
@receiver(post_delete, sender='tochuc.NhaMay', dispatch_uid='core.refresh_plant_cache_on_delete')
def refresh_plant_cache_on_change(**kwargs):
    refresh_plant_cache()


def resolve_plant_and_code(instance):
    """
    Trả về tuple (plant_id, plant_code) cho một instance.
    """
    plant_id = resolve_plant_id(instance)
    if not plant_id:
        return None, None

    cache = get_plant_cache()
    plant_code = cache.get(plant_id)
    if not plant_code:
        # Làm mới cache nếu chưa có (ví dụ nhà máy mới tạo)
        cache = refresh_plant_cache()
        plant_code = cache.get(plant_id)

    return plant_id, plant_code


@receiver(post_log, dispatch_uid="core.log_entry_plant_snapshot_receiver")
def log_entry_plant_snapshot_receiver(sender, instance, log_entry=None, **kwargs):
    """
    Receiver bắt signal post_log của django-auditlog để ghi snapshot
    nhà máy vào trường additional_data của LogEntry.
    Tuyệt đối không ghi vào trường changes (để không làm sai lệch diff nghiệp vụ).
    """
    if not log_entry:
        return

    try:
        current_data = log_entry.additional_data or {}
        if isinstance(current_data, dict) and 'plant_id' in current_data:
            # Đã có snapshot, không ghi đè
            return

        plant_id, plant_code = resolve_plant_and_code(instance)

        if not isinstance(current_data, dict):
            current_data = {}

        current_data['plant_id'] = plant_id
        current_data['plant_code'] = plant_code
        plant = get_plant_details(plant_id)
        current_data['plant_name'] = plant['ten_nha_may'] if plant else None

        # Cập nhật trực tiếp vào database qua update() để không kích hoạt bất kỳ signal nào
        type(log_entry).objects.filter(pk=log_entry.pk).update(additional_data=current_data)
    except Exception as e:
        logger.warning(f"Không thể ghi snapshot nhà máy cho LogEntry {log_entry.pk}: {e}")
