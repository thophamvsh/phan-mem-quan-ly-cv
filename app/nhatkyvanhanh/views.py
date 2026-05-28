from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
import django_filters
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from core.factory_scope import (
    apply_request_factory_to_serializer,
    filter_queryset_by_factory,
    get_user_factory,
    has_all_factory_access,
)
from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi
from .models import (
    ChiDaoSuKien,
    ChiTietSoGiaoNhanCaHC,
    ChiTietSoGiaoNhanCaVH,
    ChiTietChuyenDoiThietBi,
    ChiTietChuyenDoiTBThang,
    DienBienSuKien,
    KhacPhucSuKien,
    LanChuyenDoiThietBi,
    LuuYChiDaoSoGiaoNhanCaVH,
    MauChuyenDoiThietBi,
    MauChuyenDoiTBThang,
    NguoiTrucSoGiaoNhanCaHC,
    SoBCHCSongHinh,
    SoChuyenDoiTBThang,
    SoChuyenDoiThietBiTuan,
    Sonhatkyvanhanh,
    SonhatkyvanhanhDiesel,
    SuKien,
    SogiaonhancaHC,
    SogiaonhancaVH,
    SoAnToanDauGio
)
from .serializers import (
    ChiDaoSuKienSerializer,
    ChiTietSoGiaoNhanCaHCSerializer,
    ChiTietSoGiaoNhanCaVHSerializer,
    ChiTietChuyenDoiThietBiSerializer,
    ChiTietChuyenDoiTBThangSerializer,
    DienBienSuKienSerializer,
    KhacPhucSuKienSerializer,
    LanChuyenDoiThietBiSerializer,
    LuuYChiDaoSoGiaoNhanCaVHSerializer,
    MauChuyenDoiThietBiSerializer,
    MauChuyenDoiTBThangSerializer,
    NhatKySuKienSerializer,
    NguoiTrucSoGiaoNhanCaHCSerializer,
    SoBCHCSongHinhSerializer,
    SoChuyenDoiTBThangSerializer,
    SoChuyenDoiThietBiTuanSerializer,
    SonhatkyvanhanhDieselSerializer,
    SonhatkyvanhanhSerializer,
    SogiaonhancaHCSerializer,
    SogiaonhancaVHSerializer,
    user_can_edit_chi_dao,
    SoAnToanSerializer
)
from thongsothuyvan.models import MucnuocQuytrinh, ThongsoSanxuat
from .permissions import (
    CanAcknowledgeOperationEvents,
    CanConfirmOperationEvents,
    CanConfirmOperationLogbooks,
    CanCreateAdminShiftHandoverLogs,
    CanCreateBCHCSongHinh,
    CanCreateDieselOperationLogbooks,
    CanCreateMonthlyEquipmentSwitchLogs,
    CanCreateOperationLogbooks,
    CanCreateWeeklyEquipmentSwitchLogs,
    CanCreateShiftHandoverLogs,
    CanCreateOperationEvents,
    CanProcessOperationEvents,
    CanReceiveAdminShiftHandoverLogs,
    CanReceiveShiftHandoverLogs,
    CanViewAdminShiftHandoverLogs,
    CanViewBCHCSongHinh,
    CanViewDieselOperationLogbooks,
    CanViewMonthlyEquipmentSwitchLogs,
    CanViewOperationLogbooks,
    CanViewWeeklyEquipmentSwitchLogs,
    CanViewShiftHandoverLogs,
    CanViewOperationEvents,
    has_profile_permission,
)

User = get_user_model()

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


class NhatKySuKienFilterSet(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name="id")
    ngay_xay_ra = django_filters.DateFilter(
        field_name="thoi_gian_xay_ra",
        lookup_expr="date",
    )
    ngay_xay_ra_tu = django_filters.DateFilter(
        field_name="thoi_gian_xay_ra",
        lookup_expr="date__gte",
    )
    ngay_xay_ra_den = django_filters.DateFilter(
        field_name="thoi_gian_xay_ra",
        lookup_expr="date__lte",
    )
    ben_ghi_nhan_su_kien = django_filters.ModelChoiceFilter(
        queryset=User.objects.all()
    )
    ben_xu_ly_su_kien_thiet_bi = django_filters.ModelChoiceFilter(
        field_name="khac_phuc_su_kiens__ben_xu_ly_su_kien_thiet_bi",
        queryset=User.objects.all(),
    )

    class Meta:
        model = SuKien
        fields = [
            "nha_may",
            "thiet_bi",
            "id",
            "loai",
            "trang_thai",
            "ben_ghi_nhan_su_kien",
            "ben_xu_ly_su_kien_thiet_bi",
            "ngay_xay_ra",
            "ngay_xay_ra_tu",
            "ngay_xay_ra_den",
        ]


class NhatKySuKienViewSet(viewsets.ModelViewSet):
    serializer_class = NhatKySuKienSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = NhatKySuKienFilterSet
    search_fields = [
        "ten_he_thong_thiet_bi",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "hien_tuong_dien_bien",
        "phan_tich_nguyen_nhan",
        "bao_cho",
        "ben_ghi_nhan_su_kien__email",
        "ben_ghi_nhan_su_kien__username",
        "khac_phuc_su_kiens__ben_xu_ly_su_kien_thiet_bi__email",
        "khac_phuc_su_kiens__ben_xu_ly_su_kien_thiet_bi__username",
    ]
    ordering_fields = ["thoi_gian_xay_ra", "created_at", "updated_at", "latest_thoi_gian_xu_ly"]
    ordering = ["-thoi_gian_xay_ra", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewOperationEvents]
        if self.action == "create":
            permission_classes = [CanCreateOperationEvents]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [CanViewOperationEvents]
        elif self.action == "ghi_nhan_su_kien":
            permission_classes = [CanAcknowledgeOperationEvents]
        elif self.action in ["tao_khac_phuc", "cap_nhat_khac_phuc", "xu_ly_xong"]:
            permission_classes = [CanProcessOperationEvents]
        elif self.action == "xac_nhan_xu_ly":
            permission_classes = [CanConfirmOperationEvents]
        elif self.action == "tao_dien_bien":
            permission_classes = [CanViewOperationEvents]
        elif self.action == "cap_nhat_dien_bien":
            permission_classes = [CanViewOperationEvents]
        elif self.action == "tao_chi_dao":
            permission_classes = [CanViewOperationEvents]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = self._build_event_queryset()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def _build_event_queryset(self):
        latest_khac_phuc = KhacPhucSuKien.objects.filter(
            su_kien_id=OuterRef("pk")
        ).order_by("-thoi_gian_xu_ly", "-created_at")

        return (
            SuKien.objects.select_related(
                "nha_may",
                "thiet_bi",
                "nguoi_tao",
                "nguoi_chi_dao",
                "ben_ghi_nhan_su_kien",
            )
            .prefetch_related(
                "chi_dao_su_kiens",
                "chi_dao_su_kiens__nguoi_chi_dao",
                "dien_bien_su_kiens",
                "dien_bien_su_kiens__nguoi_tao",
                "khac_phuc_su_kiens",
                "khac_phuc_su_kiens__nguoi_tao",
                "khac_phuc_su_kiens__ben_xu_ly_su_kien_thiet_bi",
                "khac_phuc_su_kiens__nguoi_xac_nhan_xu_ly",
            )
            .annotate(
                latest_thoi_gian_xu_ly=Subquery(latest_khac_phuc.values("thoi_gian_xu_ly")[:1])
            )
            .distinct()
        )

    def perform_create(self, serializer):
        serializer.save(
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk"),
        )

    def perform_update(self, serializer):
        request_fields = {
            key
            for key in self.request.data.keys()
            if key not in {"csrfmiddlewaretoken"}
        }
        is_chi_dao_only_update = request_fields and request_fields <= {"chi_dao"}
        if (
            not _can_edit_event(self.request.user, serializer.instance)
            and not (is_chi_dao_only_update and user_can_edit_chi_dao(self.request.user))
        ):
            raise PermissionDenied("Ban khong co quyen chinh sua su kien nay.")
        if is_chi_dao_only_update and not _can_edit_event(self.request.user, serializer.instance):
            serializer.save()
            return
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk"),
        )

    @action(detail=True, methods=["post"], url_path="chi-dao")
    def tao_chi_dao(self, request, pk=None):
        su_kien = self.get_object()
        if not user_can_edit_chi_dao(request.user):
            raise PermissionDenied("Chi lanh dao moi duoc cap nhat noi dung chi dao.")

        serializer = ChiDaoSuKienSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        chi_dao = serializer.save(
            su_kien=su_kien,
            nguoi_chi_dao=request.user,
            chuc_danh_nguoi_chi_dao=_lay_chuc_danh_user(request.user),
        )

        # Keep legacy fields populated for screens/reports that still read SuKien.chi_dao.
        su_kien.chi_dao = chi_dao.noi_dung
        su_kien.nguoi_chi_dao = request.user
        su_kien.chu_ky_nguoi_chi_dao = chi_dao.chu_ky_nguoi_chi_dao
        su_kien.save(update_fields=["chi_dao", "nguoi_chi_dao", "chu_ky_nguoi_chi_dao", "updated_at"])
        return Response(
            ChiDaoSuKienSerializer(chi_dao, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        if not _can_delete_event(self.request.user, instance):
            raise PermissionDenied("Ban khong co quyen xoa su kien nay.")
        instance.delete()

    @action(detail=False, methods=["get"], url_path="dashboard-summary")
    def dashboard_summary(self, request):
        date_str = request.query_params.get("date")
        try:
            target_date = (
                datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str
                else timezone.localdate()
            )
        except ValueError:
            return Response(
                {"detail": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        year = int(request.query_params.get("year") or target_date.year)
        nhamay_param = request.query_params.get("nhamay")
        factory = _factory_from_dashboard_param(nhamay_param)
        factory_ids = _factory_ids_from_dashboard_param(nhamay_param)
        loai = request.query_params.get("loai")
        scope = request.query_params.get("scope") or "ytd"

        events_qs = self._build_event_queryset()
        if scope != "all":
            events_qs = events_qs.filter(
                thoi_gian_xay_ra__date__gte=datetime(year, 1, 1).date(),
            )
            if scope != "year":
                events_qs = events_qs.filter(thoi_gian_xay_ra__date__lte=target_date)
        logbooks_qs = Sonhatkyvanhanh.objects.all()

        if factory_ids:
            factory_query = Q(nha_may_id__in=factory_ids)
            if _is_song_hinh_factory(factory) or _is_song_hinh_dashboard_param(nhamay_param):
                factory_query |= Q(nha_may__isnull=True)
            if not has_all_factory_access(request.user):
                user_factory = get_user_factory(request.user)
                if not user_factory or user_factory.id not in factory_ids:
                    events_qs = events_qs.none()
                else:
                    events_qs = events_qs.filter(factory_query)
            else:
                events_qs = events_qs.filter(factory_query)
            logbooks_qs = logbooks_qs.filter(nha_may_id__in=factory_ids)
        else:
            events_qs = filter_queryset_by_factory(
                events_qs,
                request.user,
                "nha_may",
                "fk",
            )
            logbooks_qs = filter_queryset_by_factory(
                logbooks_qs,
                request.user,
                "nha_may",
                "fk",
            )

        base_status_counts = {
            SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG: 0,
            SuKien.TrangThaiXuLy.DANG_XU_LY: 0,
            SuKien.TrangThaiXuLy.XU_LY_XONG: 0,
        }
        base_type_counts = {
            SuKien.LoaiSuKien.SU_CO: 0,
            SuKien.LoaiSuKien.KHIEM_KHUYET: 0,
        }
        status_by_type = {
            event_type: dict(base_status_counts)
            for event_type in base_type_counts.keys()
        }

        for item in events_qs.values("trang_thai").annotate(total=Count("id")):
            status = _normalize_event_status(item["trang_thai"])
            if status in base_status_counts:
                base_status_counts[status] += item["total"]

        for item in events_qs.values("loai").annotate(total=Count("id")):
            event_type = _normalize_event_type(item["loai"])
            if event_type in base_type_counts:
                base_type_counts[event_type] += item["total"]

        for item in events_qs.values("loai", "trang_thai").annotate(total=Count("id")):
            event_type = _normalize_event_type(item["loai"])
            status = _normalize_event_status(item["trang_thai"])
            if event_type in status_by_type and status in status_by_type[event_type]:
                status_by_type[event_type][status] += item["total"]

        filtered_events_qs = events_qs
        if loai in dict(SuKien.LoaiSuKien.choices):
            filtered_events_qs = events_qs.filter(loai=loai)

        selected_status_counts = dict(base_status_counts)
        if loai in status_by_type:
            selected_status_counts = dict(status_by_type[loai])

        open_events = (
            filtered_events_qs.filter(
                trang_thai__in=[
                    SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
                    SuKien.TrangThaiXuLy.DANG_XU_LY,
                ]
            )
            .order_by("-thoi_gian_xay_ra", "-created_at")[:8]
        )

        serializer = self.get_serializer(open_events, many=True)
        operation_log_count = logbooks_qs.filter(thoi_gian_tao__date=target_date).count()

        return Response(
            {
                "date": target_date.isoformat(),
                "year": year,
                "operation_log_count": operation_log_count,
                "has_operation_log": operation_log_count > 0,
                "status_counts": {
                    "chua_xu_ly_xong": selected_status_counts[SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG],
                    "dang_xu_ly": selected_status_counts[SuKien.TrangThaiXuLy.DANG_XU_LY],
                    "xu_ly_xong": selected_status_counts[SuKien.TrangThaiXuLy.XU_LY_XONG],
                },
                "type_counts": {
                    "su_co": base_type_counts[SuKien.LoaiSuKien.SU_CO],
                    "khiem_khuyet": base_type_counts[SuKien.LoaiSuKien.KHIEM_KHUYET],
                },
                "status_by_type": {
                    "su_co": {
                        "chua_xu_ly_xong": status_by_type[SuKien.LoaiSuKien.SU_CO][SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG],
                        "dang_xu_ly": status_by_type[SuKien.LoaiSuKien.SU_CO][SuKien.TrangThaiXuLy.DANG_XU_LY],
                        "xu_ly_xong": status_by_type[SuKien.LoaiSuKien.SU_CO][SuKien.TrangThaiXuLy.XU_LY_XONG],
                    },
                    "khiem_khuyet": {
                        "chua_xu_ly_xong": status_by_type[SuKien.LoaiSuKien.KHIEM_KHUYET][SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG],
                        "dang_xu_ly": status_by_type[SuKien.LoaiSuKien.KHIEM_KHUYET][SuKien.TrangThaiXuLy.DANG_XU_LY],
                        "xu_ly_xong": status_by_type[SuKien.LoaiSuKien.KHIEM_KHUYET][SuKien.TrangThaiXuLy.XU_LY_XONG],
                    },
                },
                "open_events": serializer.data,
            }
        )

    @action(detail=True, methods=["post"], url_path="khac-phuc")
    def tao_khac_phuc(self, request, pk=None):
        su_kien = self.get_object()
        if su_kien.nguoi_tao_id and su_kien.nguoi_tao_id == request.user.id:
            return Response(
                {"detail": "User tao moi su kien khong duoc phep tu xu ly su kien nay."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not su_kien.ben_ghi_nhan_su_kien_id:
            return Response(
                {"detail": "Can ghi nhan su kien truoc khi xu ly."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if su_kien.trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG:
            return Response(
                {"detail": "Su kien da xu ly xong, khong the tao them ban ghi khac phuc."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data.copy()
        payload["su_kien"] = str(su_kien.id)
        if not payload.get("ben_xu_ly_su_kien_thiet_bi"):
            payload["ben_xu_ly_su_kien_thiet_bi"] = str(request.user.id)

        serializer = KhacPhucSuKienSerializer(data=payload, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        khac_phuc = serializer.save(nguoi_tao=request.user)

        trang_thai = request.data.get("trang_thai")
        if trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG and not khac_phuc.thoi_gian_xu_ly:
            khac_phuc.thoi_gian_xu_ly = timezone.now()

        if khac_phuc.ben_xu_ly_su_kien_thiet_bi:
            _gan_chu_ky_tu_profile(
                khac_phuc.ben_xu_ly_su_kien_thiet_bi,
                khac_phuc,
                "chu_ky_ben_xu_ly_su_kien_thiet_bi",
            )
        khac_phuc.save()

        if trang_thai in [SuKien.TrangThaiXuLy.DANG_XU_LY, SuKien.TrangThaiXuLy.XU_LY_XONG]:
            su_kien.trang_thai = trang_thai
        else:
            su_kien.trang_thai = SuKien.TrangThaiXuLy.DANG_XU_LY
        su_kien.save()

        response_serializer = self.get_serializer(su_kien)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"khac-phuc/(?P<khac_phuc_id>[^/.]+)")
    def cap_nhat_khac_phuc(self, request, pk=None, khac_phuc_id=None):
        su_kien = self.get_object()
        try:
            khac_phuc = su_kien.khac_phuc_su_kiens.get(pk=khac_phuc_id)
        except KhacPhucSuKien.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay ban ghi khac phuc."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if khac_phuc.nguoi_xac_nhan_xu_ly_id:
            return Response(
                {"detail": "Ban ghi khac phuc da duoc xac nhan, khong the chinh sua."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if khac_phuc.nguoi_tao_id and not _can_edit_remediation(request.user, khac_phuc):
            return Response(
                {
                    "detail": "Ban khong co quyen chinh sua noi dung khac phuc nay."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not khac_phuc.nguoi_tao_id:
            khac_phuc.nguoi_tao = request.user
            khac_phuc.save(update_fields=["nguoi_tao"])

        payload = request.data.copy()
        payload["su_kien"] = str(su_kien.id)
        if not payload.get("ben_xu_ly_su_kien_thiet_bi") and not khac_phuc.ben_xu_ly_su_kien_thiet_bi_id:
            payload["ben_xu_ly_su_kien_thiet_bi"] = str(request.user.id)

        serializer = KhacPhucSuKienSerializer(
            khac_phuc,
            data=payload,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        khac_phuc = serializer.save()

        if khac_phuc.ben_xu_ly_su_kien_thiet_bi:
            _gan_chu_ky_tu_profile(
                khac_phuc.ben_xu_ly_su_kien_thiet_bi,
                khac_phuc,
                "chu_ky_ben_xu_ly_su_kien_thiet_bi",
            )

        trang_thai = request.data.get("trang_thai")
        if trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG and not khac_phuc.thoi_gian_xu_ly:
            khac_phuc.thoi_gian_xu_ly = timezone.now()
        khac_phuc.save()

        if trang_thai in [SuKien.TrangThaiXuLy.DANG_XU_LY, SuKien.TrangThaiXuLy.XU_LY_XONG]:
            su_kien.trang_thai = trang_thai
            su_kien.save()

        response_serializer = self.get_serializer(su_kien)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ghi_nhan_su_kien(self, request, pk=None):
        su_kien = self.get_object()
        if su_kien.nguoi_tao_id and su_kien.nguoi_tao_id == request.user.id:
            return Response(
                {"detail": "User tao moi su kien khong duoc phep ghi nhan su kien cua minh."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not su_kien.ben_ghi_nhan_su_kien_id:
            su_kien.ben_ghi_nhan_su_kien = request.user
        if su_kien.ben_ghi_nhan_su_kien_id == request.user.id:
            _gan_chu_ky_tu_profile(request.user, su_kien, "chu_ky_ben_ghi_nhan_su_kien")
        elif su_kien.ben_ghi_nhan_su_kien:
            _gan_chu_ky_tu_profile(
                su_kien.ben_ghi_nhan_su_kien,
                su_kien,
                "chu_ky_ben_ghi_nhan_su_kien",
            )
        su_kien.save()
        serializer = self.get_serializer(su_kien)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="dien-bien")
    def tao_dien_bien(self, request, pk=None):
        su_kien = self.get_object()
        if not _co_quyen_them_dien_bien(request.user):
            return Response(
                {"detail": "Ban khong co quyen them dien bien su kien."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not su_kien.ben_ghi_nhan_su_kien_id:
            return Response(
                {"detail": "Can ghi nhan su kien truoc khi them dien bien."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if su_kien.trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG:
            return Response(
                {"detail": "Su kien da xu ly xong, khong the them dien bien."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data.copy()
        payload["su_kien"] = str(su_kien.id)
        serializer = DienBienSuKienSerializer(
            data=payload,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            nguoi_tao=request.user,
            chuc_danh_nguoi_tao=_lay_chuc_danh_user(request.user),
        )

        response_serializer = self.get_serializer(su_kien)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"dien-bien/(?P<dien_bien_id>[^/.]+)")
    def cap_nhat_dien_bien(self, request, pk=None, dien_bien_id=None):
        su_kien = self.get_object()
        try:
            dien_bien = su_kien.dien_bien_su_kiens.get(pk=dien_bien_id)
        except DienBienSuKien.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay dien bien su kien."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if su_kien.trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG:
            return Response(
                {"detail": "Su kien da xu ly xong, khong the chinh sua dien bien."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if dien_bien.nguoi_tao_id and not _can_edit_development(request.user, dien_bien):
            return Response(
                {"detail": "Ban khong co quyen chinh sua dien bien su kien nay."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not dien_bien.nguoi_tao_id:
            dien_bien.nguoi_tao = request.user
            dien_bien.chuc_danh_nguoi_tao = _lay_chuc_danh_user(request.user)
            dien_bien.save(update_fields=["nguoi_tao", "chuc_danh_nguoi_tao"])
        elif not dien_bien.chuc_danh_nguoi_tao:
            dien_bien.chuc_danh_nguoi_tao = _lay_chuc_danh_user(dien_bien.nguoi_tao)
            dien_bien.save(update_fields=["chuc_danh_nguoi_tao"])

        payload = request.data.copy()
        payload["su_kien"] = str(su_kien.id)
        serializer = DienBienSuKienSerializer(
            dien_bien,
            data=payload,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = self.get_serializer(su_kien)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def xu_ly_xong(self, request, pk=None):
        su_kien = self.get_object()
        if su_kien.nguoi_tao_id and su_kien.nguoi_tao_id == request.user.id:
            return Response(
                {"detail": "User tao moi su kien khong duoc phep tu xu ly su kien nay."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not su_kien.ben_ghi_nhan_su_kien_id:
            return Response(
                {"detail": "Can ghi nhan su kien truoc khi xu ly."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        su_kien.trang_thai = SuKien.TrangThaiXuLy.XU_LY_XONG
        _gan_chu_ky_tu_profile(su_kien.ben_ghi_nhan_su_kien, su_kien, "chu_ky_ben_ghi_nhan_su_kien")
        khac_phuc = _get_or_create_latest_khac_phuc(su_kien, request.user)
        if khac_phuc.nguoi_tao_id and not _can_edit_remediation(request.user, khac_phuc):
            return Response(
                {
                    "detail": "Ban khong co quyen chinh sua noi dung khac phuc nay."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not khac_phuc.nguoi_tao_id:
            khac_phuc.nguoi_tao = request.user
        if not khac_phuc.thoi_gian_xu_ly:
            khac_phuc.thoi_gian_xu_ly = timezone.now()
        if not khac_phuc.ben_xu_ly_su_kien_thiet_bi_id:
            khac_phuc.ben_xu_ly_su_kien_thiet_bi = request.user
        if khac_phuc.ben_xu_ly_su_kien_thiet_bi:
            _gan_chu_ky_tu_profile(
                khac_phuc.ben_xu_ly_su_kien_thiet_bi,
                khac_phuc,
                "chu_ky_ben_xu_ly_su_kien_thiet_bi",
            )
        su_kien.save()
        khac_phuc.save()
        serializer = self.get_serializer(su_kien)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def xac_nhan_xu_ly(self, request, pk=None):
        su_kien = self.get_object()
        khac_phuc = su_kien.latest_khac_phuc

        if su_kien.trang_thai not in [
            SuKien.TrangThaiXuLy.DANG_XU_LY,
            SuKien.TrangThaiXuLy.XU_LY_XONG,
        ]:
            return Response(
                {"detail": "Su kien phai dang xu ly hoac xu ly xong truoc khi xac nhan."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not khac_phuc:
            return Response(
                {"detail": "Can co noi dung khac phuc truoc khi xac nhan."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            khac_phuc.ben_xu_ly_su_kien_thiet_bi_id
            and khac_phuc.ben_xu_ly_su_kien_thiet_bi_id == request.user.id
        ):
            return Response(
                {"detail": "User dang xu ly su kien khong duoc phep tu xac nhan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not khac_phuc.nguoi_xac_nhan_xu_ly_id:
            khac_phuc.nguoi_xac_nhan_xu_ly = request.user
        if khac_phuc.nguoi_xac_nhan_xu_ly:
            _gan_chu_ky_tu_profile(
                khac_phuc.nguoi_xac_nhan_xu_ly,
                khac_phuc,
                "chu_ky_nguoi_xac_nhan_xu_ly",
            )
        khac_phuc.save()
        serializer = self.get_serializer(su_kien)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SonhatkyvanhanhFilterSet(django_filters.FilterSet):
    ngay_tao = django_filters.DateFilter(
        field_name="thoi_gian_tao",
        lookup_expr="date",
    )
    ngay_tao_tu = django_filters.DateFilter(
        field_name="thoi_gian_tao",
        lookup_expr="date__gte",
    )
    ngay_tao_den = django_filters.DateFilter(
        field_name="thoi_gian_tao",
        lookup_expr="date__lte",
    )

    class Meta:
        model = Sonhatkyvanhanh
        fields = [
            "nha_may",
            "trang_thai",
            "ngay_tao",
            "ngay_tao_tu",
            "ngay_tao_den",
            "nguoi_tao",
            "nguoi_xac_nhan",
        ]


class SonhatkyvanhanhViewSet(viewsets.ModelViewSet):
    serializer_class = SonhatkyvanhanhSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SonhatkyvanhanhFilterSet
    search_fields = [
        "noi_dung_tao",
        "nguoi_tao__email",
        "nguoi_tao__username",
        "nguoi_xac_nhan__email",
        "nguoi_xac_nhan__username",
    ]
    ordering_fields = ["thoi_gian_tao", "created_at", "updated_at"]
    ordering = ["-thoi_gian_tao", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewOperationLogbooks]
        if self.action == "create":
            permission_classes = [CanCreateOperationLogbooks]
        elif self.action == "xac_nhan":
            permission_classes = [CanConfirmOperationLogbooks]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = Sonhatkyvanhanh.objects.select_related(
            "nha_may",
            "nguoi_tao",
            "nguoi_xac_nhan",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        item = serializer.save(
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_update(self, serializer):
        if _operation_logbook_locked(serializer.instance):
            raise PermissionDenied("So nhat ky van hanh da duoc xac nhan, khong duoc chinh sua.")
        if not _can_edit_operation_logbook(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so nhat ky van hanh.")
        item = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_destroy(self, instance):
        if _operation_logbook_locked(instance):
            raise PermissionDenied("So nhat ky van hanh da duoc xac nhan, khong duoc xoa.")
        if not _can_delete_operation_logbook(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so nhat ky van hanh.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def xac_nhan(self, request, pk=None):
        item = self.get_object()
        if item.nguoi_tao_id == request.user.id:
            return Response(
                {"detail": "Nguoi tao so khong duoc tu xac nhan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if item.nguoi_xac_nhan_id and item.nguoi_xac_nhan_id != request.user.id:
            return Response(
                {"detail": "So nhat ky van hanh da duoc user khac xac nhan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not item.xac_nhan_at:
            item.nguoi_xac_nhan = request.user
            item.xac_nhan_at = timezone.now()
            item.save()
        serializer = self.get_serializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SonhatkyvanhanhDieselFilterSet(django_filters.FilterSet):
    ngay_tu = django_filters.DateFilter(field_name="thoi_gian", lookup_expr="date__gte")
    ngay_den = django_filters.DateFilter(field_name="thoi_gian", lookup_expr="date__lte")

    class Meta:
        model = SonhatkyvanhanhDiesel
        fields = ["nha_may", "ca_truc", "ngay_tu", "ngay_den", "nguoi_tao"]


class SonhatkyvanhanhDieselViewSet(viewsets.ModelViewSet):
    serializer_class = SonhatkyvanhanhDieselSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SonhatkyvanhanhDieselFilterSet
    search_fields = [
        "noi_dung",
        "ca_truc",
        "nguoi_tao__email",
        "nguoi_tao__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["thoi_gian", "created_at", "updated_at"]
    ordering = ["-thoi_gian", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewDieselOperationLogbooks]
        if self.action == "create":
            permission_classes = [CanCreateDieselOperationLogbooks]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SonhatkyvanhanhDiesel.objects.select_related(
            "nha_may",
            "nguoi_tao",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        item = serializer.save(
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_update(self, serializer):
        if not _can_edit_diesel_operation_logbook(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so nhat ky van hanh Diesel.")
        item = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_destroy(self, instance):
        if not _can_delete_diesel_operation_logbook(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so nhat ky van hanh Diesel.")
        return super().perform_destroy(instance)


class SoBCHCSongHinhFilterSet(django_filters.FilterSet):
    ngay_tu = django_filters.DateFilter(field_name="ngay_dong_bo", lookup_expr="gte")
    ngay_den = django_filters.DateFilter(field_name="ngay_dong_bo", lookup_expr="lte")

    class Meta:
        model = SoBCHCSongHinh
        fields = ["ngay_dong_bo", "ngay_tu", "ngay_den", "nguoi_dong_bo"]


class SoBCHCSongHinhViewSet(viewsets.ModelViewSet):
    serializer_class = SoBCHCSongHinhSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoBCHCSongHinhFilterSet
    search_fields = [
        "nguyen_nhan_khong_dap_ung",
        "nguoi_dong_bo__email",
        "nguoi_dong_bo__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["ngay_dong_bo", "created_at", "updated_at"]
    ordering = ["-ngay_dong_bo", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewBCHCSongHinh]
        if self.action in ["create", "dong_bo"]:
            permission_classes = [CanCreateBCHCSongHinh]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SoBCHCSongHinh.objects.select_related(
            "nha_may",
            "nguoi_dong_bo",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        item = serializer.save(
            nha_may=_get_song_hinh_factory(),
            nguoi_dong_bo=self.request.user,
        )
        item.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        if not (
            has_profile_permission(user, "can_edit_bchc_song_hinh")
            or instance.nguoi_dong_bo_id == user.id
        ):
            raise PermissionDenied("Chi user dong bo hoac user co quyen moi duoc cap nhat so BCHC Song Hinh.")
        item = serializer.save()
        item.save()

    def perform_destroy(self, instance):
        if not (
            has_profile_permission(self.request.user, "can_edit_bchc_song_hinh")
            or instance.nguoi_dong_bo_id == self.request.user.id
        ):
            raise PermissionDenied("Chi user dong bo hoac user co quyen moi duoc xoa so BCHC Song Hinh.")
        return super().perform_destroy(instance)

    @action(detail=False, methods=["post"], url_path="dong-bo")
    def dong_bo(self, request):
        ngay_dong_bo = request.data.get("ngay_dong_bo") or request.data.get("date")
        if not ngay_dong_bo:
            return Response(
                {"detail": "Thieu ngay_dong_bo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sync_date = datetime.strptime(str(ngay_dong_bo), "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "ngay_dong_bo phai co dinh dang YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        san_xuat = (
            ThongsoSanxuat.objects.filter(nha_may="songhinh", thoi_gian__date=sync_date)
            .order_by("-thoi_gian")
            .first()
        )
        if not san_xuat:
            return Response(
                {"detail": "Khong co du lieu ThongsoSanxuat Song Hinh cho ngay nay."},
                status=status.HTTP_404_NOT_FOUND,
            )

        quy_trinh = _find_muc_nuoc_quy_trinh(sync_date)
        muc_nuoc_tu = _decimal_or_none(getattr(quy_trinh, "muc_nuoc_bat_dau", None))
        muc_nuoc_den = _decimal_or_none(getattr(quy_trinh, "muc_nuoc_ket_thuc", None))
        muc_nuoc_ho = _decimal_or_none(san_xuat.cot_g)

        item, created = SoBCHCSongHinh.objects.get_or_create(
            ngay_dong_bo=sync_date,
            defaults={
                "nha_may": _get_song_hinh_factory(),
                "nguoi_dong_bo": request.user,
            },
        )
        if (
            not created
            and not request.user.is_superuser
            and item.nguoi_dong_bo_id
            and item.nguoi_dong_bo_id != request.user.id
        ):
            raise PermissionDenied("Chi user dong bo moi duoc dong bo lai ngay nay.")

        item.nha_may = item.nha_may or _get_song_hinh_factory()
        item.nguoi_dong_bo = request.user
        item.chu_ky_nguoi_dong_bo = None
        item.muc_nuoc_quy_trinh_tu = muc_nuoc_tu
        item.muc_nuoc_quy_trinh_den = muc_nuoc_den
        item.muc_nuoc_quy_trinh = _format_decimal_range(muc_nuoc_tu, muc_nuoc_den)
        item.muc_nuoc_ho = muc_nuoc_ho
        item.luu_luong_ve_ho = _decimal_or_none(san_xuat.cot_i)
        item.luu_luong_xa_tran = _decimal_or_none(san_xuat.cot_k)
        item.luu_luong_chay_may = _decimal_or_none(san_xuat.cot_j)
        item.luu_luong_chay_may_qt = _calculate_bchc_qt(
            muc_nuoc_ho,
            muc_nuoc_tu,
            muc_nuoc_den,
        )
        item.save()

        serializer = self.get_serializer(item)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SogiaonhancaVHFilterSet(django_filters.FilterSet):
    ngay_truc_tu = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="gte")
    ngay_truc_den = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="lte")

    class Meta:
        model = SogiaonhancaVH
        fields = [
            "nha_may",
            "ca_truc",
            "trang_thai",
            "ngay_truc",
            "ngay_truc_tu",
            "ngay_truc_den",
            "user_giao_ca",
            "user_nhan_ca",
        ]


class SogiaonhancaVHViewSet(viewsets.ModelViewSet):
    serializer_class = SogiaonhancaVHSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SogiaonhancaVHFilterSet
    search_fields = [
        "dia_diem",
        "truc_chinh",
        "truc_phu",
        "truc_ktvh",
        "noi_dung_chi_tiets__tieu_de",
        "noi_dung_chi_tiets__noi_dung",
        "luu_y",
        "user_giao_ca__email",
        "user_giao_ca__username",
        "user_nhan_ca__email",
        "user_nhan_ca__username",
    ]
    ordering_fields = [
        "ngay_truc",
        "thoi_gian_bat_dau_ca",
        "thoi_gian_giao_ca",
        "created_at",
        "updated_at",
    ]
    ordering = ["-ngay_truc", "-thoi_gian_bat_dau_ca", "-thoi_gian_giao_ca", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewShiftHandoverLogs]
        if self.action == "create":
            permission_classes = [CanCreateShiftHandoverLogs]
        elif self.action == "ky_nhan_ca":
            permission_classes = [CanReceiveShiftHandoverLogs]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SogiaonhancaVH.objects.select_related(
            "nha_may",
            "user_giao_ca",
            "user_nhan_ca",
            "nguoi_tao",
        ).prefetch_related(
            "noi_dung_chi_tiets__nguoi_tao",
            "luu_y_chi_daos__nguoi_tao",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        so = serializer.save(
            user_giao_ca=self.request.user,
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        _sync_truc_ktvh_from_admin_shift_log(so)
        _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
        so.save()

    def perform_update(self, serializer):
        if _shift_log_locked(serializer.instance):
            raise PermissionDenied("So giao nhan ca da co du 2 chu ky, khong duoc chinh sua.")
        if not _can_edit_shift_log(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so giao nhan ca.")
        so = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        _sync_truc_ktvh_from_admin_shift_log(so)
        _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
        so.save()

    def perform_destroy(self, instance):
        if _shift_log_locked(instance):
            raise PermissionDenied("So giao nhan ca da co du 2 chu ky, khong duoc xoa.")
        if not _can_delete_shift_log(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so giao nhan ca.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def ky_giao_ca(self, request, pk=None):
        so = self.get_object()
        if not _is_creator_of_shift_log(request.user, so):
            return Response(
                {"detail": "Chi user tao so giao nhan ca moi duoc ky giao ca."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not so.nhan_ca_ky_at:
            return Response(
                {"detail": "Can ky nhan ca truoc khi ky giao ca."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not so.giao_ca_ky_at:
            so.giao_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="noi-dung-chi-tiet")
    def tao_noi_dung_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if _shift_log_locked(so):
            return Response(
                {"detail": "So giao nhan ca da co du 2 chu ky, khong duoc them noi dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_create_shift_detail(request.user, so):
            return Response(
                {"detail": "Chi user giao ca moi duoc them noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ChiTietSoGiaoNhanCaVHSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"noi-dung-chi-tiet/(?P<chi_tiet_id>[^/.]+)",
    )
    def cap_nhat_noi_dung_chi_tiet(self, request, pk=None, chi_tiet_id=None):
        so = self.get_object()
        if _shift_log_locked(so):
            return Response(
                {"detail": "So giao nhan ca da co du 2 chu ky, khong duoc cap nhat noi dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            chi_tiet = so.noi_dung_chi_tiets.get(pk=chi_tiet_id)
        except ChiTietSoGiaoNhanCaVH.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay noi dung chi tiet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _can_update_shift_detail(request.user, so, chi_tiet):
            return Response(
                {"detail": "Chi user giao ca tao noi dung moi duoc cap nhat noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            chi_tiet.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = ChiTietSoGiaoNhanCaVHSerializer(
            chi_tiet,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="luu-y-chi-dao")
    def tao_luu_y_chi_dao(self, request, pk=None):
        so = self.get_object()
        if not _can_create_shift_directive(request.user, so):
            return Response(
                {"detail": "User khong co quyen tao luu y chi dao."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = LuuYChiDaoSoGiaoNhanCaVHSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"luu-y-chi-dao/(?P<directive_id>[^/.]+)",
    )
    def cap_nhat_luu_y_chi_dao(self, request, pk=None, directive_id=None):
        so = self.get_object()
        if not _can_view_shift_directives(request.user):
            return Response(
                {"detail": "User khong co quyen xem luu y chi dao."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            directive = so.luu_y_chi_daos.get(pk=directive_id)
        except LuuYChiDaoSoGiaoNhanCaVH.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay luu y chi dao."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _can_update_shift_directive(request.user, directive):
            return Response(
                {"detail": "Chi user tao luu y chi dao moi duoc cap nhat hoac xoa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            directive.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = LuuYChiDaoSoGiaoNhanCaVHSerializer(
            directive,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ky_nhan_ca(self, request, pk=None):
        so = self.get_object()
        if so.user_giao_ca_id == request.user.id:
            return Response(
                {"detail": "User giao ca khong duoc tu ky nhan ca."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if so.user_nhan_ca_id and so.user_nhan_ca_id != request.user.id:
            return Response(
                {"detail": "So da duoc gan user nhan ca khac."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not so.nhan_ca_ky_at:
            if not so.user_nhan_ca_id:
                so.user_nhan_ca = request.user
            so.nhan_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SogiaonhancaHCFilterSet(django_filters.FilterSet):
    ngay_truc_tu = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="gte")
    ngay_truc_den = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="lte")

    class Meta:
        model = SogiaonhancaHC
        fields = [
            "nha_may",
            "trang_thai",
            "ngay_truc",
            "ngay_truc_tu",
            "ngay_truc_den",
            "user_giao_ca",
            "user_nhan_ca",
        ]


class SogiaonhancaHCViewSet(viewsets.ModelViewSet):
    serializer_class = SogiaonhancaHCSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SogiaonhancaHCFilterSet
    search_fields = [
        "dia_diem",
        "nguoi_truc",
        "nguoi_truc_2",
        "nguoi_truc_3",
        "nguoi_truc_chi_tiets__ten_nguoi_truc",
        "noi_dung_chi_tiets__tieu_de",
        "noi_dung_chi_tiets__noi_dung",
        "luu_y",
        "user_giao_ca__email",
        "user_giao_ca__username",
        "user_nhan_ca__email",
        "user_nhan_ca__username",
    ]
    ordering_fields = [
        "ngay_truc",
        "thoi_gian_bat_dau_ca",
        "thoi_gian_giao_ca",
        "created_at",
        "updated_at",
    ]
    ordering = ["-ngay_truc", "-thoi_gian_bat_dau_ca", "-thoi_gian_giao_ca", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewAdminShiftHandoverLogs]
        if self.action == "create":
            permission_classes = [CanCreateAdminShiftHandoverLogs]
        elif self.action == "ky_nhan_ca":
            permission_classes = [CanReceiveAdminShiftHandoverLogs]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SogiaonhancaHC.objects.select_related(
            "nha_may",
            "user_giao_ca",
            "user_nhan_ca",
            "nguoi_tao",
        ).prefetch_related(
            "nguoi_truc_chi_tiets__nguoi_tao",
            "noi_dung_chi_tiets__nguoi_tao",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        so = serializer.save(
            user_giao_ca=self.request.user,
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
        so.save()

    def perform_update(self, serializer):
        if _shift_log_received(serializer.instance):
            raise PermissionDenied("So giao nhan ca da duoc ky nhan, khong duoc chinh sua.")
        if not _is_creator_of_shift_log(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so giao nhan ca hanh chinh.")
        so = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
        so.save()

    def perform_destroy(self, instance):
        if _shift_log_received(instance):
            raise PermissionDenied("So giao nhan ca da duoc ky nhan, khong duoc xoa.")
        if not _is_creator_of_shift_log(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so giao nhan ca hanh chinh.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def ky_giao_ca(self, request, pk=None):
        so = self.get_object()
        if not _is_creator_of_shift_log(request.user, so):
            return Response(
                {"detail": "Chi user tao so giao nhan ca moi duoc ky giao ca."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not so.nhan_ca_ky_at:
            return Response(
                {"detail": "Can ky nhan ca truoc khi ky giao ca."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not so.giao_ca_ky_at:
            so.giao_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="noi-dung-chi-tiet")
    def tao_noi_dung_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if _shift_log_received(so):
            return Response(
                {"detail": "So giao nhan ca da duoc ky nhan, khong duoc them noi dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_create_shift_detail(request.user, so):
            return Response(
                {"detail": "Chi user giao ca moi duoc them noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ChiTietSoGiaoNhanCaHCSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"noi-dung-chi-tiet/(?P<chi_tiet_id>[^/.]+)",
    )
    def cap_nhat_noi_dung_chi_tiet(self, request, pk=None, chi_tiet_id=None):
        so = self.get_object()
        if _shift_log_received(so):
            return Response(
                {"detail": "So giao nhan ca da duoc ky nhan, khong duoc cap nhat noi dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            chi_tiet = so.noi_dung_chi_tiets.get(pk=chi_tiet_id)
        except ChiTietSoGiaoNhanCaHC.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay noi dung chi tiet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _can_update_shift_detail(request.user, so, chi_tiet):
            return Response(
                {"detail": "Chi user giao ca tao noi dung moi duoc cap nhat noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            chi_tiet.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = ChiTietSoGiaoNhanCaHCSerializer(
            chi_tiet,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="nguoi-truc-chi-tiet")
    def tao_nguoi_truc_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if _shift_log_received(so):
            return Response(
                {"detail": "So giao nhan ca da duoc ky nhan, khong duoc them nguoi truc."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _is_creator_of_shift_log(request.user, so):
            return Response(
                {"detail": "Chi user tao so moi duoc them nguoi truc."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = NguoiTrucSoGiaoNhanCaHCSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"nguoi-truc-chi-tiet/(?P<nguoi_truc_id>[^/.]+)",
    )
    def cap_nhat_nguoi_truc_chi_tiet(self, request, pk=None, nguoi_truc_id=None):
        so = self.get_object()
        if _shift_log_received(so):
            return Response(
                {"detail": "So giao nhan ca da duoc ky nhan, khong duoc cap nhat nguoi truc."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _is_creator_of_shift_log(request.user, so):
            return Response(
                {"detail": "Chi user tao so moi duoc cap nhat nguoi truc."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            nguoi_truc = so.nguoi_truc_chi_tiets.get(pk=nguoi_truc_id)
        except NguoiTrucSoGiaoNhanCaHC.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay nguoi truc."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "DELETE":
            nguoi_truc.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = NguoiTrucSoGiaoNhanCaHCSerializer(
            nguoi_truc,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ky_nhan_ca(self, request, pk=None):
        so = self.get_object()
        if so.user_giao_ca_id == request.user.id:
            return Response(
                {"detail": "User giao ca khong duoc tu ky nhan ca."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if so.user_nhan_ca_id and so.user_nhan_ca_id != request.user.id:
            return Response(
                {"detail": "So da duoc gan user nhan ca khac."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not so.nhan_ca_ky_at:
            if not so.user_nhan_ca_id:
                so.user_nhan_ca = request.user
            so.nhan_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SoAntoanFilterSet(django_filters.FilterSet):
    ngay_dong_bo_tu = django_filters.DateFilter(field_name="ngay_dong_bo", lookup_expr="gte")
    ngay_dong_bo_den = django_filters.DateFilter(field_name="ngay_dong_bo", lookup_expr="lte")

    class Meta:
        model = SoAnToanDauGio
        fields = ["nha_may", "ngay_dong_bo", "ngay_dong_bo_tu", "ngay_dong_bo_den", "nguoi_dong_bo"]


class SoAnToanViewSet(viewsets.ModelViewSet):
    serializer_class = SoAnToanSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoAntoanFilterSet
    search_fields = [
        "tinh_trang_an_toan",
        "nguoi_dong_bo__email",
        "nguoi_dong_bo__username",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["ngay_dong_bo", "created_at", "updated_at"]
    ordering = ["-ngay_dong_bo", "-created_at"]

    def get_permissions(self):
        from .permissions import CanCreateOperationLogbooks, CanViewSoAnToanDauGio

        permission_classes = [CanViewSoAnToanDauGio]
        if self.action == "create":
            permission_classes = [CanViewSoAnToanDauGio, CanCreateOperationLogbooks]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SoAnToanDauGio.objects.select_related(
            "nha_may",
            "nguoi_dong_bo",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        item = serializer.save(
            nguoi_dong_bo=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        item.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = serializer.instance
        if not (
            has_profile_permission(user, "can_edit_so_an_toan_dau_gio")
            or instance.nguoi_dong_bo_id == user.id
        ):
            raise PermissionDenied("Ban khong co quyen chinh sua so an toan dau gio nay.")
        item = serializer.save()
        item.save()

    def perform_destroy(self, instance):
        if not (
            has_profile_permission(self.request.user, "can_delete_so_an_toan_dau_gio")
            or instance.nguoi_dong_bo_id == self.request.user.id
        ):
            raise PermissionDenied("Ban khong co quyen xoa so an toan dau gio nay.")
        return super().perform_destroy(instance)


class MauChuyenDoiThietBiFilterSet(django_filters.FilterSet):
    class Meta:
        model = MauChuyenDoiThietBi
        fields = ["nha_may", "to_may", "dang_su_dung", "thiet_bi"]


class MauChuyenDoiThietBiViewSet(viewsets.ModelViewSet):
    serializer_class = MauChuyenDoiThietBiSerializer
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MauChuyenDoiThietBiFilterSet
    search_fields = [
        "nhom_thiet_bi",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["to_may", "thu_tu", "created_at", "updated_at"]
    ordering = ["to_may", "thu_tu", "created_at"]

    def get_permissions(self):
        permission_classes = [CanViewOperationLogbooks]
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [CanCreateOperationLogbooks]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = MauChuyenDoiThietBi.objects.select_related(
            "nha_may",
            "thiet_bi",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_update(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )


class SoChuyenDoiThietBiTuanFilterSet(django_filters.FilterSet):
    tuan_tu = django_filters.NumberFilter(field_name="tuan", lookup_expr="gte")
    tuan_den = django_filters.NumberFilter(field_name="tuan", lookup_expr="lte")
    ngay_tu = django_filters.DateFilter(field_name="tuan_ket_thuc", lookup_expr="gte")
    ngay_den = django_filters.DateFilter(field_name="tuan_bat_dau", lookup_expr="lte")

    class Meta:
        model = SoChuyenDoiThietBiTuan
        fields = ["nha_may", "nam", "tuan", "ca_truc", "tuan_tu", "tuan_den", "ngay_tu", "ngay_den", "nguoi_tao"]


class SoChuyenDoiThietBiTuanViewSet(viewsets.ModelViewSet):
    serializer_class = SoChuyenDoiThietBiTuanSerializer
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoChuyenDoiThietBiTuanFilterSet
    search_fields = [
        "nguoi_tao__email",
        "nguoi_tao__username",
        "ca_truc",
        "lan_chuyen_dois__ghi_chu_chung",
        "lan_chuyen_dois__chi_tiets__ghi_chu",
        "lan_chuyen_dois__chi_tiets__thiet_bi__ten",
        "lan_chuyen_dois__chi_tiets__thiet_bi__ma_day_du",
    ]
    ordering_fields = ["nam", "tuan", "tuan_bat_dau", "created_at", "updated_at"]
    ordering = ["-nam", "-tuan", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewWeeklyEquipmentSwitchLogs]
        if self.action == "create":
            permission_classes = [CanCreateWeeklyEquipmentSwitchLogs]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = (
            SoChuyenDoiThietBiTuan.objects.select_related(
                "nha_may",
                "nguoi_tao",
            )
            .prefetch_related(
                "lan_chuyen_dois",
                "lan_chuyen_dois__nguoi_thuc_hien",
                "lan_chuyen_dois__chi_tiets",
                "lan_chuyen_dois__chi_tiets__thiet_bi",
            )
            .all()
            .distinct()
        )
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        factory_data = apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        if not factory_data.get("nha_may") and not serializer.validated_data.get("nha_may"):
            factory_data["nha_may"] = _get_song_hinh_factory()
        serializer.save(
            nguoi_tao=self.request.user,
            **factory_data
        )

    def perform_update(self, serializer):
        if not _can_edit_weekly_equipment_switch_log(self.request.user, serializer.instance):
            raise PermissionDenied("Ban khong co quyen cap nhat so chuyen doi thiet bi tuan nay.")
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_destroy(self, instance):
        if not _can_delete_weekly_equipment_switch_log(self.request.user, instance):
            raise PermissionDenied("Ban khong co quyen xoa so chuyen doi thiet bi tuan nay.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="tao-lan-chuyen-doi")
    def tao_lan_chuyen_doi(self, request, pk=None):
        so = self.get_object()
        target_nha_may = so.nha_may or _get_song_hinh_factory()
        if not _can_edit_weekly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Ban khong co quyen them lan chuyen doi thiet bi."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if so.lan_chuyen_dois.exists():
            return Response(
                {"detail": "Moi so tuan chi duoc tao mot lan chuyen doi thiet bi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LanChuyenDoiThietBiSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        templates = list(
            MauChuyenDoiThietBi.objects.select_related("thiet_bi")
            .filter(dang_su_dung=True)
            .filter(nha_may=target_nha_may)
            .order_by("to_may", "thu_tu", "created_at")
        )
        if not templates:
            _create_default_switch_templates(target_nha_may)
            templates = list(
                MauChuyenDoiThietBi.objects.select_related("thiet_bi")
                .filter(dang_su_dung=True)
                .filter(nha_may=target_nha_may)
                .order_by("to_may", "thu_tu", "created_at")
            )
        if not templates:
            return Response(
                {"detail": "Chua co mau chuyen doi thiet bi cho nha may nay va khong tim thay thiet bi phu hop de tao mau mac dinh."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            lan = serializer.save(so=so, nguoi_thuc_hien=request.user)
            ChiTietChuyenDoiThietBi.objects.bulk_create(
                [
                    ChiTietChuyenDoiThietBi(
                        lan_chuyen_doi=lan,
                        thiet_bi=template.thiet_bi,
                        to_may=template.to_may,
                        nhom_thiet_bi=template.nhom_thiet_bi,
                        thu_tu=template.thu_tu,
                    )
                    for template in templates
                ]
            )

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"lan-chuyen-doi/(?P<lan_id>[^/.]+)",
    )
    def cap_nhat_lan_chuyen_doi(self, request, pk=None, lan_id=None):
        so = self.get_object()
        try:
            lan = so.lan_chuyen_dois.get(pk=lan_id)
        except LanChuyenDoiThietBi.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay lan chuyen doi thiet bi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "DELETE":
            if not _can_delete_weekly_equipment_switch_entry(request.user, lan):
                return Response(
                    {"detail": "Ban khong co quyen xoa lan chuyen doi thiet bi nay."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            lan.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        if not _can_edit_weekly_equipment_switch_entry(request.user, lan):
            return Response(
                {"detail": "Ban khong co quyen cap nhat lan chuyen doi thiet bi nay."},
                status=status.HTTP_403_FORBIDDEN,
            )

        lan_serializer = LanChuyenDoiThietBiSerializer(
            lan,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        lan_serializer.is_valid(raise_exception=True)

        chi_tiets = request.data.get("chi_tiets", [])
        chi_tiet_map = {str(item.id): item for item in lan.chi_tiets.all()}
        allowed_statuses = {choice[0] for choice in ChiTietChuyenDoiThietBi.TrangThai.choices}
        for payload in chi_tiets:
            trang_thai_value = payload.get("trang_thai")
            if trang_thai_value and trang_thai_value not in allowed_statuses:
                return Response(
                    {"detail": f"Trang thai khong hop le: {trang_thai_value}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            lan_serializer.save()
            for payload in chi_tiets:
                chi_tiet = chi_tiet_map.get(str(payload.get("id")))
                if not chi_tiet:
                    continue
                trang_thai_value = payload.get("trang_thai", chi_tiet.trang_thai)
                chi_tiet.trang_thai = trang_thai_value or ""
                chi_tiet.ghi_chu = payload.get("ghi_chu", chi_tiet.ghi_chu)
                chi_tiet.save(update_fields=["trang_thai", "ghi_chu", "updated_at"])

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_200_OK)


class MauChuyenDoiTBThangFilterSet(django_filters.FilterSet):
    class Meta:
        model = MauChuyenDoiTBThang
        fields = ["nha_may", "ma_nhom", "dang_su_dung", "thiet_bi"]


class MauChuyenDoiTBThangViewSet(viewsets.ModelViewSet):
    serializer_class = MauChuyenDoiTBThangSerializer
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MauChuyenDoiTBThangFilterSet
    search_fields = [
        "ma_nhom",
        "ten_nhom",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["thu_tu_nhom", "thu_tu", "created_at", "updated_at"]
    ordering = ["thu_tu_nhom", "thu_tu", "created_at"]

    def get_permissions(self):
        permission_classes = [CanViewMonthlyEquipmentSwitchLogs]
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [CanCreateMonthlyEquipmentSwitchLogs]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = MauChuyenDoiTBThang.objects.select_related(
            "nha_may",
            "thiet_bi",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_update(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )


class SoChuyenDoiTBThangFilterSet(django_filters.FilterSet):
    thang_tu = django_filters.NumberFilter(field_name="thang", lookup_expr="gte")
    thang_den = django_filters.NumberFilter(field_name="thang", lookup_expr="lte")
    ngay_tu = django_filters.DateFilter(field_name="thang_ket_thuc", lookup_expr="gte")
    ngay_den = django_filters.DateFilter(field_name="thang_bat_dau", lookup_expr="lte")

    class Meta:
        model = SoChuyenDoiTBThang
        fields = ["nha_may", "nam", "thang", "ca_truc", "thang_tu", "thang_den", "ngay_tu", "ngay_den", "nguoi_tao"]


class SoChuyenDoiTBThangViewSet(viewsets.ModelViewSet):
    serializer_class = SoChuyenDoiTBThangSerializer
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoChuyenDoiTBThangFilterSet
    search_fields = [
        "nguoi_tao__email",
        "nguoi_tao__username",
        "ca_truc",
        "chi_tiets__ghi_chu",
        "chi_tiets__ten_nhom",
        "chi_tiets__thiet_bi__ten",
        "chi_tiets__thiet_bi__ma_day_du",
    ]
    ordering_fields = ["nam", "thang", "thang_bat_dau", "created_at", "updated_at"]
    ordering = ["-nam", "-thang", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewMonthlyEquipmentSwitchLogs]
        if self.action == "create":
            permission_classes = [CanCreateMonthlyEquipmentSwitchLogs]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = (
            SoChuyenDoiTBThang.objects.select_related(
                "nha_may",
                "nguoi_tao",
            )
            .prefetch_related(
                "chi_tiets",
                "chi_tiets__thiet_bi",
            )
            .all()
            .distinct()
        )
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def _create_details_from_templates(self, so):
        target_nha_may = so.nha_may or _get_song_hinh_factory()
        templates = list(
            MauChuyenDoiTBThang.objects.select_related("thiet_bi")
            .filter(dang_su_dung=True)
            .filter(nha_may=target_nha_may)
            .order_by("thu_tu_nhom", "thu_tu", "created_at")
        )
        if not templates:
            _create_default_monthly_switch_templates(target_nha_may)
            templates = list(
                MauChuyenDoiTBThang.objects.select_related("thiet_bi")
                .filter(dang_su_dung=True)
                .filter(nha_may=target_nha_may)
                .order_by("thu_tu_nhom", "thu_tu", "created_at")
            )
        if not templates:
            return False

        previous_values = _previous_month_values_by_device(so)
        existing_ids = set(so.chi_tiets.values_list("thiet_bi_id", flat=True))
        ChiTietChuyenDoiTBThang.objects.bulk_create(
            [
                ChiTietChuyenDoiTBThang(
                    so=so,
                    thiet_bi=template.thiet_bi,
                    ma_nhom=template.ma_nhom,
                    ten_nhom=template.ten_nhom,
                    don_vi_nhom=template.don_vi_nhom,
                    don_vi=template.don_vi,
                    dau_thang=previous_values.get(template.thiet_bi_id, 0),
                    cuoi_thang=previous_values.get(template.thiet_bi_id, 0),
                    thu_tu_nhom=template.thu_tu_nhom,
                    thu_tu=template.thu_tu,
                )
                for template in templates
                if template.thiet_bi_id not in existing_ids
            ]
        )
        return True

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        factory_data = apply_request_factory_to_serializer(request.user, serializer, "nha_may", "fk")
        if not factory_data.get("nha_may") and not serializer.validated_data.get("nha_may"):
            factory_data["nha_may"] = _get_song_hinh_factory()

        with transaction.atomic():
            so = serializer.save(nguoi_tao=request.user, **factory_data)
            details_created = self._create_details_from_templates(so)
            if not details_created:
                raise DRFValidationError(
                    {"detail": "Chua co mau chuyen doi TB thang cho nha may nay va khong tim thay thiet bi phu hop de tao mau mac dinh."}
                )

        response_serializer = self.get_serializer(self.get_queryset().get(pk=so.pk))
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        if not _can_edit_monthly_equipment_switch_log(self.request.user, serializer.instance):
            raise PermissionDenied("Ban khong co quyen cap nhat so chuyen doi TB thang nay.")
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_destroy(self, instance):
        if not _can_delete_monthly_equipment_switch_log(self.request.user, instance):
            raise PermissionDenied("Ban khong co quyen xoa so chuyen doi TB thang nay.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="tao-chi-tiet")
    def tao_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if not _can_edit_monthly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Ban khong co quyen them chi tiet chuyen doi TB thang."},
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            details_created = self._create_details_from_templates(so)
            if not details_created:
                return Response(
                    {"detail": "Chua co mau chuyen doi TB thang cho nha may nay va khong tim thay thiet bi phu hop de tao mau mac dinh."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch"],
        url_path=r"chi-tiet/(?P<chi_tiet_id>[^/.]+)",
    )
    def cap_nhat_chi_tiet(self, request, pk=None, chi_tiet_id=None):
        so = self.get_object()
        if not _can_edit_monthly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Ban khong co quyen cap nhat chi tiet chuyen doi TB thang nay."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            chi_tiet = so.chi_tiets.get(pk=chi_tiet_id)
        except ChiTietChuyenDoiTBThang.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay chi tiet chuyen doi TB thang."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ChiTietChuyenDoiTBThangSerializer(
            chi_tiet,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_200_OK)
