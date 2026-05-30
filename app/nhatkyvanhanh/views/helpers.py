import unicodedata
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.utils import timezone
from django.db.models import Q
from django.db import transaction

from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi
from thongsothuyvan.models import MucnuocQuytrinh, ThongsoSanxuat
from nhatkyvanhanh.models import (
    SuKien,
    KhacPhucSuKien,
    SogiaonhancaHC,
    SogiaonhancaVH,
    MauChuyenDoiThietBi,
    MauChuyenDoiTBThang,
    SoChuyenDoiTBThang,
    SoAnToanDauGio,
)
from nhatkyvanhanh.permissions import has_profile_permission

HYDROLOGY_FACTORY_CODES = {
    "songhinh": "SH",
    "sh": "SH",
    "vinhson": "VS",
    "vs": "VS",
    "thuongkontum": "TKT",
    "thuong-kon-tum": "TKT",
    "tkt": "TKT",
}


def _normalize_factory_query_value(value):
    if not value:
        return ""
    normalized = unicodedata.normalize("NFD", str(value).replace("đ", "d").replace("Đ", "D"))
    normalized = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return normalized.strip().lower().replace("_", "").replace("-", "").replace(" ", "")


def _factory_from_dashboard_param(value):
    if not value:
        return None

    normalized = _normalize_factory_query_value(value)
    factory_code = HYDROLOGY_FACTORY_CODES.get(normalized, str(value).strip())
    factory = Bang_nha_may.objects.filter(ma_nha_may__iexact=factory_code).first()
    if factory:
        return factory

    for item in Bang_nha_may.objects.all():
        item_code = _normalize_factory_query_value(item.ma_nha_may)
        item_name = _normalize_factory_query_value(item.ten_nha_may)
        if normalized in {item_code, item_name} or normalized in item_name:
            return item

    return None


def _factory_ids_from_dashboard_param(value):
    if not value:
        return []

    normalized = _normalize_factory_query_value(value)
    factory_code = HYDROLOGY_FACTORY_CODES.get(normalized, str(value).strip())
    matched_ids = set(
        Bang_nha_may.objects.filter(ma_nha_may__iexact=factory_code).values_list(
            "id",
            flat=True,
        )
    )

    for item in Bang_nha_may.objects.all():
        item_code = _normalize_factory_query_value(item.ma_nha_may)
        item_name = _normalize_factory_query_value(item.ten_nha_may)
        if normalized in {item_code, item_name} or normalized in item_name:
            matched_ids.add(item.id)
        if normalized == "songhinh" and (item_code == "sh" or "songhinh" in item_name):
            matched_ids.add(item.id)

    return list(matched_ids)


def _is_song_hinh_factory(factory):
    if not factory:
        return False

    code = _normalize_factory_query_value(factory.ma_nha_may)
    name = _normalize_factory_query_value(factory.ten_nha_may)
    return code == "sh" or "songhinh" in name


def _is_song_hinh_dashboard_param(value):
    normalized = _normalize_factory_query_value(value)
    return normalized in {"songhinh", "sh"}


def _normalize_event_status(value):
    normalized = _normalize_factory_query_value(value)
    if normalized in {"dangxuly", "dangxulyxong"}:
        return SuKien.TrangThaiXuLy.DANG_XU_LY
    if normalized in {"xulyxong", "daxuly", "hoanthanh"}:
        return SuKien.TrangThaiXuLy.XU_LY_XONG
    if normalized in {"chuaxuly", "chuaxulyxong", "choxuly", "chua"}:
        return SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG
    return value


def _normalize_event_type(value):
    normalized = _normalize_factory_query_value(value)
    if normalized in {"suco", "sukien"}:
        return SuKien.LoaiSuKien.SU_CO
    if normalized in {"khiemkhuyet", "khuyetdiem", "khiemkhuyetthietbi"}:
        return SuKien.LoaiSuKien.KHIEM_KHUYET
    return value


def _get_song_hinh_factory():
    return (
        Bang_nha_may.objects.filter(ma_nha_may__iexact="SH").first()
        or Bang_nha_may.objects.filter(ten_nha_may__icontains="Sông Hinh").first()
        or Bang_nha_may.objects.filter(ten_nha_may__icontains="Song Hinh").first()
    )


def _find_switch_template_device(factory_code, code_candidates=(), name_terms=()):
    prefix = f"{factory_code}.TB."
    for code in code_candidates:
        device = ThietBi.objects.filter(ma_day_du__iexact=code).first()
        if device:
            return device

    queryset = ThietBi.objects.filter(ma_day_du__istartswith=prefix)
    for term in name_terms:
        queryset = queryset.filter(ten__icontains=term)
    return queryset.order_by("cap", "thu_tu", "ma_day_du").first()


def _create_default_switch_templates(nha_may):
    if not nha_may or not nha_may.ma_nha_may:
        return 0

    factory_code = nha_may.ma_nha_may.upper()
    unit_codes = ["H1", "H2"]
    rows = []
    order = 1

    def add(to_may, nhom, codes=(), terms=()):
        nonlocal order
        device = _find_switch_template_device(factory_code, codes, terms)
        if not device:
            return
        rows.append(
            {
                "to_may": to_may,
                "nhom_thiet_bi": nhom,
                "thiet_bi": device,
                "thu_tu": order,
            }
        )
        order += 1

    for unit in unit_codes:
        to_may = unit
        prefix = f"{factory_code}.TB.{unit}"
        add(to_may, "Bơm nước làm mát", [f"{prefix}.NLM.MOR1"], ["Bơm nước", "01"])
        add(to_may, "Bơm nước làm mát", [f"{prefix}.NLM.MOR2"], ["Bơm nước", "02"])
        add(to_may, "Bơm dầu điều tốc", [f"{prefix}.TL.B1", f"{prefix}.TL.BO1"], ["Bơm dầu", "01"])
        add(to_may, "Bơm dầu điều tốc", [f"{prefix}.TL.B2", f"{prefix}.TL.BO2"], ["Bơm dầu", "02"])
        add(to_may, "Hệ thống điều tốc", [f"{prefix}.GOV.TCC1.A01", f"{prefix}.GOV.TCC2.G11", f"{prefix}.GOV.TB.CPU1"], ["CPU", "01"])
        add(to_may, "Hệ thống điều tốc", [f"{prefix}.GOV.TCC1.A02", f"{prefix}.GOV.TCC2.G12", f"{prefix}.GOV.TB.CPU2"], ["CPU", "02"])
        add(to_may, "Hệ thống điều tốc", [f"{prefix}.GOV.TCC1.0K17", f"{prefix}.GOV.TCC2.G99"], ["Rail #0"])
        add(to_may, "Hệ thống điều tốc", [f"{prefix}.GOV.TCC1.1", f"{prefix}.GOV.TCC2.G100"], ["Rail #1"])
        add(to_may, "Hệ thống kích từ", [f"{prefix}.EXC.ER.A51", f"{prefix}.EXE.AVR.CPU1"], ["CH1"])
        add(to_may, "Hệ thống kích từ", [f"{prefix}.EXC.ER.A53", f"{prefix}.EXE.AVR.CPU2"], ["CH2"])

    add("tu_dung", "Tự dùng", [f"{factory_code}.TB.1.CTTD1"], ["TD91"])
    add("tu_dung", "Tự dùng", [f"{factory_code}.TB.1.CTTD2"], ["TD94"])

    created = 0
    for row in rows:
        _, was_created = MauChuyenDoiThietBi.objects.get_or_create(
            nha_may=nha_may,
            thiet_bi=row["thiet_bi"],
            defaults={
                "to_may": row["to_may"],
                "nhom_thiet_bi": row["nhom_thiet_bi"],
                "thu_tu": row["thu_tu"],
                "dang_su_dung": True,
            },
        )
        created += int(was_created)
    return created


MONTHLY_SWITCH_TEMPLATE_ROWS = [
    ("I", "So lan dong/Cat", "MC", "MC 171", "Lan", 1, 1),
    ("I", "So lan dong/Cat", "MC", "MC 172", "Lan", 1, 2),
    ("I", "So lan dong/Cat", "MC", "MC 173", "Lan", 1, 3),
    ("I", "So lan dong/Cat", "MC", "MC 174", "Lan", 1, 4),
    ("I", "So lan dong/Cat", "MC", "MC 412", "Lan", 1, 5),
    ("I", "So lan dong/Cat", "MC", "MC 471", "Lan", 1, 6),
    ("I", "So lan dong/Cat", "MC", "MC 472", "Lan", 1, 7),
    ("I", "So lan dong/Cat", "MC", "MC 901", "Lan", 1, 8),
    ("I", "So lan dong/Cat", "MC", "MC 902", "Lan", 1, 9),
    ("I", "So lan dong/Cat", "MC", "MC 933", "Lan", 1, 10),
    ("I", "So lan dong/Cat", "MC", "MC 934", "Lan", 1, 11),
    ("I", "So lan dong/Cat", "MC", "MC 941", "Lan", 1, 12),
    ("I", "So lan dong/Cat", "MC", "MC 942", "Lan", 1, 13),
    ("II", "So lan lam viec", "CS", "CS 172", "Lan", 2, 1),
    ("II", "So lan lam viec", "CS", "CS 174", "Lan", 2, 2),
    ("II", "So lan lam viec", "CS", "CS 1T12", "Lan", 2, 3),
    ("II", "So lan lam viec", "CS", "CS 1T22", "Lan", 2, 4),
    ("II", "So lan lam viec", "CS", "CS 1T11", "Lan", 2, 5),
    ("II", "So lan lam viec", "CS", "CS 1T21", "Lan", 2, 6),
    ("II", "So lan lam viec", "CS", "CS 4T3", "Lan", 2, 7),
    ("II", "So lan lam viec", "CS", "CS 4T4", "Lan", 2, 8),
    ("III", "So lan chuyen NPA", "MBA", "MBA T1", "Lan", 3, 1),
    ("III", "So lan chuyen NPA", "MBA", "MBA T2", "Lan", 3, 2),
    ("III", "So lan chuyen NPA", "MBA", "MBA TD91", "Lan", 3, 3),
    ("III", "So lan chuyen NPA", "MBA", "MBA TD94", "Lan", 3, 4),
]


def _find_monthly_switch_template_device(nha_may, device_name):
    compact_name = device_name.replace(" ", "")
    queryset = ThietBi.objects.all()
    if nha_may and nha_may.ma_nha_may:
        factory_code = nha_may.ma_nha_may.upper()
        factory_filter = (
            Q(ma_day_du__istartswith=f"{factory_code}.")
            | Q(nha_may__iexact=factory_code)
        )
        if getattr(nha_may, "ten_nha_may", ""):
            factory_filter |= Q(nha_may__icontains=nha_may.ten_nha_may)
        queryset = queryset.filter(factory_filter)
    return (
        queryset.filter(
            Q(ten__iexact=device_name)
            | Q(ten__icontains=device_name)
            | Q(ma__iexact=compact_name)
            | Q(ma_day_du__icontains=compact_name)
            | Q(ma_day_du__icontains=device_name)
        )
        .order_by("cap", "thu_tu", "ma_day_du")
        .first()
    )


def _create_default_monthly_switch_templates(nha_may):
    if not nha_may:
        return 0

    created = 0
    for ma_nhom, ten_nhom, don_vi_nhom, device_name, don_vi, thu_tu_nhom, thu_tu in MONTHLY_SWITCH_TEMPLATE_ROWS:
        device = _find_monthly_switch_template_device(nha_may, device_name)
        if not device:
            continue
        _, was_created = MauChuyenDoiTBThang.objects.get_or_create(
            nha_may=nha_may,
            thiet_bi=device,
            defaults={
                "ma_nhom": ma_nhom,
                "ten_nhom": ten_nhom,
                "don_vi_nhom": don_vi_nhom,
                "don_vi": don_vi,
                "thu_tu_nhom": thu_tu_nhom,
                "thu_tu": thu_tu,
                "dang_su_dung": True,
            },
        )
        created += int(was_created)
    return created


def _previous_month_values_by_device(so):
    previous_year = so.nam
    previous_month = so.thang - 1
    if previous_month < 1:
        previous_year -= 1
        previous_month = 12

    previous_so = (
        SoChuyenDoiTBThang.objects.filter(
            nha_may=so.nha_may,
            nam=previous_year,
            thang=previous_month,
            ca_truc=so.ca_truc,
        )
        .order_by("-created_at")
        .first()
    )
    if not previous_so:
        return {}
    return {
        item.thiet_bi_id: item.cuoi_thang
        for item in previous_so.chi_tiets.only("thiet_bi_id", "cuoi_thang")
    }


def _month_day_key(date_value):
    return date_value.strftime("%d/%m")


def _month_day_to_order(value):
    try:
        parsed = datetime.strptime(str(value).strip(), "%d/%m")
    except (TypeError, ValueError):
        return None
    return parsed.month * 100 + parsed.day


def _find_muc_nuoc_quy_trinh(date_value):
    day_order = _month_day_to_order(_month_day_key(date_value))
    if day_order is None:
        return None

    for item in MucnuocQuytrinh.objects.filter(nha_may="songhinh"):
        start_order = _month_day_to_order(item.ngay_bat_dau)
        end_order = _month_day_to_order(item.ngay_ket_thuc)
        if start_order is None or end_order is None:
            continue
        if start_order <= end_order and start_order <= day_order <= end_order:
            return item
        if start_order > end_order and (day_order >= start_order or day_order <= end_order):
            return item
    return None


def _decimal_or_none(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_decimal_range(start, end):
    if start is None or end is None:
        return ""
    return f"{start.normalize()}-{end.normalize()}"


def _calculate_bchc_qt(muc_nuoc_ho, muc_nuoc_tu, muc_nuoc_den):
    if muc_nuoc_ho is None or muc_nuoc_tu is None or muc_nuoc_den is None:
        return ""
    if muc_nuoc_ho > muc_nuoc_den:
        return "> 25 m3/s"
    if muc_nuoc_tu <= muc_nuoc_ho <= muc_nuoc_den:
        return "20-25 m3/s"
    return "<20 m3/s"


def _gan_chu_ky_tu_profile(user, model_instance, field_name):
    profile = getattr(user, "profile", None)
    if profile and profile.chu_ky and not getattr(model_instance, field_name):
        setattr(model_instance, field_name, profile.chu_ky.name)


def _lay_chuc_danh_user(user):
    profile = getattr(user, "profile", None)
    return (getattr(profile, "chuc_danh", None) or "").strip()


def _normalize_text(value):
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_marks.casefold().split())


def _la_truong_ca(user):
    return _normalize_text(_lay_chuc_danh_user(user)) == "truong ca"


def _co_quyen_them_dien_bien(user):
    return _la_truong_ca(user) or has_profile_permission(user, "can_add_event_developments")


def _can_edit_event(user, su_kien):
    if has_profile_permission(user, "can_edit_all_operation_events"):
        return True
    return (
        has_profile_permission(user, "can_edit_own_operation_events")
        and su_kien.nguoi_tao_id == user.id
        and not su_kien.ben_ghi_nhan_su_kien_id
        and su_kien.trang_thai == SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG
    )


def _can_delete_event(user, su_kien):
    if has_profile_permission(user, "can_delete_all_operation_events"):
        return True
    return (
        has_profile_permission(user, "can_delete_own_operation_events")
        and su_kien.nguoi_tao_id == user.id
        and not su_kien.ben_ghi_nhan_su_kien_id
    )


def _can_edit_remediation(user, khac_phuc):
    if has_profile_permission(user, "can_edit_all_remediations"):
        return True
    return (
        has_profile_permission(user, "can_edit_own_remediations")
        and khac_phuc.nguoi_tao_id == user.id
    )


def _can_edit_development(user, dien_bien):
    if has_profile_permission(user, "can_edit_all_event_developments"):
        return True
    return (
        has_profile_permission(user, "can_edit_own_event_developments")
        and dien_bien.nguoi_tao_id == user.id
    )


def _dong_bo_chu_ky_so_giao_nhan(so, current_user=None):
    so.dong_bo_chu_ky_tu_user()


def _get_user_display_name(user):
    if not user:
        return ""
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.username or user.email or ""


def _append_unique_name(names, value):
    value = str(value or "").strip()
    if value and value not in names:
        names.append(value)


def _build_admin_shift_duty_display(so_hc):
    names = []
    _append_unique_name(names, _get_user_display_name(so_hc.user_giao_ca))
    for person in so_hc.nguoi_truc_chi_tiets.all():
        _append_unique_name(names, person.ten_nguoi_truc)
    for value in (so_hc.nguoi_truc, so_hc.nguoi_truc_2, so_hc.nguoi_truc_3):
        _append_unique_name(names, value)
    return ", ".join(names)


def _find_overlapping_admin_shift_log(so_vh):
    if not so_vh.thoi_gian_bat_dau_ca or not so_vh.thoi_gian_giao_ca:
        return None

    queryset = (
        SogiaonhancaHC.objects.select_related("user_giao_ca")
        .prefetch_related("nguoi_truc_chi_tiets")
        .filter(
            thoi_gian_bat_dau_ca__isnull=False,
            thoi_gian_bat_dau_ca__lte=so_vh.thoi_gian_giao_ca,
            thoi_gian_giao_ca__gte=so_vh.thoi_gian_bat_dau_ca,
        )
    )
    if so_vh.nha_may_id:
        queryset = queryset.filter(nha_may_id=so_vh.nha_may_id)
    return queryset.order_by("-ngay_truc", "-thoi_gian_bat_dau_ca", "-created_at").first()


def _sync_truc_ktvh_from_admin_shift_log(so_vh):
    so_hc = _find_overlapping_admin_shift_log(so_vh)
    if not so_hc:
        return so_vh

    so_vh.truc_ktvh = _build_admin_shift_duty_display(so_hc)
    return so_vh


def _shift_log_locked(so):
    return bool(so.giao_ca_ky_at and so.nhan_ca_ky_at)


def _shift_log_received(so):
    return bool(so.nhan_ca_ky_at)


def _is_creator_of_shift_log(user, so):
    return bool(
        user
        and user.is_authenticated
        and (so.nguoi_tao_id == user.id or so.user_giao_ca_id == user.id)
    )


def _can_create_shift_detail(user, so):
    return bool(user and user.is_authenticated and so.user_giao_ca_id == user.id)


def _can_update_shift_detail(user, so, chi_tiet):
    return bool(
        _can_create_shift_detail(user, so)
        and chi_tiet.nguoi_tao_id == user.id
    )


def _can_edit_shift_log(user, so):
    return has_profile_permission(user, "can_edit_shift_handover_logs") or _is_creator_of_shift_log(user, so)


def _can_delete_shift_log(user, so):
    return has_profile_permission(user, "can_delete_shift_handover_logs") or _is_creator_of_shift_log(user, so)


def _can_view_shift_directives(user):
    return (
        has_profile_permission(user, "can_view_shift_handover_directives")
        or has_profile_permission(user, "can_view_shift_handover_logs")
    )


def _can_create_shift_directive(user, so=None):
    if has_profile_permission(user, "can_create_shift_handover_directives"):
        return True
    if has_profile_permission(user, "can_edit_shift_handover_logs"):
        return True
    if so and (user.is_superuser or so.user_giao_ca_id == user.id):
        return True
    return False


def _can_update_shift_directive(user, directive):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or directive.nguoi_tao_id == user.id)
    )


def _operation_logbook_locked(item):
    return bool(item.nguoi_xac_nhan_id and item.xac_nhan_at)


def _is_creator_of_operation_logbook(user, item):
    return bool(user and user.is_authenticated and item.nguoi_tao_id == user.id)


def _can_edit_operation_logbook(user, item):
    return (
        has_profile_permission(user, "can_edit_operation_logbooks")
        or _is_creator_of_operation_logbook(user, item)
    )


def _can_delete_operation_logbook(user, item):
    return (
        has_profile_permission(user, "can_delete_operation_logbooks")
        or _is_creator_of_operation_logbook(user, item)
    )


def _is_creator_of_diesel_operation_logbook(user, item):
    return bool(user and user.is_authenticated and item.nguoi_tao_id == user.id)


def _can_edit_diesel_operation_logbook(user, item):
    return _is_creator_of_diesel_operation_logbook(user, item)


def _can_delete_diesel_operation_logbook(user, item):
    return (
        has_profile_permission(user, "can_delete_diesel_operation_logbooks")
        or _is_creator_of_diesel_operation_logbook(user, item)
    )


def _can_edit_weekly_equipment_switch_log(user, item):
    return (
        has_profile_permission(user, "can_edit_weekly_equipment_switch_logs")
        or bool(user and user.is_authenticated and item.nguoi_tao_id == user.id)
    )


def _can_delete_weekly_equipment_switch_log(user, item):
    return (
        has_profile_permission(user, "can_delete_weekly_equipment_switch_logs")
        or bool(user and user.is_authenticated and item.nguoi_tao_id == user.id)
    )


def _can_edit_weekly_equipment_switch_entry(user, lan):
    return (
        has_profile_permission(user, "can_edit_weekly_equipment_switch_logs")
        or bool(user and user.is_authenticated and lan.nguoi_thuc_hien_id == user.id)
    )


def _can_delete_weekly_equipment_switch_entry(user, lan):
    return (
        has_profile_permission(user, "can_delete_weekly_equipment_switch_logs")
        or bool(user and user.is_authenticated and lan.nguoi_thuc_hien_id == user.id)
    )


def _can_edit_monthly_equipment_switch_log(user, item):
    return (
        has_profile_permission(user, "can_edit_monthly_equipment_switch_logs")
        or bool(user and user.is_authenticated and item.nguoi_tao_id == user.id)
    )


def _can_delete_monthly_equipment_switch_log(user, item):
    return (
        has_profile_permission(user, "can_delete_monthly_equipment_switch_logs")
        or bool(user and user.is_authenticated and item.nguoi_tao_id == user.id)
    )


def _get_or_create_latest_khac_phuc(su_kien, nguoi_tao=None):
    latest = su_kien.latest_khac_phuc
    if latest:
        return latest
    return KhacPhucSuKien.objects.create(su_kien=su_kien, nguoi_tao=nguoi_tao)
