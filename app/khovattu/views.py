import pandas as pd
import uuid as _uuid

from django.db import transaction, models
from django.db.models import F, Sum, Q, Count
from django.db.models.functions import Greatest
from django.utils import timezone
from django.conf import settings

from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from .permissions import HasFactoryAccess, HasSpecificFactoryAccess
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from django.db.models.deletion import ProtectedError


from .models import (
    Bang_vat_tu, Bang_vi_tri, Bang_kiem_ke,
    Bang_de_nghi_nhap, Bang_de_nghi_xuat, Bang_nha_may, Bang_xuat_xu
)
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
    page_size = 10
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

class ImportVatTuAPIView(APIView):
    """
    Upload Excel vật tư (mỗi dòng có cột nhà máy) -> tạo/cập nhật vật tư + sinh QR.
    Tối thiểu: ma_nha_may | ma_bravo | ten_vat_tu | don_vi
    Tuỳ chọn: thong_so_ky_thuat | ton_kho | so_luong_kh | ma_vi_tri / (ma_he_thong,kho,ke,ngan,tang)
    """
    permission_classes = [HasFactoryAccess]

    def post(self, request):
        ser = FileUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        df = pd.read_excel(ser.validated_data["file"], dtype=str).fillna("")
        created, updated, errors = 0, 0, []

        # Lấy hình ảnh từ request (nếu có)
        image_file = request.FILES.get('image')

        # Lấy mã nhà máy từ form data thay vì Excel
        ma_nha_may_param = request.data.get('ma_nha_may')
        if ma_nha_may_param:
            # Sử dụng nhà máy từ parameter
            nm = Bang_nha_may.objects.get(ma_nha_may=ma_nha_may_param.strip())
        else:
            # Fallback: lấy từ Excel như cũ
            nm = None

        with transaction.atomic():
            for i, row in df.iterrows():
                try:
                    # Nếu không có nhà máy từ parameter, lấy từ Excel
                    if nm is None:
                        nm = _get_nha_may_from_row(row)

                    ma_bravo = str(row.get("ma_bravo") or "").strip()
                    if not ma_bravo:
                        raise ValueError("Thiếu ma_bravo")

                    vt_pos = _get_vi_tri_from_excel(row)

                    # Map xuất xứ từ mã Bravo (giống logic trong admin.py)
                    xuat_xu_obj = None
                    if ma_bravo:
                        bravo_parts = ma_bravo.split('.')
                        if len(bravo_parts) >= 5:
                            country_code = bravo_parts[4]
                            try:
                                xuat_xu_obj = Bang_xuat_xu.objects.get(ma_country=country_code)
                                print(f"✅ Mapped xuất xứ {country_code} -> {xuat_xu_obj.ten_nuoc} for {ma_bravo}")
                            except Bang_xuat_xu.DoesNotExist:
                                print(f"❌ Country code {country_code} not found for {ma_bravo}")

                    # Check if this is an update (existing record)
                    existing_vat_tu = Bang_vat_tu.objects.filter(
                        ma_bravo=ma_bravo,
                        bang_nha_may=nm
                    ).first()

                    is_update = existing_vat_tu is not None

                    # For new records: use defaults, for updates: preserve existing values if Excel cell is empty
                    ton_kho_val = _to_int(row.get("ton_kho"), 0 if not is_update else None)
                    so_luong_kh_val = _to_int(row.get("so_luong_kh"), 0 if not is_update else None)

                    # For updates: if Excel cell is empty, keep existing value
                    if is_update:
                        if ton_kho_val is None:
                            ton_kho_val = existing_vat_tu.ton_kho
                        if so_luong_kh_val is None:
                            so_luong_kh_val = existing_vat_tu.so_luong_kh

                    # Double-check to prevent None values for new records
                    if ton_kho_val is None:
                        ton_kho_val = 0
                    if so_luong_kh_val is None:
                        so_luong_kh_val = 0

                    defaults = dict(
                        ten_vat_tu=str(row.get("ten_vat_tu") or "").strip(),
                        don_vi=str(row.get("don_vi") or "").strip(),
                        thong_so_ky_thuat=str(row.get("thong_so_ky_thuat") or "").strip(),
                        ton_kho=ton_kho_val,
                        so_luong_kh=so_luong_kh_val,
                        ma_vi_tri=vt_pos,
                        xuat_xu=xuat_xu_obj,  # Thêm mapping xuất xứ
                    )
                    obj, is_created = Bang_vat_tu.objects.update_or_create(
                        ma_bravo=ma_bravo,
                        bang_nha_may=nm,   # lookup theo unique constraint (nha_may, ma_bravo)
                        defaults=defaults,
                    )

                    # Cập nhật hình ảnh nếu có
                    if image_file:
                        obj.hinh_anh_vt = image_file
                        obj.save()

                    # Tạo QR code cho vật tư mới hoặc cập nhật
                    try:
                        obj.ensure_qr_image(force=True)
                        obj.save(update_fields=['ma_QR'])
                        print(f"✅ QR created for {obj.ma_bravo}")
                    except Exception as qr_error:
                        print(f"❌ QR creation failed for {obj.ma_bravo}: {qr_error}")
                        # Không crash import nếu QR lỗi

                    created += 1 if is_created else 0
                    updated += 0 if is_created else 1
                except Exception as ex:
                    errors.append(f"Row {i+2}: {ex}")

        # Collect IDs of recently created/updated items for frontend tracking
        imported_ids = []
        if created > 0 or updated > 0:
            # Get the most recently modified items for this factory ONLY
            # This ensures export only includes items from the import session
            recent_items = Bang_vat_tu.objects.filter(bang_nha_may=nm).order_by('-id')[:created + updated]
            imported_ids = [item.id for item in recent_items]

        return Response({
            "created": created,
            "updated": updated,
            "errors": errors,
            "imported_ids": imported_ids,
            "factory": nm.ma_nha_may,  # Add factory info for better tracking
            "image_uploaded": bool(image_file)  # Thông báo có upload hình ảnh không
        }, status=status.HTTP_200_OK)


class ImportKiemKeAPIView(APIView):
    """
    Tối thiểu: ma_bravo | so_luong
    Tuỳ chọn: stt/so_thu_tu | ten_vat_tu | don_vi
    ma_nha_may được truyền qua request parameter
    """
    permission_classes = [HasFactoryAccess]

    def post(self, request):
        ser = FileUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        # Lấy mã nhà máy từ request
        ma_nha_may = request.data.get('ma_nha_may')
        if not ma_nha_may:
            return Response({"error": "Thiếu mã nhà máy"}, status=status.HTTP_400_BAD_REQUEST)

        # Đọc Excel với xử lý merged cells
        df = pd.read_excel(ser.validated_data["file"], header=0).fillna("")

        # Xử lý merged cells - điền dữ liệu từ ô trước đó
        for col in df.columns:
            for i in range(1, len(df)):
                if pd.isna(df.iloc[i][col]) or df.iloc[i][col] == "":
                    df.iloc[i, df.columns.get_loc(col)] = df.iloc[i-1, df.columns.get_loc(col)]
        total_rows = len(df)
        created, errors = 0, []


        with transaction.atomic():
            # Xóa dữ liệu cũ của nhà máy này trước khi import mới
            old_count = Bang_kiem_ke.objects.filter(ma_nha_may=ma_nha_may).count()
            Bang_kiem_ke.objects.filter(ma_nha_may=ma_nha_may).delete()

            skipped_empty = 0
            for i, row in df.iterrows():
                try:
                    # Thử nhiều tên column khác nhau cho ma_bravo
                    ma_bravo = (
                        str(row.get("ma_bravo") or "") or
                        str(row.get("Mã Bravo") or "") or
                        str(row.get("Mã_Bravo") or "") or
                        str(row.get("mã bravo") or "") or
                        ""
                    ).strip()

                    # Nếu không có mã Bravo, sử dụng tên vật tư làm mã Bravo tạm thời
                    if not ma_bravo:
                        # Lấy tên vật tư từ Excel
                        ten_vat_tu_raw = (
                            str(row.get("ten_vat_tu") or "") or
                            str(row.get("Tên vật tư") or "") or
                            str(row.get("Tên_vật_tư") or "") or
                            str(row.get("tên vật tư") or "") or
                            ""
                        ).strip()

                        if ten_vat_tu_raw:
                            # Sử dụng tên vật tư làm mã Bravo tạm thời
                            ma_bravo = f"TEMP_{ten_vat_tu_raw[:50]}"  # Giới hạn 50 ký tự
                        else:
                            # Nếu không có gì, bỏ qua dòng này
                            skipped_empty += 1
                            continue

                    vt = _get_vattu_by_nm_bravo(ma_nha_may, ma_bravo)

                    # Thử nhiều tên column khác nhau cho ten_vat_tu
                    ten_vat_tu = (
                        str(row.get("ten_vat_tu") or "") or
                        str(row.get("Tên vật tư") or "") or
                        str(row.get("Tên_vật_tư") or "") or
                        str(row.get("tên vật tư") or "") or
                        str(row.get("Mô tả") or "") or
                        (vt.ten_vat_tu if vt else "") or
                        ma_bravo  # Fallback to ma_bravo if nothing else
                    ).strip()

                    # Thử nhiều tên column khác nhau cho don_vi
                    don_vi = (
                        str(row.get("don_vi") or "") or
                        str(row.get("Đơn vị") or "") or
                        str(row.get("Đơn_vị") or "") or
                        str(row.get("đơn vị") or "") or
                        (vt.don_vi if vt else "") or
                        "Cái"  # Default unit
                    ).strip()

                    # Thử nhiều tên column khác nhau cho so_luong
                    so_luong_raw = (
                        row.get("so_luong") or
                        row.get("Số lượng") or
                        row.get("Số_lượng") or
                        row.get("số lượng") or
                        "0"
                    )

                    # Xử lý số lượng - có thể là float hoặc string
                    try:
                        if isinstance(so_luong_raw, (int, float)):
                            so_luong = int(so_luong_raw)
                        else:
                            # Xử lý string như "1.00" -> 1
                            so_luong_str = str(so_luong_raw).replace(",", ".").strip()
                            so_luong = int(float(so_luong_str))
                    except (ValueError, TypeError):
                        so_luong = 0


                    Bang_kiem_ke.objects.create(
                        so_thu_tu=_to_int(row.get("stt") or row.get("so_thu_tu") or row.get("Số thứ tự"), i + 1),
                        ma_bravo=ma_bravo,  # Lưu mã Bravo
                        ma_nha_may=ma_nha_may,  # Lưu mã nhà máy từ request
                        vat_tu=vt,  # Gán ID vật tư nếu tìm thấy
                        ten_vat_tu=ten_vat_tu,
                        don_vi=don_vi,
                        so_luong=so_luong,
                    )
                    created += 1
                except Exception as ex:
                    error_msg = f"Row {i+2}: {ex}"
                    errors.append(error_msg)

        # Kiểm tra số lượng records trong database sau import
        total_in_db = Bang_kiem_ke.objects.filter(ma_nha_may=ma_nha_may).count()

        return Response({
            "created": created,
            "errors": errors,
            "skipped_empty": skipped_empty,
            "total_rows": total_rows,
            "total_in_db": total_in_db,
            "success_rate": f"{(created/(total_rows-skipped_empty)*100):.1f}%" if (total_rows-skipped_empty) > 0 else "0%"
        }, status=status.HTTP_200_OK)


class KiemKeListAPIView(ListAPIView):
    """
    GET /api/khovattu/kiem-ke/?page=1&limit=20
    Trả về danh sách kiểm kê với thông tin so sánh tồn kho
    """
    serializer_class = None  # Sẽ tạo custom serializer
    permission_classes = [HasFactoryAccess]
    pagination_class = PageNumberPagination

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


class DownloadKiemKeTemplateAPIView(APIView):
    """
    Download template Excel cho import kiểm kê
    """
    permission_classes = [HasFactoryAccess]

    def get(self, request):
        import io
        from django.http import HttpResponse

        # Tạo DataFrame mẫu (không có ma_nha_may)
        template_data = {
            'so_thu_tu': [1, 2, 3],
            'ma_bravo': ['1.26.46.001.000.00.000', '1.26.46.002.000.00.000', '1.26.46.003.000.00.000'],
            'ten_vat_tu': ['Khí SF6', 'Vật tư 2', 'Vật tư 3'],
            'don_vi': ['Kg', 'Cái', 'Mét'],
            'so_luong': [10, 5, 15],
            'so_luong_thuc_te': [0, 0, 0]  # Mặc định là 0, người dùng sẽ nhập khi kiểm kê
        }

        df = pd.DataFrame(template_data)

        # Tạo file Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Template', index=False)

            # Định dạng cột
            worksheet = writer.sheets['Template']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="template_kiem_ke.xlsx"'

        return response


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


class ExportKiemKeAPIView(APIView):
    """
    Export dữ liệu kiểm kê ra file Excel
    """
    permission_classes = [HasFactoryAccess]

    def get(self, request):
        import io
        from django.http import HttpResponse
        from .models import Bang_kiem_ke

        # Lấy tất cả dữ liệu kiểm kê
        kiem_ke_data = Bang_kiem_ke.objects.select_related('vat_tu__bang_nha_may').all().order_by('id')

        # Tạo dữ liệu export
        export_data = []
        for item in kiem_ke_data:
            vat_tu = item.vat_tu
            # Chênh lệch = Số lượng thực tế - Số lượng kiểm kê (dự kiến)
            chenh_lech = item.so_luong_thuc_te - item.so_luong

            export_data.append({
                'ID': item.id,
                'Số TT': item.so_thu_tu,
                'Mã nhà máy': item.ma_nha_may,
                'Mã Bravo': item.ma_bravo,
                'Tên vật tư': item.ten_vat_tu,
                'Đơn vị': item.don_vi,
                'Số lượng kiểm kê': item.so_luong,
                'Số lượng thực tế': item.so_luong_thuc_te,
                'Số lượng tồn kho': vat_tu.ton_kho if vat_tu else 0,  # Giữ lại để tham khảo
                'Chênh lệch': chenh_lech,
                'Trạng thái': self._get_trang_thai_new(item.so_luong, item.so_luong_thuc_te),
                'Tên nhà máy': vat_tu.bang_nha_may.ten_nha_may if vat_tu and vat_tu.bang_nha_may else None
            })

        df = pd.DataFrame(export_data)

        # Tạo file Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Kiểm kê', index=False)

            # Định dạng cột
            worksheet = writer.sheets['Kiểm kê']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="kiem_ke_export.xlsx"'

        return response

    def _get_trang_thai(self, so_luong_kiem_ke, so_luong_ton_kho):
        """Xác định trạng thái chênh lệch"""
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


class ImportDeNghiNhapAPIView(APIView):
    """Cộng ton_kho và trừ so_luong_kh (không âm) theo (ma_nha_may, ma_bravo)."""
    permission_classes = [HasFactoryAccess]

    def post(self, request):
        ser = FileUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        df = pd.read_excel(ser.validated_data["file"], dtype=str).fillna("")
        created, errors = 0, []

        # Lấy ma_nha_may từ FormData
        ma_nha_may = request.data.get("ma_nha_may")
        if not ma_nha_may:
            return Response({"error": "Thiếu ma_nha_may"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            nm = Bang_nha_may.objects.get(ma_nha_may=ma_nha_may)
        except Bang_nha_may.DoesNotExist:
            return Response({"error": f"Không tồn tại nhà máy với ma_nha_may='{ma_nha_may}'"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for i, row in df.iterrows():
                try:
                    ma_bravo = str(row.get("ma_bravo") or "").strip()
                    so_luong = _to_int(row.get("so_luong"), 0)
                    vt = Bang_vat_tu.objects.select_for_update().get(
                        ma_bravo=ma_bravo,
                        bang_nha_may__ma_nha_may=nm.ma_nha_may,
                    )

                    Bang_de_nghi_nhap.objects.create(
                        stt=_to_int(row.get("stt"), 0),
                        vat_tu=vt,
                        ma_bravo_text=ma_bravo,
                        ten_vat_tu=str(row.get("ten_vat_tu") or vt.ten_vat_tu),
                        don_vi=str(row.get("don_vi") or vt.don_vi),
                        so_luong=so_luong,
                        don_gia=_to_int(row.get("don_gia"), 0),
                        thanh_tien=_to_int(row.get("thanh_tien"), 0),
                        so_de_nghi_cap=str(row.get("so_de_nghi_cap") or ""),
                        ngay_de_nghi=_parse_dt(row.get("ngay_de_nghi")),
                        bo_phan=str(row.get("bo_phan") or ""),
                        ghi_chu=str(row.get("ghi_chu") or ""),
                    )
                    Bang_vat_tu.objects.filter(pk=vt.pk).update(
                        ton_kho=F("ton_kho") + so_luong,
                        so_luong_kh=Greatest(F("so_luong_kh") - so_luong, 0),
                    )
                    created += 1
                except Exception as ex:
                    errors.append(f"Row {i+2}: {ex}")

        return Response({"created": created, "errors": errors}, status=status.HTTP_200_OK)


class ImportDeNghiXuatAPIView(APIView):
    """Trừ ton_kho (không cho âm) theo (ma_nha_may, ma_bravo)."""
    permission_classes = [HasFactoryAccess]

    def post(self, request):
        ser = FileUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        df = pd.read_excel(ser.validated_data["file"], dtype=str).fillna("")
        created, errors = 0, []

        # Lấy ma_nha_may từ FormData
        ma_nha_may = request.data.get("ma_nha_may")
        if not ma_nha_may:
            return Response({"error": "Thiếu ma_nha_may"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            nm = Bang_nha_may.objects.get(ma_nha_may=ma_nha_may)
        except Bang_nha_may.DoesNotExist:
            return Response({"error": f"Không tồn tại nhà máy với ma_nha_may='{ma_nha_may}'"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            for i, row in df.iterrows():
                try:
                    ma_bravo = str(row.get("ma_bravo") or "").strip()
                    so_luong = _to_int(row.get("so_luong"), 0)
                    vt = Bang_vat_tu.objects.select_for_update().get(
                        ma_bravo=ma_bravo,
                        bang_nha_may__ma_nha_may=nm.ma_nha_may,
                    )

                    if vt.ton_kho < so_luong:
                        raise ValueError(f"Tồn kho ({vt.ton_kho}) < số lượng xuất ({so_luong})")

                    Bang_de_nghi_xuat.objects.create(
                        stt=_to_int(row.get("stt"), 0),
                        vat_tu=vt,
                        ma_bravo_text=ma_bravo,
                        ten_vat_tu=str(row.get("ten_vat_tu") or vt.ten_vat_tu),
                        don_vi=str(row.get("don_vi") or vt.don_vi),
                        so_luong=so_luong,
                        ngay_de_nghi_xuat=_parse_dt(row.get("ngay_de_nghi_xuat")),
                        ghi_chu=str(row.get("ghi_chu") or ""),
                    )
                    Bang_vat_tu.objects.filter(pk=vt.pk).update(
                        ton_kho=F("ton_kho") - so_luong
                    )
                    created += 1
                except Exception as ex:
                    errors.append(f"Row {i+2}: {ex}")

        return Response({"created": created, "errors": errors}, status=status.HTTP_200_OK)


class ImportViTriAPIView(APIView):
    """
    Upload Excel vị trí. Cột: ma_vi_tri, ma_he_thong, kho, ke, ngan, tang, mo_ta (tuỳ)
    Ví dụ: A1, "Đập tràn", 2, A, 1, 1
    """
    permission_classes = [HasFactoryAccess]

    def post(self, request):
        ser = FileUploadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        df = pd.read_excel(ser.validated_data["file"], dtype=str).fillna("")
        created, updated, errors = 0, 0, []

        with transaction.atomic():
            for i, row in df.iterrows():
                try:
                    code = str(row.get("ma_vi_tri") or "").strip()
                    if not code:
                        raise ValueError("Thiếu ma_vi_tri")
                    defaults = {
                        "ma_he_thong": str(row.get("ma_he_thong") or "").strip(),
                        "kho": str(row.get("kho") or "").strip(),
                        "ke": str(row.get("ke") or "").strip(),
                        "ngan": str(row.get("ngan") or "").strip(),
                        "tang": str(row.get("tang") or "").strip(),
                        "mo_ta": str(row.get("mo_ta") or "").strip(),
                    }
                    _, is_created = Bang_vi_tri.objects.update_or_create(
                        ma_vi_tri=code, defaults=defaults
                    )
                    created += 1 if is_created else 0
                    updated += 0 if is_created else 1
                except Exception as ex:
                    errors.append(f"Row {i+2}: {ex}")

        return Response({"created": created, "updated": updated, "errors": errors}, status=status.HTTP_200_OK)


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


class DownloadVatTuTemplateAPIView(APIView):
    """
    Download template Excel cho import vật tư (ĐÃ BỎ CỘT VỊ TRÍ)
    """
    permission_classes = [HasFactoryAccess]

    def get(self, request):
        import io
        from django.http import HttpResponse

        # Template mới - KHÔNG CÓ CỘT VỊ TRÍ VÀ MÃ NHÀ MÁY - Tự động từ dropdown!
        template_data = {
            'ten_vat_tu': ['Ví dụ: Khí SF6', 'Ví dụ: Cầu chì 10A', 'Vật tư VIE', 'Vật tư USA'],
            'ma_bravo': ['1.26.46.001.000.A8.000', '1.26.46.002.000.A8.000', '1.61.66.006.VIE.C3.000', '1.71.07.001.USA.C3.000'],
            'don_vi': ['Kg', 'Cái', 'Thùng', 'Bộ'],
            'thong_so_ky_thuat': ['Khí SF6, áp suất cao', 'Cầu chì 10A, 250V', 'Vật tư nhập khẩu VIE', 'Vật tư nhập khẩu USA'],
            'ton_kho': [5, 10, 8, 3],
            'so_luong_kh': [15, 20, 12, 5]
        }

        df = pd.DataFrame(template_data)

        # Tạo file Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Template_VatTu', index=False)

            # Định dạng cột
            worksheet = writer.sheets['Template_VatTu']

            # Auto-fit column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

            # Thêm ghi chú
            worksheet['A8'] = '🎯 HƯỚNG DẪN MỚI - TEMPLATE ĐƠN GIẢN NHẤT:'
            worksheet['A9'] = '✅ Cột VỊ TRÍ đã được BỎ - Tự động trích xuất từ mã Bravo!'
            worksheet['A10'] = '✅ Cột MÃ NHÀ MÁY đã được BỎ - Chọn từ dropdown!'
            worksheet['A11'] = '📋 Chỉ cần điền: ten_vat_tu | ma_bravo | don_vi | ton_kho | so_luong_kh'
            worksheet['A12'] = '🔍 Ví dụ: 1.26.46.001.000.A8.000 → Vị trí A8 (Đập tràn)'
            worksheet['A13'] = '🔍 Ví dụ: 1.61.66.006.VIE.C3.000 → Vị trí C3 (Đập tràn)'
            worksheet['A14'] = '🏭 Nhà máy: Chọn từ dropdown trong giao diện import!'
            worksheet['A15'] = '⚡ Hỗ trợ cả country code (VIE, KOR, USA) và format cũ!'
            worksheet['A16'] = '🎉 Template đơn giản nhất - Tiết kiệm thời gian tối đa!'

        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="template_vat_tu_v2.xlsx"'

        return response

# ===================== VỊ TRÍ: GET list + detail =====================

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

# ===================== VẬT TƯ: GET list + detail + overview =====================

class VatTuListAPIView(ListAPIView):
    """
    GET /api/khovattu/vat-tu/?q=&ma_nha_may=&ma_bravo=&don_vi=&ma_vi_tri=&he_thong=&page=1
    """
    serializer_class = VatTuSerializer
    permission_classes = [HasFactoryAccess]
    pagination_class = CustomPageNumberPagination

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
        vt = Bang_vat_tu.objects.select_related("ma_vi_tri", "bang_nha_may").filter(pk=pk).first()
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

class DeNghiNhapByBravoPlantAPIView(APIView):
    """
    GET /api/khovattu/de-nghi-nhap/<ma_nha_may>/<ma_bravo>/?date_from=&date_to=&limit=50&offset=0&q=
    """
    permission_classes = [HasFactoryAccess]

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
    permission_classes = [HasFactoryAccess]

    def patch(self, request, pk):
        obj = Bang_de_nghi_nhap.objects.select_related("vat_tu").filter(pk=pk).first()
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
        obj = Bang_de_nghi_nhap.objects.select_related("vat_tu").filter(pk=pk).first()
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


class DeNghiXuatByBravoPlantAPIView(APIView):
    """
    GET /api/khovattu/de-nghi-xuat/<ma_nha_may>/<ma_bravo>/?date_from=&date_to=&limit=50&offset=0&q=
    """
    permission_classes = [HasFactoryAccess]

    def get(self, request, ma_nha_may: str, ma_bravo: str):
        qs = (
            Bang_de_nghi_xuat.objects
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
            qs = qs.filter(ngay_de_nghi_xuat__gte=dfrom)
        if dto:
            qs = qs.filter(ngay_de_nghi_xuat__lte=dto)

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

        items = qs.order_by("-ngay_de_nghi_xuat", "-id")[offset: offset + limit]
        data = DeNghiXuatSerializer(items, many=True).data
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
            if vt.ton_kho < so_luong:
                return Response({"error": f"Tồn kho ({vt.ton_kho}) không đủ"}, status=400)

            # === TÍNH STT THEO PHẠM VI (NHÀ MÁY + NGÀY) ===
            ngay = _parse_dt(request.data.get("ngay_de_nghi_xuat")) or timezone.now()

            scope_qs = (
                Bang_de_nghi_xuat.objects
                .select_for_update(skip_locked=True)  # nếu dùng SQLite, bỏ skip_locked
                .filter(
                    vat_tu__bang_nha_may__ma_nha_may=ma_nha_may,
                    ngay_de_nghi_xuat__date=ngay.date()
                )
            )
            last_stt = scope_qs.order_by('-stt').values_list('stt', flat=True).first() or 0
            next_stt = last_stt + 1
            # ===============================================

            obj = Bang_de_nghi_xuat.objects.create(
                stt=next_stt,  # 👈 gán STT ở đây
                vat_tu=vt,
                ma_bravo_text=vt.ma_bravo,
                ten_vat_tu=request.data.get("ten_vat_tu") or vt.ten_vat_tu,
                don_vi=request.data.get("don_vi") or vt.don_vi,
                so_luong=so_luong,
                ngay_de_nghi_xuat=ngay,
                ghi_chu=request.data.get("ghi_chu") or "",
            )
            Bang_vat_tu.objects.filter(pk=vt.pk).update(ton_kho=F("ton_kho")-so_luong)

        return Response(DeNghiXuatSerializer(obj).data, status=201)

class DeNghiXuatDetailAPIView(APIView):
    """
    PATCH  /api/khovattu/de-nghi-xuat/<int:pk>/
    DELETE /api/khovattu/de-nghi-xuat/<int:pk>/
    """
    permission_classes = [HasFactoryAccess]

    def patch(self, request, pk):
        obj = Bang_de_nghi_xuat.objects.select_related("vat_tu").filter(pk=pk).first()
        if not obj: return Response({"error":"Không tìm thấy"}, status=404)

        old = obj.so_luong
        ser = DeNghiXuatPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        # Update fields
        for field in ["so_luong", "ngay", "ghi_chu"]:
            if field in data:
                if field == "ngay":
                    setattr(obj, "ngay_de_nghi_xuat", data[field])
                else:
                    setattr(obj, field, data[field])
        obj.save()

        delta = int(obj.so_luong) - int(old)
        if delta != 0:
            with transaction.atomic():
                vt = Bang_vat_tu.objects.select_for_update().get(pk=obj.vat_tu_id)
                if delta > 0:
                    if vt.ton_kho < delta:
                        return Response({"error": f"Tồn kho ({vt.ton_kho}) không đủ để tăng {delta}"}, status=400)
                    Bang_vat_tu.objects.filter(pk=vt.pk).update(ton_kho=F("ton_kho")-delta)
                else:
                    Bang_vat_tu.objects.filter(pk=vt.pk).update(ton_kho=F("ton_kho")+abs(delta))
        return Response(DeNghiXuatSerializer(obj).data)

    def delete(self, request, pk):
        obj = Bang_de_nghi_xuat.objects.select_related("vat_tu").filter(pk=pk).first()
        if not obj: return Response(status=204)
        with transaction.atomic():
            vt = Bang_vat_tu.objects.select_for_update().get(pk=obj.vat_tu_id)
            Bang_vat_tu.objects.filter(pk=vt.pk).update(ton_kho=F("ton_kho")+obj.so_luong)
            obj.delete()
        return Response(status=204)

# ===================== ĐỀ NGHỊ: LIST API cho toàn bộ dữ liệu =====================

class DeNghiNhapListAPIView(ListAPIView):
    """
    GET /api/khovattu/de-nghi-nhap/?q=&nha_may=&ma_bravo=&don_vi=&he_thong=&page=1&ngay_de_nghi__gte=&ngay_de_nghi__lte=
    """
    serializer_class = DeNghiNhapSerializer
    permission_classes = [HasFactoryAccess]
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


class DeNghiXuatListAPIView(ListAPIView):
    """
    GET /api/khovattu/de-nghi-xuat/?q=&nha_may=&ma_bravo=&don_vi=&he_thong=&page=1&ngay_de_nghi_xuat__gte=&ngay_de_nghi_xuat__lte=
    """
    serializer_class = DeNghiXuatSerializer
    permission_classes = [HasFactoryAccess]
    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        qs = Bang_de_nghi_xuat.objects.select_related("vat_tu", "vat_tu__bang_nha_may").all()

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
                Q(vat_tu__ten_vat_tu__icontains=q) |
                Q(ghi_chu__icontains=q)
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
        ngay_de_nghi_xuat__gte_raw = self.request.GET.get("ngay_de_nghi_xuat__gte")
        ngay_de_nghi_xuat__gte = _parse_date_for_filter(ngay_de_nghi_xuat__gte_raw)
        if ngay_de_nghi_xuat__gte:
            qs = qs.filter(ngay_de_nghi_xuat__gte=ngay_de_nghi_xuat__gte)

        ngay_de_nghi_xuat__lte_raw = self.request.GET.get("ngay_de_nghi_xuat__lte")
        ngay_de_nghi_xuat__lte = _parse_date_for_filter(ngay_de_nghi_xuat__lte_raw)
        if ngay_de_nghi_xuat__lte:
            qs = qs.filter(ngay_de_nghi_xuat__lte=ngay_de_nghi_xuat__lte)

        return qs.order_by("-ngay_de_nghi_xuat", "-id")


# ===================== HỆ THỐNG API =====================

class SystemCategoriesAPIView(APIView):
    """
    GET /api/khovattu/system-categories/
    Trả về danh sách các hệ thống có trong database
    """
    permission_classes = [HasFactoryAccess]

    def get(self, request):
        try:
            # Lấy danh sách hệ thống từ database
            systems = Bang_vi_tri.objects.values_list('ma_he_thong', flat=True).distinct()
            systems = [s for s in systems if s]  # Loại bỏ None/empty values

            # Tạo response format
            system_categories = [
                {"id": system, "name": system} for system in systems
            ]

            return Response({
                "results": system_categories,
                "count": len(system_categories)
            })
        except Exception as e:
            return Response(
                {"error": f"Không thể lấy danh sách hệ thống: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ===================== ACTION cho FE: bấm Nhập / Xuất =====================

class TaoDeNghiNhapAPIView(APIView):
    permission_classes = [HasFactoryAccess]  # Temporarily allow for testing

    def post(self, request):
        ser = NhapSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        with transaction.atomic():
            vt = _get_vattu_by_nm_bravo(data["ma_nha_may"], data["ma_bravo"])
            Bang_de_nghi_nhap.objects.create(
                vat_tu=vt,
                ma_bravo_text=vt.ma_bravo,
                ten_vat_tu=vt.ten_vat_tu,
                don_vi=vt.don_vi,
                so_luong=data["so_luong"],
                ngay_de_nghi=data.get("ngay") or timezone.now(),
            )
            Bang_vat_tu.objects.filter(pk=vt.pk).update(
                ton_kho=F("ton_kho") + data["so_luong"],
                so_luong_kh=Greatest(F("so_luong_kh") - data["so_luong"], 0),
            )

        return Response({"ok": True}, status=status.HTTP_200_OK)


class TaoDeNghiXuatAPIView(APIView):
    permission_classes = [HasFactoryAccess]  # Temporarily allow for testing
    def post(self, request):
        ser = XuatSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        with transaction.atomic():
            vt = _get_vattu_by_nm_bravo(data["ma_nha_may"], data["ma_bravo"])
            if vt.ton_kho < data["so_luong"]:
                return Response({"ok": False, "error": "Tồn kho không đủ"}, status=status.HTTP_400_BAD_REQUEST)
            # === TÍNH STT THEO PHẠM VI (NHÀ MÁY + NGÀY) ===
            ngay = data.get("ngay") or timezone.now()
            scope_qs = (
                Bang_de_nghi_xuat.objects
                .select_for_update(skip_locked=True)  # nếu dùng SQLite, bỏ skip_locked
                .filter(
                    vat_tu__bang_nha_may__ma_nha_may=data["ma_nha_may"],
                    ngay_de_nghi_xuat__date=ngay.date()
                )
            )
            last_stt = scope_qs.order_by('-stt').values_list('stt', flat=True).first() or 0
            new_stt = last_stt + 1

            Bang_de_nghi_xuat.objects.create(
                stt=new_stt,
                vat_tu=vt,
                ma_bravo_text=vt.ma_bravo,
                ten_vat_tu=vt.ten_vat_tu,
                don_vi=vt.don_vi,
                so_luong=data["so_luong"],
                ngay_de_nghi_xuat=ngay,
                ghi_chu=data.get("ghi_chu", ""),
            )
            Bang_vat_tu.objects.filter(pk=vt.pk).update(
                ton_kho=F("ton_kho") - data["so_luong"]
            )
        return Response({"ok": True}, status=status.HTTP_200_OK)


class KiemKeByMaterialAPIView(APIView):
    """
    GET /api/khovattu/kiem-ke/material/{ma_nha_may}/{ma_bravo}/
    Trả về dữ liệu kiểm kê cho một vật tư cụ thể
    """
    permission_classes = [HasFactoryAccess]

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

class GetUserProfileAPIView(APIView):
    """API để lấy thông tin profile của user hiện tại"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Lấy hoặc tạo profile cho user
            profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'is_mobile_user': True}
            )

            serializer = UserProfileSerializer(profile, context={'request': request})
            return Response({
                "ok": True,
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi lấy thông tin profile: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateUserProfileAPIView(APIView):
    """API để cập nhật thông tin profile của user hiện tại"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Lấy hoặc tạo profile cho user
            profile, created = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={'is_mobile_user': True}
            )

            serializer = UserProfileSerializer(profile, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "ok": True,
                    "message": "Cập nhật profile thành công",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "ok": False,
                    "error": "Dữ liệu không hợp lệ",
                    "details": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                "ok": False,
                "error": f"Lỗi cập nhật profile: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Function-based views for URL compatibility
def get_user_profile(request):
    """Function-based view để lấy user profile"""
    view = GetUserProfileAPIView()
    view.setup(request)
    return view.get(request)


def update_user_profile(request):
    """Function-based view để cập nhật user profile"""
    view = UpdateUserProfileAPIView()
    view.setup(request)
    return view.post(request)


# ===================== XUẤT XỨ API VIEWS =====================

class XuatXuListAPIView(ListAPIView):
    """
    API để lấy danh sách xuất xứ (quốc gia)
    GET /api/khovattu/xuat-xu/
    """
    queryset = Bang_xuat_xu.objects.all()
    serializer_class = XuatXuSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'success': True,
            'results': serializer.data,
            'count': queryset.count()
        })

