import pandas as pd
import uuid as _uuid

from django.db import transaction, models
from django.db.models import F, Sum, Q, Count
from django.db.models.functions import Greatest
from django.utils import timezone
from django.conf import settings
from django.http import HttpResponse

from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from .permissions import (
    HasFactoryAccess, HasSpecificFactoryAccess, HasFactoryAccessStrict,
    CanViewMaterials, CanAddMaterials, CanEditMaterials, CanDeleteMaterials,
    CanImportExcel, CanExportExcel, CanCreateExportRequest, CanApproveExportRequest,
    CanCreateImportRequest, CanApproveImportRequest, CanViewImportRequest, CanViewExportRequest,
    CanViewInventory, CanEditInventory, CanViewReports
)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.renderers import JSONRenderer, BaseRenderer

class ExcelRenderer(BaseRenderer):
    media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    format = 'xlsx'

    def render(self, data, media_type=None, renderer_context=None):
        return data

class ExcelResponse(HttpResponse):
    def __init__(self, content, filename, *args, **kwargs):
        super().__init__(content, *args, **kwargs)
        self['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        self['Content-Disposition'] = f'attachment; filename="{filename}"'
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from django.db.models.deletion import ProtectedError


from .models import (
    Bang_vat_tu, Bang_vi_tri, Bang_kiem_ke,
    Bang_de_nghi_nhap, Bang_de_nghi_xuat, Bang_nha_may, Bang_xuat_xu
)
from core.factory_scope import ensure_factory_allowed, filter_queryset_by_factory
from core.models import UserProfile
from .bravo_parser import extract_position_from_bravo, get_vi_tri_from_bravo
from .serializers import (
    FileUploadSerializer,
    ViTriSerializer,
    VatTuSerializer,                   # read serializer (list/detail)
    DeNghiNhapSerializer, DeNghiXuatSerializer,
    NhapSerializer, XuatSerializer,
    VatTuUpsertSerializer,             # <-- NEW: dùng cho POST/PATCH vật tư
    DeNghiNhapPatchSerializer,         # <-- OPTIONAL: dùng cho PATCH đề nghị nhập
    DeNghiXuatPatchSerializer,         # <-- OPTIONAL: dùng cho PATCH đề nghị xuất
    UserProfileSerializer,
    XuatXuSerializer,
)

# ===================== CUSTOM PAGINATION =====================

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 20  # ✅ Thay đổi từ 20 thành 50
    page_size_query_param = 'limit'
    max_page_size = 200

# ===================== HELPERS =====================

def _parse_dt(val):
    dt = pd.to_datetime(val, errors="coerce")
    return dt.to_pydatetime() if pd.notna(dt) else timezone.now()

def _parse_date_for_filter(val):
    if not val:
        return None

    # Handle URL encoded datetime strings (e.g., "2025-09-08T20%3A35" -> "2025-09-08T20:35")
    if isinstance(val, str):
        val = val.replace('%3A', ':')

    try:
        # Try parsing with pandas first
        dt = pd.to_datetime(val, errors="coerce")
        if pd.isna(dt):
            return None
        py = dt.to_pydatetime()

        # Make timezone aware if naive (assume Vietnam timezone)
        if timezone.is_naive(py):
            py = timezone.make_aware(py, timezone.get_current_timezone())

        # Convert to UTC for database comparison since data is stored in UTC
        import pytz
        py_utc = py.astimezone(pytz.UTC)
        return py_utc
    except Exception:
        return None

def _to_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        s = str(v).replace(",", "")
        return int(float(s))
    except Exception:
        return default

def _get_vi_tri_from_excel(row):
    """
    - Có cột 'ma_vi_tri' (ví dụ 'A1') thì tra theo mã ngắn.
    - Hoặc đủ 5 cột: ma_he_thong, kho, ke, ngan, tang (sẽ get_or_create).
    - HOẶC trích xuất từ ma_bravo nếu có thể parse được.
    """
    # Phương pháp 1: Có cột ma_vi_tri trực tiếp
    code = str(row.get("ma_vi_tri") or "").strip()
    if code:
        try:
            return Bang_vi_tri.objects.get(ma_vi_tri=code)
        except Bang_vi_tri.DoesNotExist:
            pass

    # Phương pháp 2: Có đủ 5 cột chi tiết
    fields = {k: str(row.get(k) or "").strip() for k in ["ma_he_thong", "kho", "ke", "ngan", "tang"]}
    if any(fields.values()):
        vitri, _ = Bang_vi_tri.objects.get_or_create(
            ma_vi_tri=f'{fields["ke"]}{fields["ngan"]}'.strip() or _uuid.uuid4().hex[:6],
            defaults=fields,
        )
        return vitri

    # Phương pháp 3: Trích xuất từ ma_bravo (MỚI) - CHỈ TÌM, KHÔNG TẠO MỚI
    ma_bravo = str(row.get("ma_bravo") or "").strip()
    if ma_bravo:
        try:
            # Chỉ trích xuất thông tin, không tạo mới vị trí
            position_info = extract_position_from_bravo(ma_bravo)
            if position_info and position_info.get('ma_vi_tri'):
                # Tìm vị trí đã tồn tại
                existing_vitri = Bang_vi_tri.objects.filter(
                    ma_vi_tri=position_info['ma_vi_tri']
                ).first()
                if existing_vitri:
                    print(f"✅ Found existing position '{existing_vitri.ma_vi_tri}' for bravo '{ma_bravo}'")
                    return existing_vitri
                else:
                    print(f"⚠️  Position '{position_info['ma_vi_tri']}' not found for bravo '{ma_bravo}', skipping")
        except Exception as e:
            print(f"❌ Error parsing bravo '{ma_bravo}': {e}")
            pass

    return None

def _get_nha_may_from_row(row) -> Bang_nha_may:
    code = str(row.get("ma_nha_may") or row.get("nha_may") or "").strip()
    name = str(row.get("ten_nha_may") or "").strip()
    if code:
        nm = Bang_nha_may.objects.filter(ma_nha_may=code).first()
        if not nm:
            raise ValueError(f"Không tồn tại nhà máy với ma_nha_may='{code}'")
        return nm
    if name:
        nm = Bang_nha_may.objects.filter(ten_nha_may__iexact=name).first()
        if not nm:
            raise ValueError(f"Không tồn tại nhà máy với ten_nha_may='{name}'")
        return nm
    raise ValueError("Thiếu cột 'ma_nha_may' hoặc 'ten_nha_may'")

def _get_vattu_by_nm_bravo(ma_nha_may: str, ma_bravo: str) -> Bang_vat_tu:
    return Bang_vat_tu.objects.get(
        ma_bravo=str(ma_bravo).strip(),
        bang_nha_may__ma_nha_may=str(ma_nha_may).strip()
    )

# ===================== IMPORT APIs =====================

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 20  # ✅ Thay đổi từ 20 thành 50
    page_size_query_param = 'limit'
    max_page_size = 200

# ===================== HELPERS =====================

def _parse_dt(val):
    dt = pd.to_datetime(val, errors="coerce")
    return dt.to_pydatetime() if pd.notna(dt) else timezone.now()

def _parse_date_for_filter(val):
    if not val:
        return None

    # Handle URL encoded datetime strings (e.g., "2025-09-08T20%3A35" -> "2025-09-08T20:35")
    if isinstance(val, str):
        val = val.replace('%3A', ':')

    try:
        # Try parsing with pandas first
        dt = pd.to_datetime(val, errors="coerce")
        if pd.isna(dt):
            return None
        py = dt.to_pydatetime()

        # Make timezone aware if naive (assume Vietnam timezone)
        if timezone.is_naive(py):
            py = timezone.make_aware(py, timezone.get_current_timezone())

        # Convert to UTC for database comparison since data is stored in UTC
        import pytz
        py_utc = py.astimezone(pytz.UTC)
        return py_utc
    except Exception:
        return None

def _to_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        s = str(v).replace(",", "")
        return int(float(s))
    except Exception:
        return default

def _get_vi_tri_from_excel(row):
    """
    - Có cột 'ma_vi_tri' (ví dụ 'A1') thì tra theo mã ngắn.
    - Hoặc đủ 5 cột: ma_he_thong, kho, ke, ngan, tang (sẽ get_or_create).
    - HOẶC trích xuất từ ma_bravo nếu có thể parse được.
    """
    # Phương pháp 1: Có cột ma_vi_tri trực tiếp
    code = str(row.get("ma_vi_tri") or "").strip()
    if code:
        try:
            return Bang_vi_tri.objects.get(ma_vi_tri=code)
        except Bang_vi_tri.DoesNotExist:
            pass

    # Phương pháp 2: Có đủ 5 cột chi tiết
    fields = {k: str(row.get(k) or "").strip() for k in ["ma_he_thong", "kho", "ke", "ngan", "tang"]}
    if any(fields.values()):
        vitri, _ = Bang_vi_tri.objects.get_or_create(
            ma_vi_tri=f'{fields["ke"]}{fields["ngan"]}'.strip() or _uuid.uuid4().hex[:6],
            defaults=fields,
        )
        return vitri

    # Phương pháp 3: Trích xuất từ ma_bravo (MỚI) - CHỈ TÌM, KHÔNG TẠO MỚI
    ma_bravo = str(row.get("ma_bravo") or "").strip()
    if ma_bravo:
        try:
            # Chỉ trích xuất thông tin, không tạo mới vị trí
            position_info = extract_position_from_bravo(ma_bravo)
            if position_info and position_info.get('ma_vi_tri'):
                # Tìm vị trí đã tồn tại
                existing_vitri = Bang_vi_tri.objects.filter(
                    ma_vi_tri=position_info['ma_vi_tri']
                ).first()
                if existing_vitri:
                    print(f"✅ Found existing position '{existing_vitri.ma_vi_tri}' for bravo '{ma_bravo}'")
                    return existing_vitri
                else:
                    print(f"⚠️  Position '{position_info['ma_vi_tri']}' not found for bravo '{ma_bravo}', skipping")
        except Exception as e:
            print(f"❌ Error parsing bravo '{ma_bravo}': {e}")
            pass

    return None

def _get_nha_may_from_row(row) -> Bang_nha_may:
    code = str(row.get("ma_nha_may") or row.get("nha_may") or "").strip()
    name = str(row.get("ten_nha_may") or "").strip()
    if code:
        nm = Bang_nha_may.objects.filter(ma_nha_may=code).first()
        if not nm:
            raise ValueError(f"Không tồn tại nhà máy với ma_nha_may='{code}'")
        return nm
    if name:
        nm = Bang_nha_may.objects.filter(ten_nha_may__iexact=name).first()
        if not nm:
            raise ValueError(f"Không tồn tại nhà máy với ten_nha_may='{name}'")
        return nm
    raise ValueError("Thiếu cột 'ma_nha_may' hoặc 'ten_nha_may'")

def _get_vattu_by_nm_bravo(ma_nha_may: str, ma_bravo: str) -> Bang_vat_tu:
    return Bang_vat_tu.objects.get(
        ma_bravo=str(ma_bravo).strip(),
        bang_nha_may__ma_nha_may=str(ma_nha_may).strip()
    )

# ===================== IMPORT APIs =====================


class ExcelRenderer(BaseRenderer):
    media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    format = 'xlsx'

    def render(self, data, media_type=None, renderer_context=None):
        return data


class ExcelResponse(HttpResponse):
    def __init__(self, content, filename, *args, **kwargs):
        super().__init__(content, *args, **kwargs)
        self['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        self['Content-Disposition'] = f'attachment; filename="{filename}"'
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from django.db.models.deletion import ProtectedError


from .models import (
    Bang_vat_tu, Bang_vi_tri, Bang_kiem_ke,
    Bang_de_nghi_nhap, Bang_de_nghi_xuat, Bang_nha_may, Bang_xuat_xu
)
from core.factory_scope import ensure_factory_allowed, filter_queryset_by_factory
from core.models import UserProfile
from .bravo_parser import extract_position_from_bravo, get_vi_tri_from_bravo
from .serializers import (
    FileUploadSerializer,
    ViTriSerializer,
    VatTuSerializer,                   # read serializer (list/detail)
    DeNghiNhapSerializer, DeNghiXuatSerializer,
    NhapSerializer, XuatSerializer,
    VatTuUpsertSerializer,             # <-- NEW: dùng cho POST/PATCH vật tư
    DeNghiNhapPatchSerializer,         # <-- OPTIONAL: dùng cho PATCH đề nghị nhập
    DeNghiXuatPatchSerializer,         # <-- OPTIONAL: dùng cho PATCH đề nghị xuất
    UserProfileSerializer,
    XuatXuSerializer,
)

# ===================== CUSTOM PAGINATION =====================


