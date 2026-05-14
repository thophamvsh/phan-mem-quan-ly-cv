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

class KiemKeListAPIView(ListAPIView):
    """
    GET /api/khovattu/kiem-ke/?page=1&limit=20
    Trả về danh sách kiểm kê với thông tin so sánh tồn kho
    """
    serializer_class = None  # Sẽ tạo custom serializer
    permission_classes = [HasFactoryAccess]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        from .models import Bang_kiem_ke

        # Lấy tất cả kiểm kê với thông tin vật tư + annotate chênh lệch để filter ở DB
        qs = (
            Bang_kiem_ke.objects
            .select_related('vat_tu__bang_nha_may')
            .annotate(chenh_lech=F('so_luong_thuc_te') - F('so_luong'))
        )

        # Filter theo quyền nhà máy của user
        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                if not profile.is_all_factories and profile.nha_may:
                    # User chỉ có quyền truy cập nhà máy cụ thể
                    qs = qs.filter(ma_nha_may=profile.nha_may.ma_nha_may)
            except:
                # Nếu không có profile, không cho phép truy cập
                qs = qs.none()

        return qs.order_by('id')

    def filter_queryset(self, queryset):
        """Filter queryset based on request parameters"""
        # Filter theo nhà máy (có thể filter trực tiếp trên QuerySet)
        nha_may = self.request.GET.get('nha_may')
        if nha_may:
            queryset = queryset.filter(ma_nha_may=nha_may)

        # Filter theo tìm kiếm (có thể filter trực tiếp trên QuerySet)
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(ten_vat_tu__icontains=q) |
                Q(ma_bravo__icontains=q)
            )

        # Filter theo chênh lệch (đã annotate ở DB)
        chenh_lech_filter = self.request.GET.get('chenh_lech')
        if chenh_lech_filter:
            if chenh_lech_filter == 'dung':
                queryset = queryset.filter(chenh_lech=0)
            elif chenh_lech_filter == 'thua':
                queryset = queryset.filter(chenh_lech__gt=0)
            elif chenh_lech_filter == 'thieu':
                queryset = queryset.filter(chenh_lech__lt=0)
            elif chenh_lech_filter == 'co_chenh_lech':
                queryset = queryset.filter(~Q(chenh_lech=0))

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # === Thống kê nhanh bằng DB (không load hết) ===
        total_count = queryset.count()
        dung_count = queryset.filter(chenh_lech=0).count()
        thua_count = queryset.filter(chenh_lech__gt=0).count()
        thieu_count = queryset.filter(chenh_lech__lt=0).count()
        stats = {
            'total': total_count,
            'dung': dung_count,
            'thua': thua_count,
            'thieu': thieu_count,
            'chenh_lech_percentage': {
                'dung': round((dung_count / total_count * 100), 1) if total_count > 0 else 0,
                'thua': round((thua_count / total_count * 100), 1) if total_count > 0 else 0,
                'thieu': round((thieu_count / total_count * 100), 1) if total_count > 0 else 0,
            }
        }

        # === Paginate bằng DB trước khi materialize ===
        try:
            page = int(request.GET.get('page', 1))
        except Exception:
            page = 1
        try:
            limit = int(request.GET.get('limit', 20))
        except Exception:
            limit = 20

        start = (page - 1) * limit
        end = start + limit
        page_qs = queryset.order_by('id')[start:end]

        results = []
        for item in page_qs:
            vat_tu = item.vat_tu
            chenh = getattr(item, 'chenh_lech', (item.so_luong_thuc_te - item.so_luong))
            results.append({
                'id': item.id,
                'so_thu_tu': item.so_thu_tu,
                'ten_vat_tu': item.ten_vat_tu,
                'don_vi': item.don_vi,
                'so_luong_kiem_ke': item.so_luong,
                'so_luong_thuc_te': item.so_luong_thuc_te,
                'ma_bravo': item.ma_bravo,
                'ma_nha_may': item.ma_nha_may,
                'ten_nha_may': vat_tu.bang_nha_may.ten_nha_may if vat_tu and vat_tu.bang_nha_may else None,
                'so_luong_ton_kho': vat_tu.ton_kho if vat_tu else 0,
                'chenh_lech': chenh,
                'trang_thai': "Đúng" if chenh == 0 else ("Thừa" if chenh > 0 else "Thiếu"),
            })

        total_pages = (total_count + limit - 1) // limit
        return Response({
            'results': results,
            'count': total_count,
            'total_pages': total_pages,
            'current_page': page,
            'stats': stats
        }, status=status.HTTP_200_OK)


    def _calculate_stats(self, queryset):
        """Tính thống kê chênh lệch từ QuerySet (legacy method)"""
        total_count = queryset.count()
        dung_count = 0
        thua_count = 0
        thieu_count = 0

        for item in queryset:
            vat_tu = item.vat_tu
            so_luong_ton_kho = vat_tu.ton_kho if vat_tu else 0
            chenh_lech = item.so_luong - so_luong_ton_kho

            if chenh_lech == 0:
                dung_count += 1
            elif chenh_lech > 0:
                thua_count += 1
            else:
                thieu_count += 1

        return {
            'total': total_count,
            'dung': dung_count,
            'thua': thua_count,
            'thieu': thieu_count,
            'chenh_lech_percentage': {
                'dung': round((dung_count / total_count * 100), 1) if total_count > 0 else 0,
                'thua': round((thua_count / total_count * 100), 1) if total_count > 0 else 0,
                'thieu': round((thieu_count / total_count * 100), 1) if total_count > 0 else 0,
            }
        }

    def _get_trang_thai(self, so_luong_kiem_ke, so_luong_ton_kho):
        """Xác định trạng thái chênh lệch (cũ - so sánh với tồn kho)"""
        chenh_lech = so_luong_kiem_ke - so_luong_ton_kho
        if chenh_lech == 0:
            return "Đúng"
        elif chenh_lech > 0:
            return "Thừa"
        else:
            return "Thiếu"

    def _get_trang_thai_new(self, so_luong_kiem_ke, so_luong_thuc_te):
        """Xác định trạng thái chênh lệch mới (so_luong_thuc_te - so_luong_kiem_ke)"""
        chenh_lech = so_luong_thuc_te - so_luong_kiem_ke
        if chenh_lech == 0:
            return "Đúng"
        elif chenh_lech > 0:
            return "Thừa"
        else:
            return "Thiếu"



class KiemKeStatsAPIView(APIView):
    """
    GET /api/khovattu/kiem-ke/stats/
    Trả về thống kê tổng quan về kiểm kê
    """
    permission_classes = [HasFactoryAccess]

    def get(self, request):
        from .models import Bang_kiem_ke

        # Tổng số records trong database
        total_count = Bang_kiem_ke.objects.count()

        # Thống kê theo nhà máy - tối ưu bằng 1 query
        agg = (
            Bang_kiem_ke.objects
            .values('ma_nha_may')
            .annotate(count=Count('id'))
            .order_by('ma_nha_may')
        )
        stats_by_factory = {x['ma_nha_may']: x['count'] for x in agg}

        return Response({
            'total_records': total_count,
            'by_factory': stats_by_factory,
            'factories': list(stats_by_factory.keys())
        }, status=status.HTTP_200_OK)



class UpdateSoLuongThucTeAPIView(APIView):
    """
    API endpoint để cập nhật số lượng thực tế cho kiểm kê
    PATCH /api/khovattu/kiem-ke/{id}/update-so-luong-thuc-te/
    """
    permission_classes = [HasFactoryAccess]  # Temporarily allow for testing

    def patch(self, request, id):
        try:
            from .models import Bang_kiem_ke

            # Tìm kiểm kê theo ID
            kiem_ke = Bang_kiem_ke.objects.get(id=id)

            # Lấy số lượng thực tế từ request
            so_luong_thuc_te = request.data.get('so_luong_thuc_te')

            if so_luong_thuc_te is None:
                return Response({
                    "ok": False,
                    "error": "Số lượng thực tế không được để trống"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Cập nhật số lượng thực tế
            kiem_ke.so_luong_thuc_te = int(so_luong_thuc_te)
            kiem_ke.save()

            # Tính chênh lệch
            chenh_lech = kiem_ke.so_luong_thuc_te - kiem_ke.so_luong

            # Xác định trạng thái
            if chenh_lech == 0:
                trang_thai = "Đúng"
            elif chenh_lech > 0:
                trang_thai = "Thừa"
            else:
                trang_thai = "Thiếu"

            return Response({
                "ok": True,
                "message": "Cập nhật số lượng thực tế thành công",
                "data": {
                    "id": kiem_ke.id,
                    "so_luong_thuc_te": kiem_ke.so_luong_thuc_te,
                    "chenh_lech": chenh_lech,
                    "trang_thai": trang_thai
                }
            }, status=status.HTTP_200_OK)

        except Bang_kiem_ke.DoesNotExist:
            return Response({
                "ok": False,
                "error": "Không tìm thấy bản ghi kiểm kê"
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi cập nhật: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class KiemKeByMaterialAPIView(APIView):
    """
    GET /api/khovattu/kiem-ke/material/{ma_nha_may}/{ma_bravo}/
    Trả về dữ liệu kiểm kê cho một vật tư cụ thể
    """
    permission_classes = [HasFactoryAccess, CanViewInventory]

    def get(self, request, ma_nha_may, ma_bravo):
        try:
            from .models import Bang_kiem_ke

            # Lấy tất cả bản ghi kiểm kê cho vật tư này
            kiem_ke_items = Bang_kiem_ke.objects.filter(
                ma_nha_may=ma_nha_may,
                ma_bravo=ma_bravo
            ).order_by('so_thu_tu')

            if not kiem_ke_items.exists():
                return Response({
                    "ok": True,
                    "data": [],
                    "message": "Không có dữ liệu kiểm kê cho vật tư này"
                }, status=status.HTTP_200_OK)

            # Tạo dữ liệu response
            results = []
            for item in kiem_ke_items:
                # Tính chênh lệch = Số lượng thực tế - Số lượng kiểm kê
                chenh_lech = item.so_luong_thuc_te - item.so_luong

                # Xác định trạng thái
                if chenh_lech == 0:
                    trang_thai = "Đúng"
                elif chenh_lech > 0:
                    trang_thai = "Thừa"
                else:
                    trang_thai = "Thiếu"

                results.append({
                    'id': item.id,
                    'so_thu_tu': item.so_thu_tu,
                    'ma_nha_may': item.ma_nha_may,
                    'ma_bravo': item.ma_bravo,
                    'ten_vat_tu': item.ten_vat_tu,
                    'don_vi': item.don_vi,
                    'so_luong_kiem_ke': item.so_luong,
                    'so_luong_thuc_te': item.so_luong_thuc_te,
                    'chenh_lech': chenh_lech,
                    'trang_thai': trang_thai,
                })

            return Response({
                "ok": True,
                "data": results
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi lấy dữ liệu kiểm kê: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== USER PROFILE VIEWS =====


