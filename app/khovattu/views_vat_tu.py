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

class VatTuListAPIView(ListAPIView):
    """
    GET /api/khovattu/vat-tu/?q=&ma_nha_may=&ma_bravo=&don_vi=&ma_vi_tri=&he_thong=&page=1
    POST /api/khovattu/vat-tu/ - Tạo vật tư mới
    """
    serializer_class = VatTuSerializer
    permission_classes = [HasFactoryAccess]
    pagination_class = CustomPageNumberPagination

    def get_permissions(self):
        """
        Override để áp dụng permission khác nhau cho từng method
        """
        if self.request.method == 'GET':
            permission_classes = [HasFactoryAccess, CanViewMaterials]
        elif self.request.method == 'POST':
            permission_classes = [HasFactoryAccess, CanAddMaterials]
        else:
            permission_classes = self.permission_classes

        return [permission() for permission in permission_classes]

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Bang_vat_tu.objects.select_related("ma_vi_tri", "bang_nha_may").all()

        # Filter theo quyền nhà máy của user
        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                if not profile.is_all_factories and profile.nha_may:
                    # User chỉ có quyền truy cập nhà máy cụ thể
                    qs = qs.filter(bang_nha_may=profile.nha_may)
            except:
                # Nếu không có profile, không cho phép truy cập
                qs = qs.none()

        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(ma_bravo__icontains=q) |
                Q(ten_vat_tu__icontains=q) |
                Q(thong_so_ky_thuat__icontains=q)
            )

        ma_nha_may = (self.request.GET.get("ma_nha_may") or "").strip()
        if ma_nha_may:
            qs = qs.filter(bang_nha_may__ma_nha_may__iexact=ma_nha_may)

        ma_bravo = (self.request.GET.get("ma_bravo") or "").strip()
        if ma_bravo:
            qs = qs.filter(ma_bravo__iexact=ma_bravo)

        don_vi = (self.request.GET.get("don_vi") or "").strip()
        if don_vi:
            qs = qs.filter(don_vi__iexact=don_vi)

        ma_vi_tri = (self.request.GET.get("ma_vi_tri") or "").strip()
        if ma_vi_tri:
            if ma_vi_tri == "co_vi_tri":
                qs = qs.filter(ma_vi_tri__isnull=False)
            elif ma_vi_tri == "chua_vi_tri":
                qs = qs.filter(ma_vi_tri__isnull=True)
            elif ma_vi_tri == "ton_thap":
                qs = qs.filter(ton_kho__lt=10)
            elif ma_vi_tri == "ton_cao":
                qs = qs.filter(ton_kho__gte=10)
            else:
                qs = qs.filter(ma_vi_tri__ma_vi_tri__iexact=ma_vi_tri)

        # Filter by hệ thống (ma_he_thong)
        he_thong = (self.request.GET.get("he_thong") or "").strip()
        if he_thong:
            qs = qs.filter(ma_vi_tri__ma_he_thong__iexact=he_thong)

        # Filter by so_luong_kh (số lượng kế hoạch)
        so_luong_kh = self.request.GET.get("so_luong_kh")
        if so_luong_kh is not None:
            try:
                so_luong_kh_value = int(so_luong_kh)
                qs = qs.filter(so_luong_kh=so_luong_kh_value)
            except ValueError:
                pass  # Ignore invalid values

        so_luong_kh__gt = self.request.GET.get("so_luong_kh__gt")
        if so_luong_kh__gt is not None:
            try:
                so_luong_kh_gt_value = int(so_luong_kh__gt)
                qs = qs.filter(so_luong_kh__gt=so_luong_kh_gt_value)
            except ValueError:
                pass  # Ignore invalid values

        so_luong_kh__lt = self.request.GET.get("so_luong_kh__lt")
        if so_luong_kh__lt is not None:
            try:
                so_luong_kh_lt_value = int(so_luong_kh__lt)
                qs = qs.filter(so_luong_kh__lt=so_luong_kh_lt_value)
            except ValueError:
                pass  # Ignore invalid values

        # Filter by ton_kho (số lượng tồn)
        ton_kho__gt = self.request.GET.get("ton_kho__gt")
        if ton_kho__gt is not None:
            try:
                ton_kho_gt_value = int(ton_kho__gt)
                qs = qs.filter(ton_kho__gt=ton_kho_gt_value)
            except ValueError:
                pass  # Ignore invalid values

        ton_kho__lt = self.request.GET.get("ton_kho__lt")
        if ton_kho__lt is not None:
            try:
                ton_kho_lt_value = int(ton_kho__lt)
                qs = qs.filter(ton_kho__lt=ton_kho_lt_value)
            except ValueError:
                pass  # Ignore invalid values

        ton_kho__gte = self.request.GET.get("ton_kho__gte")
        if ton_kho__gte is not None:
            try:
                ton_kho_gte_value = int(ton_kho__gte)
                qs = qs.filter(ton_kho__gte=ton_kho_gte_value)
            except ValueError:
                pass  # Ignore invalid values

        # Filter by nhà máy
        nha_may = (self.request.GET.get("nha_may") or "").strip()
        if nha_may:
            qs = qs.filter(bang_nha_may__ma_nha_may__iexact=nha_may)

        return qs.order_by("id")

    def post(self, request):
    # Tạo/cập nhật theo (ma_nha_may, ma_bravo)
        ser = VatTuUpsertSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        nm = ser.validated_data["bang_nha_may"]
        ensure_factory_allowed(request.user, nm)
        ma_bravo = ser.validated_data["ma_bravo"]
        vtpos = ser.validated_data.get("ma_vi_tri_obj")

    # Nếu tạo mới, bắt buộc có tên & đơn vị
        is_exist = Bang_vat_tu.objects.filter(bang_nha_may=nm, ma_bravo=ma_bravo).exists()
        if not is_exist:
            if not request.data.get("ten_vat_tu"):
                return Response({"error": "Thiếu ten_vat_tu khi tạo mới"}, status=400)
            if not request.data.get("don_vi"):
                return Response({"error": "Thiếu don_vi khi tạo mới"}, status=400)

        defaults = {
            "ten_vat_tu": request.data.get("ten_vat_tu"),
            "don_vi": request.data.get("don_vi"),
            "thong_so_ky_thuat": ser.validated_data.get("thong_so_ky_thuat"),
            "ton_kho": ser.validated_data.get("ton_kho", 0),
            "so_luong_kh": ser.validated_data.get("so_luong_kh", 0),
            "ma_vi_tri": vtpos,
            "hinh_anh_vt": request.FILES.get("hinh_anh_vt"),  # Handle image upload
        }
    # Bỏ các key None để tránh overwrite bằng None khi update
        defaults = {k: v for k, v in defaults.items() if v is not None}

        obj, created = Bang_vat_tu.objects.update_or_create(
            bang_nha_may=nm,
            ma_bravo=ma_bravo,
            defaults=defaults,
        )
        obj.save()  # đảm bảo QR tồn tại
        return Response(
            VatTuSerializer(obj).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class VatTuDetailByIdAPIView(APIView):
    """GET /api/khovattu/vat-tu/id/<int:pk>/"""
    permission_classes = [HasFactoryAccess]

    def get(self, request, pk: int):
        vt = filter_queryset_by_factory(
            Bang_vat_tu.objects.select_related("ma_vi_tri", "bang_nha_may").filter(pk=pk),
            request.user,
            "bang_nha_may",
            "fk",
        ).first()
        if not vt:
            return Response({"error": "Không tìm thấy vật tư"}, status=status.HTTP_404_NOT_FOUND)
        return Response(VatTuSerializer(vt).data, status=status.HTTP_200_OK)



class VatTuDetailByBravoAPIView(APIView):
    """
    GET    /api/khovattu/vat-tu/<ma_nha_may>/<ma_bravo>/
    PATCH  /api/khovattu/vat-tu/<ma_nha_may>/<ma_bravo>/
      body: {ten_vat_tu?, don_vi?, thong_so_ky_thuat?, ton_kho?, so_luong_kh?, ma_vi_tri?}
    DELETE /api/khovattu/vat-tu/<ma_nha_may>/<ma_bravo>/

    """
    permission_classes = [HasFactoryAccess]

    def get_permissions(self):
        """
        Override để áp dụng permission khác nhau cho từng method
        """
        if self.request.method == 'GET':
            permission_classes = [HasFactoryAccess, CanViewMaterials]
        elif self.request.method == 'PATCH':
            permission_classes = [HasFactoryAccess, CanEditMaterials]
        elif self.request.method == 'DELETE':
            permission_classes = [HasFactoryAccess, CanDeleteMaterials]
        else:
            permission_classes = self.permission_classes

        return [permission() for permission in permission_classes]

    def get_object(self, ma_nha_may, ma_bravo):
        return Bang_vat_tu.objects.select_related("ma_vi_tri","bang_nha_may").filter(
            bang_nha_may__ma_nha_may=ma_nha_may, ma_bravo=ma_bravo
        ).first()

    def get(self, request, ma_nha_may, ma_bravo):
        vt = self.get_object(ma_nha_may, ma_bravo)
        if not vt: return Response({"error":"Không tìm thấy vật tư"}, status=404)

        # Lấy thông tin vật tư
        vat_tu_data = VatTuSerializer(vt).data

        # Lấy lịch sử nhập/xuất
        lich_su_nhap = Bang_de_nghi_nhap.objects.filter(
            vat_tu__bang_nha_may__ma_nha_may=ma_nha_may,
            ma_bravo_text=ma_bravo
        ).values('so_luong', 'ngay_de_nghi', 'ghi_chu')

        lich_su_xuat = Bang_de_nghi_xuat.objects.filter(
            vat_tu__bang_nha_may__ma_nha_may=ma_nha_may,
            ma_bravo_text=ma_bravo
        ).values('so_luong', 'ngay_de_nghi_xuat', 'ghi_chu')

        # Tính tổng nhập/xuất
        tong_nhap = sum(item['so_luong'] or 0 for item in lich_su_nhap)
        tong_xuat = sum(item['so_luong'] or 0 for item in lich_su_xuat)

        # Trả về dữ liệu đầy đủ
        response_data = {
            'vat_tu': vat_tu_data,
            'lich_su': {
                'de_nghi_nhap': list(lich_su_nhap),
                'de_nghi_xuat': list(lich_su_xuat)
            },
            'tong_hop': {
                'tong_nhap': tong_nhap,
                'tong_xuat': tong_xuat
            }
        }

        return Response(response_data)

    def patch(self, request, ma_nha_may, ma_bravo):
        obj = self.get_object(ma_nha_may, ma_bravo)
        if not obj:
            return Response({"error": "Không tìm thấy vật tư"}, status=404)

    # không cho đổi khoá - chỉ kiểm tra bang_nha_may và ma_bravo trực tiếp
        if "bang_nha_may" in request.data or "ma_bravo" in request.data:
            return Response({"error": "Không được sửa bang_nha_may/ma_bravo"}, status=400)

        ser = VatTuUpsertSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

    # Vị trí (nếu có)
        if "ma_vi_tri_obj" in data:
            obj.ma_vi_tri = data["ma_vi_tri_obj"]

        for field in ["ten_vat_tu", "don_vi", "thong_so_ky_thuat", "ton_kho", "so_luong_kh", "bang_nha_may"]:
            if field in data:
                setattr(obj, field, data[field])

        # Handle image upload for PATCH
        if "hinh_anh_vt" in request.FILES:
            obj.hinh_anh_vt = request.FILES["hinh_anh_vt"]

        obj.save()
        return Response(VatTuSerializer(obj).data)

    def delete(self, request, ma_nha_may, ma_bravo):
        obj = self.get_object(ma_nha_may, ma_bravo)
        if not obj: return Response(status=204)
        try:
            obj.delete()
            return Response(status=204)
        except ProtectedError:
            return Response({"error":"Vật tư đang được tham chiếu (PROTECT)."}, status=409)


# VatTuImageAPIView removed - using UploadMaterialImageView from views_upload.py instead



class VatTuByQRAPIView(APIView):
    """
    GET /api/khovattu/vat-tu/qr/<ma_nha_may>/<ma_bravo>/
    Endpoint đặc biệt để lấy thông tin vật tư từ QR code
    Bây giờ yêu cầu cả mã nhà máy và mã bravo để tránh nhầm lẫn
    """
    permission_classes = [HasFactoryAccess]

    def get(self, request, ma_nha_may: str, ma_bravo: str):
        # Tìm vật tư theo cả ma_nha_may và ma_bravo
        vt = Bang_vat_tu.objects.select_related("ma_vi_tri", "bang_nha_may").filter(
            bang_nha_may__ma_nha_may=ma_nha_may,
            ma_bravo=ma_bravo
        ).first()

        if not vt:
            return Response(
                {"error": f"Không tìm thấy vật tư với mã: {ma_bravo} tại nhà máy: {ma_nha_may}"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Trả về thông tin chi tiết
        return Response(VatTuSerializer(vt).data, status=status.HTTP_200_OK)



class VatTuOverviewAPIView(APIView):
    """
    GET /api/khovattu/vat-tu/<ma_nha_may>/<ma_bravo>/overview/?limit=10
    Trả về thông tin vật tư + tổng nhập/xuất + lịch sử gần nhất (đúng nhà máy).
    """
    permission_classes = [HasFactoryAccess]

    def get(self, request, ma_nha_may: str, ma_bravo: str):
        try:
            limit = int(request.GET.get("limit", 10))
        except Exception:
            limit = 10

        vt = Bang_vat_tu.objects.select_related("ma_vi_tri", "bang_nha_may", "xuat_xu").filter(
            ma_bravo=ma_bravo, bang_nha_may__ma_nha_may=ma_nha_may
        ).first()
        if not vt:
            return Response({"error": f"Không tìm thấy vật tư {ma_bravo} tại nhà máy {ma_nha_may}"}, status=status.HTTP_404_NOT_FOUND)

        nhap_qs = Bang_de_nghi_nhap.objects.filter(vat_tu=vt).order_by("-id")[:limit]
        xuat_qs = Bang_de_nghi_xuat.objects.filter(vat_tu=vt).order_by("-id")[:limit]
        kk_qs   = Bang_kiem_ke.objects.filter(vat_tu=vt).order_by("-id")[:limit]

        tong_nhap = Bang_de_nghi_nhap.objects.filter(vat_tu=vt).aggregate(total=Sum("so_luong"))["total"] or 0
        tong_xuat = Bang_de_nghi_xuat.objects.filter(vat_tu=vt).aggregate(total=Sum("so_luong"))["total"] or 0

        def map_nhap(x):
            return {"stt": x.stt, "so_luong": x.so_luong, "thanh_tien": getattr(x, "thanh_tien", None),
                    "ngay": x.ngay_de_nghi, "created_at": getattr(x, "created_at", None)}

        def map_xuat(x):
            return {"stt": x.stt, "so_luong": x.so_luong, "ghi_chu": getattr(x, "ghi_chu", ""),
                    "ngay": x.ngay_de_nghi_xuat, "created_at": getattr(x, "created_at", None)}

        def map_kk(x):
            return {"so_thu_tu": x.so_thu_tu, "so_luong": x.so_luong,
                    "ten_vat_tu": x.ten_vat_tu, "ngay": getattr(x, "created_at", None)}

        data = {
            "vat_tu": {
                "ma_bravo": vt.ma_bravo,
                "ten_vat_tu": vt.ten_vat_tu,
                "don_vi": vt.don_vi,
                "thong_so": vt.thong_so_ky_thuat,
                "ton_kho": vt.ton_kho,
                "so_luong_kh": vt.so_luong_kh,
                "vi_tri": {
                    "ma_vi_tri": vt.ma_vi_tri.ma_vi_tri if vt.ma_vi_tri else None,
                    "ma_he_thong": vt.ma_vi_tri.ma_he_thong if vt.ma_vi_tri else None,
                    "ten_he_thong": vt.ma_vi_tri.ma_he_thong if vt.ma_vi_tri else None,
                    "kho": vt.ma_vi_tri.kho if vt.ma_vi_tri else None,
                    "ke": vt.ma_vi_tri.ke if vt.ma_vi_tri else None,
                    "ngan": vt.ma_vi_tri.ngan if vt.ma_vi_tri else None,
                    "tang": vt.ma_vi_tri.tang if vt.ma_vi_tri else None,
                    "mo_ta": vt.ma_vi_tri.mo_ta if vt.ma_vi_tri else None,
                } if vt.ma_vi_tri else None,
                "nha_may": vt.bang_nha_may.ma_nha_may if vt.bang_nha_may else None,
                "ten_nha_may": vt.bang_nha_may.ten_nha_may if vt.bang_nha_may else None,
                "image_url": f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{vt.hinh_anh_vt.url}" if vt.hinh_anh_vt else None,
                "qr_url": f"{getattr(settings, 'KHO_BACKEND_BASE_URL', 'http://localhost:8000')}{vt.ma_QR.url}" if vt.ma_QR else None,
                "xuat_xu": {
                    "ma_country": vt.xuat_xu.ma_country if vt.xuat_xu else None,
                    "ten_nuoc": vt.xuat_xu.ten_nuoc if vt.xuat_xu else None,
                    "ten_viet_tat": vt.xuat_xu.ten_viet_tat if vt.xuat_xu else None,
                    "ten_hien_thi": vt.xuat_xu.ten_viet_tat or vt.xuat_xu.ten_nuoc if vt.xuat_xu else None,
                } if vt.xuat_xu else None,
            },
            "tong_hop": {"tong_nhap": tong_nhap, "tong_xuat": tong_xuat, "chenh_lech": tong_nhap - tong_xuat},
            "lich_su": {
                "de_nghi_nhap": [map_nhap(x) for x in nhap_qs],
                "de_nghi_xuat": [map_xuat(x) for x in xuat_qs],
                "kiem_ke": [map_kk(x) for x in kk_qs],
            },
        }
        return Response(data, status=status.HTTP_200_OK)

# ===================== ĐỀ NGHỊ: GET theo (nhà máy + mã Bravo) =====================


