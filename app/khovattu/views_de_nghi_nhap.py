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

class DeNghiNhapListAPIView(ListAPIView):
    """
    GET /api/khovattu/de-nghi-nhap/?q=&nha_may=&ma_bravo=&don_vi=&he_thong=&page=1&ngay_de_nghi__gte=&ngay_de_nghi__lte=
    """
    serializer_class = DeNghiNhapSerializer
    permission_classes = [HasFactoryAccess, CanViewImportRequest]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        qs = Bang_de_nghi_nhap.objects.select_related("vat_tu", "vat_tu__bang_nha_may").all()

        # Filter theo quyền nhà máy của user
        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                if not profile.is_all_factories and profile.nha_may:
                    # User chỉ có quyền truy cập nhà máy cụ thể
                    qs = qs.filter(vat_tu__bang_nha_may=profile.nha_may)
            except:
                # Nếu không có profile, không cho phép truy cập
                qs = qs.none()

        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(ma_bravo_text__icontains=q) |
                Q(ten_vat_tu__icontains=q) |
                Q(vat_tu__ma_bravo__icontains=q) |
                Q(vat_tu__ten_vat_tu__icontains=q)
            )

        nha_may = (self.request.GET.get("nha_may") or "").strip()
        if nha_may:
            qs = qs.filter(vat_tu__bang_nha_may__ma_nha_may__iexact=nha_may)

        ma_bravo = (self.request.GET.get("ma_bravo") or "").strip()
        if ma_bravo:
            qs = qs.filter(
                Q(ma_bravo_text__iexact=ma_bravo) |
                Q(vat_tu__ma_bravo__iexact=ma_bravo)
            )

        don_vi = (self.request.GET.get("don_vi") or "").strip()
        if don_vi:
            qs = qs.filter(don_vi__iexact=don_vi)

        he_thong = (self.request.GET.get("he_thong") or "").strip()
        if he_thong:
            qs = qs.filter(vat_tu__ma_vi_tri__ma_he_thong__icontains=he_thong)

        # Filter theo thời gian
        ngay_de_nghi__gte_raw = self.request.GET.get("ngay_de_nghi__gte")
        ngay_de_nghi__gte = _parse_date_for_filter(ngay_de_nghi__gte_raw)
        if ngay_de_nghi__gte:
            qs = qs.filter(ngay_de_nghi__gte=ngay_de_nghi__gte)

        ngay_de_nghi__lte_raw = self.request.GET.get("ngay_de_nghi__lte")
        ngay_de_nghi__lte = _parse_date_for_filter(ngay_de_nghi__lte_raw)
        if ngay_de_nghi__lte:
            qs = qs.filter(ngay_de_nghi__lte=ngay_de_nghi__lte)

        return qs.order_by("-ngay_de_nghi", "-id")



class DeNghiNhapByBravoPlantAPIView(APIView):
    """
    GET /api/khovattu/de-nghi-nhap/<ma_nha_may>/<ma_bravo>/?date_from=&date_to=&limit=50&offset=0&q=
    """
    permission_classes = [HasFactoryAccess, CanCreateImportRequest]

    def get(self, request, ma_nha_may: str, ma_bravo: str):
        qs = (
            Bang_de_nghi_nhap.objects
            .select_related("vat_tu", "vat_tu__bang_nha_may")
            .filter(
                vat_tu__bang_nha_may__ma_nha_may__iexact=ma_nha_may,
                vat_tu__ma_bravo__iexact=ma_bravo
            )
        )

        q = (request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(ten_vat_tu__icontains=q))

        dfrom = _parse_date_for_filter(request.GET.get("date_from"))
        dto   = _parse_date_for_filter(request.GET.get("date_to"))
        if dfrom:
            qs = qs.filter(ngay_de_nghi__gte=dfrom)
        if dto:
            qs = qs.filter(ngay_de_nghi__lte=dto)

        total = qs.count()
        total_sl = qs.aggregate(s=Sum("so_luong"))["s"] or 0

        try:
            limit = int(request.GET.get("limit", 50))
        except Exception:
            limit = 50
        try:
            offset = int(request.GET.get("offset", 0))
        except Exception:
            offset = 0

        items = qs.order_by("-ngay_de_nghi", "-id")[offset: offset + limit]
        data = DeNghiNhapSerializer(items, many=True).data
        return Response({"count": total, "total_so_luong": total_sl, "results": data}, status=status.HTTP_200_OK)

    def post(self, request, ma_nha_may, ma_bravo):
        so_luong = _to_int(request.data.get("so_luong"), None)
        if not so_luong or so_luong <= 0:
            return Response({"error":"so_luong phải > 0"}, status=400)

        with transaction.atomic():
            vt = Bang_vat_tu.objects.select_for_update().filter(
                bang_nha_may__ma_nha_may=ma_nha_may, ma_bravo=ma_bravo
            ).first()
            if not vt:
                return Response({"error":"Không tìm thấy vật tư"}, status=404)
            # === TÍNH STT THEO PHẠM VI (NHÀ MÁY + NGÀY) ===
            ngay = _parse_dt(request.data.get("ngay_de_nghi")) or timezone.now()

            scope_qs = (
                Bang_de_nghi_nhap.objects
                .select_for_update(skip_locked=True)  # nếu dùng SQLite thì bỏ skip_locked
                .filter(
                    vat_tu__bang_nha_may__ma_nha_may=ma_nha_may,
                    ngay_de_nghi__date=ngay.date()
                )
            )
            last_stt = scope_qs.order_by('-stt').values_list('stt', flat=True).first() or 0
            next_stt = last_stt + 1

            obj = Bang_de_nghi_nhap.objects.create(
                stt=next_stt,  # 👈 gán STT
                vat_tu=vt,
                ma_bravo_text=vt.ma_bravo,
                ten_vat_tu=request.data.get("ten_vat_tu") or vt.ten_vat_tu,
                don_vi=request.data.get("don_vi") or vt.don_vi,
                so_luong=so_luong,
                ngay_de_nghi=_parse_dt(request.data.get("ngay_de_nghi")),
                ghi_chu=request.data.get("ghi_chu") or "",
            )
            Bang_vat_tu.objects.filter(pk=vt.pk).update(
                ton_kho=F("ton_kho")+so_luong,
                so_luong_kh=Greatest(F("so_luong_kh")-so_luong, 0),
            )
        return Response(DeNghiNhapSerializer(obj).data, status=201)


class DeNghiNhapDetailAPIView(APIView):
    """
    PATCH  /api/khovattu/de-nghi-nhap/<int:pk>/
    DELETE /api/khovattu/de-nghi-nhap/<int:pk>/
    """
    permission_classes = [HasFactoryAccess, CanCreateImportRequest]

    def get_object(self, pk, for_update=False):
        qs = Bang_de_nghi_nhap.objects.select_related("vat_tu", "vat_tu__bang_nha_may").filter(pk=pk)
        if for_update:
            qs = qs.select_for_update()
        return filter_queryset_by_factory(qs, self.request.user, "vat_tu__bang_nha_may", "fk").first()

    def patch(self, request, pk):
        obj = self.get_object(pk)
        if not obj: return Response({"error":"Không tìm thấy"}, status=404)

        old = obj.so_luong
        ser = DeNghiNhapPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Update fields
        for field in ["so_luong", "ngay", "ghi_chu"]:
            if field in data:
                if field == "ngay":
                    setattr(obj, "ngay_de_nghi", data[field])
                else:
                    setattr(obj, field, data[field])
        obj.save()

        delta = int(obj.so_luong) - int(old)
        if delta != 0:
            with transaction.atomic():
                vt = Bang_vat_tu.objects.select_for_update().get(pk=obj.vat_tu_id)
                if delta > 0:
                    Bang_vat_tu.objects.filter(pk=vt.pk).update(
                        ton_kho=F("ton_kho")+delta,
                        so_luong_kh=Greatest(F("so_luong_kh")-delta, 0),
                    )
                else:
                    if vt.ton_kho < abs(delta):
                        return Response({"error": f"Tồn kho ({vt.ton_kho}) không đủ để giảm {abs(delta)}"}, status=400)
                    Bang_vat_tu.objects.filter(pk=vt.pk).update(
                        ton_kho=F("ton_kho")+delta,  # delta âm
                        so_luong_kh=F("so_luong_kh")+abs(delta),
                    )
        return Response(DeNghiNhapSerializer(obj).data)

    def delete(self, request, pk):
        obj = self.get_object(pk)
        if not obj: return Response(status=204)
        with transaction.atomic():
            vt = Bang_vat_tu.objects.select_for_update().get(pk=obj.vat_tu_id)
            if vt.ton_kho < obj.so_luong:
                return Response({"error": f"Tồn kho ({vt.ton_kho}) không đủ để xoá phiếu"}, status=400)
            Bang_vat_tu.objects.filter(pk=vt.pk).update(
                ton_kho=F("ton_kho")-obj.so_luong,
                so_luong_kh=F("so_luong_kh")+obj.so_luong,
            )
            obj.delete()
        return Response(status=204)



class TaoDeNghiNhapAPIView(APIView):
    permission_classes = [HasFactoryAccess, CanCreateImportRequest]

    def post(self, request):
        ser = NhapSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data


        with transaction.atomic():
            vt = _get_vattu_by_nm_bravo(data["ma_nha_may"], data["ma_bravo"])

            # Tự động tạo số thứ tự
            max_stt = Bang_de_nghi_nhap.objects.aggregate(max_stt=models.Max('stt'))['max_stt'] or 0
            next_stt = max_stt + 1

            de_nghi_nhap = Bang_de_nghi_nhap.objects.create(
                stt=next_stt,
                vat_tu=vt,
                ma_bravo_text=vt.ma_bravo,
                ten_vat_tu=vt.ten_vat_tu,
                don_vi=vt.don_vi,
                so_luong=data["so_luong"],
                ngay_de_nghi=data.get("ngay_de_nghi") or timezone.now(),
                nguoi_de_nghi=data.get("nguoi_de_nghi", ""),
                ghi_chu=data.get("ghi_chu", ""),
            )

            Bang_vat_tu.objects.filter(pk=vt.pk).update(
                ton_kho=F("ton_kho") + data["so_luong"],
                so_luong_kh=Greatest(F("so_luong_kh") - data["so_luong"], 0),
            )

        return Response({"ok": True}, status=status.HTTP_200_OK)



