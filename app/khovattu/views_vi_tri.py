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

class ViTriListAPIView(APIView):
    """
    GET /api/khovattu/vi-tri/?q=&ma_he_thong=&kho=&ke=&ngan=&tang=&limit=50&offset=0
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Bang_vi_tri.objects.all().order_by("ma_vi_tri")

        q = (request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(ma_vi_tri__icontains=q) |
                Q(ma_he_thong__icontains=q) |
                Q(kho__icontains=q) |
                Q(ke__icontains=q) |
                Q(ngan__icontains=q) |
                Q(tang__icontains=q) |
                Q(mo_ta__icontains=q)
            )

        for field in ["ma_he_thong", "kho", "ke", "ngan", "tang"]:
            val = (request.GET.get(field) or "").strip()
            if val:
                qs = qs.filter(**{f"{field}__iexact": val})

        total = qs.count()
        try:
            limit = int(request.GET.get("limit", 50))
        except Exception:
            limit = 50
        try:
            offset = int(request.GET.get("offset", 0))
        except Exception:
            offset = 0

        items = qs[offset: offset + limit]
        data = ViTriSerializer(items, many=True).data
        return Response({"count": total, "results": data}, status=status.HTTP_200_OK)



class ViTriDetailAPIView(APIView):
    """GET /api/khovattu/vi-tri/<ma_vi_tri>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, ma_vi_tri: str):
        obj = Bang_vi_tri.objects.filter(ma_vi_tri=ma_vi_tri).first()
        if not obj:
            return Response({"error": "Không tìm thấy vị trí"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ViTriSerializer(obj).data, status=status.HTTP_200_OK)



class HeThongListAPIView(APIView):
    """GET /api/khovattu/he-thong/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Lấy danh sách hệ thống có vật tư
        systems = Bang_vat_tu.objects.values('ma_vi_tri__ma_he_thong').annotate(
            count=models.Count('id')
        ).filter(
            ma_vi_tri__ma_he_thong__isnull=False
        ).order_by('ma_vi_tri__ma_he_thong')

        result = []
        for system in systems:
            system_name = system['ma_vi_tri__ma_he_thong']
            count = system['count']
            result.append({
                'ma_he_thong': system_name,
                'so_luong_vat_tu': count
            })

        return Response(result, status=status.HTTP_200_OK)



class HeThongByFactoryListAPIView(APIView):
    """
    GET /api/khovattu/he-thong/by-factory/?ma_nha_may=SH
    Lấy danh sách hệ thống theo nhà máy cụ thể với số lượng vật tư chính xác
    """
    permission_classes = [IsAuthenticated, HasFactoryAccess]

    def get(self, request):
        ma_nha_may = request.GET.get('ma_nha_may')

        if not ma_nha_may:
            return Response({'error': 'Thiếu tham số ma_nha_may'}, status=status.HTTP_400_BAD_REQUEST)

        # Lấy danh sách hệ thống có vật tư của nhà máy cụ thể
        systems = Bang_vat_tu.objects.filter(
            bang_nha_may__ma_nha_may=ma_nha_may
        ).values('ma_vi_tri__ma_he_thong').annotate(
            count=models.Count('id')
        ).filter(
            ma_vi_tri__ma_he_thong__isnull=False
        ).order_by('ma_vi_tri__ma_he_thong')

        result = []
        for system in systems:
            system_name = system['ma_vi_tri__ma_he_thong']
            count = system['count']
            result.append({
                'ma_he_thong': system_name,
                'so_luong_vat_tu': count
            })

        return Response(result, status=status.HTTP_200_OK)

# ===================== VẬT TƯ: GET list + detail + overview =====================


class BravoPositionAnalyzeAPIView(APIView):
    """
    POST /api/khovattu/bravo/analyze/
    Phân tích mã Bravo để trích xuất thông tin vị trí
    """
    permission_classes = [HasFactoryAccess]

    def post(self, request):
        ma_bravo = request.data.get('ma_bravo', '').strip()
        if not ma_bravo:
            return Response({"error": "Thiếu ma_bravo"}, status=status.HTTP_400_BAD_REQUEST)

        # Trích xuất thông tin vị trí
        position_info = extract_position_from_bravo(ma_bravo)
        if not position_info:
            return Response({
                "ma_bravo": ma_bravo,
                "success": False,
                "message": "Không thể trích xuất thông tin vị trí từ mã Bravo này"
            }, status=status.HTTP_200_OK)

        # Thử tạo/lấy đối tượng vị trí
        vi_tri = None
        try:
            vi_tri = get_vi_tri_from_bravo(ma_bravo)
        except Exception as e:
            pass

        response_data = {
            "ma_bravo": ma_bravo,
            "success": True,
            "extracted_info": position_info,
            "vi_tri_created": vi_tri is not None,
        }

        if vi_tri:
            response_data["vi_tri"] = {
                "id": vi_tri.id,
                "ma_vi_tri": vi_tri.ma_vi_tri,
                "ma_he_thong": vi_tri.ma_he_thong,
                "kho": vi_tri.kho,
                "ke": vi_tri.ke,
                "ngan": vi_tri.ngan,
                "tang": vi_tri.tang,
            }

        return Response(response_data, status=status.HTTP_200_OK)



# ===================== VỊ TRÍ: GET list + detail =====================


