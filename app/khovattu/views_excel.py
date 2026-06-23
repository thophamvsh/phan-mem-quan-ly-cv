import pandas as pd
import io
from datetime import timedelta
from django.utils import timezone
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Q, Max
from rest_framework.views import APIView
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework import status

from core.factory_scope import filter_queryset_by_factory
from .models import Bang_vat_tu, Bang_kiem_ke, Bang_de_nghi_nhap, Bang_de_nghi_xuat, Bang_vi_tri
from .permissions import HasFactoryAccess, CanImportExcel, CanExportExcel


class ExcelResponse(HttpResponse):
    """Custom response class for Excel files"""
    def __init__(self, content, filename, *args, **kwargs):
        super().__init__(content, *args, **kwargs)
        self['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        self['Content-Disposition'] = f'attachment; filename="{filename}"'


class ExcelRenderer(BaseRenderer):
    """Custom renderer for Excel files"""
    media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    format = 'xlsx'

    def render(self, data, media_type=None, renderer_context=None):
        return data


class ExportVatTuAPIView(APIView):
    """
    Export vật tư ra file Excel - bỏ 4 cột cuối (Mô tả vị trí, Có hình ảnh, Có QR Code, Mã QR URL)
    """
    permission_classes = [HasFactoryAccess, CanExportExcel]
    renderer_classes = [ExcelRenderer]

    def get(self, request):
        # Lấy tham số filter từ request
        ma_nha_may = request.GET.get('ma_nha_may')
        he_thong = request.GET.get('he_thong')
        q = request.GET.get('q', '')
        ton_kho__gt = request.GET.get('ton_kho__gt')
        ton_kho__lt = request.GET.get('ton_kho__lt')
        so_luong_kh__gt = request.GET.get('so_luong_kh__gt')
        so_luong_kh = request.GET.get('so_luong_kh')

        # Các tham số phân trang
        page = request.GET.get('page')
        limit = request.GET.get('limit')
        export_type = request.GET.get('export_type', 'all')  # all, current_page, factory_only

        # Filter cho recently imported
        recently_imported = request.GET.get('recently_imported')
        last_import_factory = request.GET.get('last_import_factory')

        # Filter cho export theo hệ thống
        export_by_system = request.GET.get('export_by_system')
        system_name = request.GET.get('system_name')

        # Build query
        queryset = filter_queryset_by_factory(
            Bang_vat_tu.objects.select_related('ma_vi_tri', 'bang_nha_may').all(),
            request.user,
            'bang_nha_may',
            'fk',
        )

        if ma_nha_may and ma_nha_may != 'all':
            queryset = queryset.filter(bang_nha_may__ma_nha_may=ma_nha_may)

        if he_thong:
            queryset = queryset.filter(ma_vi_tri__ma_he_thong=he_thong)

        if q:
            queryset = queryset.filter(
                Q(ten_vat_tu__icontains=q) |
                Q(ma_bravo__icontains=q) |
                Q(don_vi__icontains=q)
            )

        if ton_kho__gt:
            queryset = queryset.filter(ton_kho__gt=float(ton_kho__gt))

        if ton_kho__lt:
            queryset = queryset.filter(ton_kho__lt=float(ton_kho__lt))

        if so_luong_kh__gt:
            queryset = queryset.filter(so_luong_kh__gt=float(so_luong_kh__gt))

        if so_luong_kh:
            queryset = queryset.filter(so_luong_kh=float(so_luong_kh))

        # Filter cho recently imported
        if recently_imported == 'true' and last_import_factory:
            # Lấy vật tư import gần đây của nhà máy cụ thể
            recent_date = timezone.now() - timedelta(days=7)  # 7 ngày gần đây
            queryset = queryset.filter(
                bang_nha_may__ma_nha_may=last_import_factory,
                ngay_cap_nhat__gte=recent_date
            ).order_by('-ngay_cap_nhat')

        # Filter cho export theo hệ thống
        if export_by_system == 'true' and system_name:
            queryset = queryset.filter(ma_vi_tri__ma_he_thong=system_name)

        # Sắp xếp queryset trước khi áp dụng phân trang
        queryset = queryset.order_by('id')

        # Áp dụng phân trang tùy theo export_type
        if export_type == 'current_page' and page and limit:
            # Export chỉ trang hiện tại
            page_num = int(page)
            limit_num = int(limit)
            offset = (page_num - 1) * limit_num
            queryset = queryset[offset:offset + limit_num]
        elif export_type == 'factory_only' and ma_nha_may and ma_nha_may != 'all':
            # Export tất cả dữ liệu của nhà máy (không phân trang)
            pass
        # export_type == 'all' hoặc không có export_type: export tất cả

        # Tạo dữ liệu export - BỎ 4 CỘT CUỐI
        export_data = []
        for index, vat_tu in enumerate(queryset, 1):
            export_data.append({
                'STT': index,
                'Nhà máy': vat_tu.bang_nha_may.ma_nha_may if vat_tu.bang_nha_may else '',
                'Tên vật tư': vat_tu.ten_vat_tu,
                'Mã Bravo': vat_tu.ma_bravo,
                'Đơn vị': vat_tu.don_vi,
                'SL tồn kho': vat_tu.ton_kho,
                # 'Số lượng kế hoạch': vat_tu.so_luong_kh,
                # 'Mã vị trí': vat_tu.ma_vi_tri.ma_vi_tri if vat_tu.ma_vi_tri else '',
                'Vị trí': f"Kho:{vat_tu.ma_vi_tri.kho} Kệ:{vat_tu.ma_vi_tri.ke} Ngăn:{vat_tu.ma_vi_tri.ngan} Tầng:{vat_tu.ma_vi_tri.tang}" if vat_tu.ma_vi_tri else '',
                'Hệ thống': vat_tu.ma_vi_tri.ma_he_thong if vat_tu.ma_vi_tri else '',
                # 'Thông số kỹ thuật': vat_tu.thong_so_ky_thuat or '',
                # 'Ngày cập nhật': vat_tu.updated_at.strftime('%d/%m/%Y %H:%M')
                #  if vat_tu.updated_at else '',
                # BỎ 4 CỘT CUỐI: Mô tả vị trí, Có hình ảnh, Có QR Code, Mã QR URL
            })

        # Tạo DataFrame và export Excel
        df = pd.DataFrame(export_data)

        # Tạo file Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='VatTu')

            # Lấy worksheet để format
            worksheet = writer.sheets['VatTu']

            # Auto-fit column widths
            column_widths = [5, 15, 30, 15, 10, 15, 15, 15, 15, 50, 30, 20]
            for i, width in enumerate(column_widths, 1):
                worksheet.column_dimensions[chr(64 + i)].width = width

        output.seek(0)

        # Tạo tên file
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

        if export_by_system == 'true' and system_name:
            # Export theo hệ thống
            safe_system_name = system_name.replace(' ', '_').replace('/', '_')
            if export_type == 'current_page':
                filename = f'vat_tu_he_thong_{safe_system_name}_trang_{page}_{timestamp}.xlsx'
            elif export_type == 'factory_only' and ma_nha_may and ma_nha_may != 'all':
                filename = f'vat_tu_he_thong_{safe_system_name}_nha_may_{ma_nha_may}_{timestamp}.xlsx'
            else:
                filename = f'vat_tu_he_thong_{safe_system_name}_tat_ca_{timestamp}.xlsx'
        elif recently_imported == 'true' and last_import_factory:
            filename = f'vat_tu_import_gan_day_{last_import_factory}_{timestamp}.xlsx'
        elif export_type == 'current_page':
            filename = f'vat_tu_trang_{page}_{timestamp}.xlsx'
        elif export_type == 'factory_only' and ma_nha_may and ma_nha_may != 'all':
            filename = f'vat_tu_nha_may_{ma_nha_may}_{timestamp}.xlsx'
        else:
            filename = f'vat_tu_tat_ca_{timestamp}.xlsx'

        # Tạo response
        return ExcelResponse(output.getvalue(), filename)


class ExportKiemKeAPIView(APIView):
    """
    Export kiểm kê ra file Excel
    """
    permission_classes = [HasFactoryAccess, CanExportExcel]
    renderer_classes = [ExcelRenderer]

    def get(self, request):
        # Lấy tham số filter từ request
        ma_nha_may = request.GET.get('ma_nha_may')
        ma_vat_tu = request.GET.get('ma_vat_tu')
        export_type = request.GET.get('export_type', 'all')
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        export_by_system = request.GET.get('export_by_system', 'false')
        system_name = request.GET.get('system_name')
        he_thong = request.GET.get('he_thong')


        # Build query với select_related để tối ưu
        queryset = filter_queryset_by_factory(
            Bang_kiem_ke.objects.select_related('vat_tu', 'vat_tu__ma_vi_tri', 'vat_tu__bang_nha_may').all(),
            request.user,
            'vat_tu__bang_nha_may',
            'fk',
        )

        # Filter theo nhà máy
        if ma_nha_may and ma_nha_may != 'all':
            queryset = queryset.filter(vat_tu__bang_nha_may__ma_nha_may=ma_nha_may)

        # Filter theo mã vật tư
        if ma_vat_tu:
            queryset = queryset.filter(vat_tu__ma_bravo=ma_vat_tu)

        # Filter theo hệ thống
        if he_thong:
            queryset = queryset.filter(vat_tu__ma_vi_tri__ma_he_thong=he_thong)

        # Filter theo hệ thống khi export_by_system = true
        if export_by_system == 'true' and system_name:
            queryset = queryset.filter(vat_tu__ma_vi_tri__ma_he_thong=system_name)

        # Xử lý pagination cho export_type = current_page
        if export_type == 'current_page':
            start_index = (page - 1) * limit
            end_index = start_index + limit
            queryset = queryset.order_by('id')[start_index:end_index]
        else:
            queryset = queryset.order_by('id')

        # Tạo dữ liệu export
        export_data = []
        for index, kiem_ke in enumerate(queryset, 1):
            export_data.append({
                'STT': index,
                'Mã nhà máy': kiem_ke.vat_tu.bang_nha_may.ma_nha_may if kiem_ke.vat_tu and kiem_ke.vat_tu.bang_nha_may else '',
                'Tên nhà máy': kiem_ke.vat_tu.bang_nha_may.ten_nha_may if kiem_ke.vat_tu and kiem_ke.vat_tu.bang_nha_may else '',
                'Mã Bravo': kiem_ke.vat_tu.ma_bravo if kiem_ke.vat_tu else '',
                'Tên vật tư': kiem_ke.vat_tu.ten_vat_tu if kiem_ke.vat_tu else '',
                'Đơn vị': kiem_ke.vat_tu.don_vi if kiem_ke.vat_tu else '',
                'Số lượng tồn kho': kiem_ke.so_luong,
                'Số lượng thực tế': kiem_ke.so_luong_thuc_te,
            })

        # Tạo DataFrame và export Excel
        df = pd.DataFrame(export_data)

        # Tạo file Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='KiemKe')

            # Lấy worksheet để format
            worksheet = writer.sheets['KiemKe']

            # Auto-fit column widths
            column_widths = [5, 15, 25, 15, 30, 10, 15, 15]
            for i, width in enumerate(column_widths, 1):
                worksheet.column_dimensions[chr(64 + i)].width = width

        output.seek(0)

        # Tạo tên file
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

        if export_by_system == 'true' and system_name:
            # Export theo hệ thống
            safe_system_name = system_name.replace(' ', '_').replace('/', '_')
            if export_type == 'current_page':
                filename = f'kiem_ke_he_thong_{safe_system_name}_trang_{page}_{timestamp}.xlsx'
            elif export_type == 'factory_only' and ma_nha_may and ma_nha_may != 'all':
                filename = f'kiem_ke_he_thong_{safe_system_name}_nha_may_{ma_nha_may}_{timestamp}.xlsx'
            else:
                filename = f'kiem_ke_he_thong_{safe_system_name}_tat_ca_{timestamp}.xlsx'
        elif export_type == 'current_page':
            filename = f'kiem_ke_trang_{page}_{timestamp}.xlsx'
        elif export_type == 'factory_only' and ma_nha_may and ma_nha_may != 'all':
            filename = f'kiem_ke_nha_may_{ma_nha_may}_{timestamp}.xlsx'
        else:
            filename = f'kiem_ke_tat_ca_{timestamp}.xlsx'

        # Tạo response
        return ExcelResponse(output.getvalue(), filename)


class ImportVatTuAPIView(APIView):
    """
    Import vật tư từ file Excel
    """
    permission_classes = [HasFactoryAccess, CanImportExcel]

    def post(self, request):
        file = request.FILES.get('file')
        ma_nha_may = request.data.get('ma_nha_may')

        if not file:
            return Response({'error': 'Không có file được upload'}, status=status.HTTP_400_BAD_REQUEST)

        if not ma_nha_may:
            return Response({'error': 'Thiếu mã nhà máy'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Đọc file Excel
            df = pd.read_excel(file)

            # Debug: Log columns để kiểm tra
            print(f"DEBUG - File columns: {list(df.columns)}")
            print(f"DEBUG - Column types: {[type(col) for col in df.columns]}")
            print(f"DEBUG - Column repr: {[repr(col) for col in df.columns]}")

            # Validate columns - Số lượng kế hoạch không bắt buộc
            required_columns = ['Tên vật tư', 'Mã Bravo', 'Đơn vị', 'Số lượng tồn kho']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return Response({
                    'error': f'Thiếu các cột bắt buộc: {", ".join(missing_columns)}. Các cột có sẵn: {", ".join(df.columns)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Import data
            imported_count = 0
            created_count = 0
            updated_count = 0
            imported_ids = []
            errors = []

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Tạo hoặc cập nhật vật tư
                        vat_tu, created = Bang_vat_tu.objects.get_or_create(
                            ma_bravo=row['Mã Bravo'],
                            bang_nha_may__ma_nha_may=ma_nha_may,
                            defaults={
                                'ten_vat_tu': row['Tên vật tư'],
                                'don_vi': row['Đơn vị'],
                                'ton_kho': float(row['Số lượng tồn kho']) if pd.notna(row['Số lượng tồn kho']) else 0,
                                'so_luong_kh': float(row.get('Số lượng kế hoạch', 0)) if pd.notna(row.get('Số lượng kế hoạch')) else 0,
                                'thong_so_ky_thuat': row.get('Thông số kỹ thuật', ''),
                            }
                        )

                        if created:
                            # Vật tư mới được tạo
                            created_count += 1
                            imported_count += 1
                            imported_ids.append(vat_tu.id)
                        else:
                            # Cập nhật nếu đã tồn tại - chỉ cập nhật khi có giá trị, giữ giá trị cũ khi bỏ trống
                            updated = False

                            # Kiểm tra từng cột và chỉ cập nhật khi có giá trị thực sự
                            # Tên vật tư - chỉ cập nhật khi có giá trị và khác với giá trị hiện tại
                            if (pd.notna(row['Tên vật tư']) and
                                str(row['Tên vật tư']).strip() and
                                str(row['Tên vật tư']).strip() != 'nan' and
                                str(row['Tên vật tư']).strip() != vat_tu.ten_vat_tu):
                                vat_tu.ten_vat_tu = str(row['Tên vật tư']).strip()
                                updated = True

                            # Đơn vị - chỉ cập nhật khi có giá trị và khác với giá trị hiện tại
                            if (pd.notna(row['Đơn vị']) and
                                str(row['Đơn vị']).strip() and
                                str(row['Đơn vị']).strip() != 'nan' and
                                str(row['Đơn vị']).strip() != vat_tu.don_vi):
                                vat_tu.don_vi = str(row['Đơn vị']).strip()
                                updated = True

                            # Số lượng tồn kho - chỉ cập nhật khi có giá trị số hợp lệ và khác với giá trị hiện tại
                            if pd.notna(row['Số lượng tồn kho']) and str(row['Số lượng tồn kho']).strip() and str(row['Số lượng tồn kho']).strip() != 'nan':
                                try:
                                    new_ton_kho = float(row['Số lượng tồn kho'])
                                    if new_ton_kho != vat_tu.ton_kho:
                                        vat_tu.ton_kho = new_ton_kho
                                        updated = True
                                except (ValueError, TypeError):
                                    pass

                            # Số lượng kế hoạch - chỉ cập nhật khi có giá trị số hợp lệ và khác với giá trị hiện tại
                            if (pd.notna(row.get('Số lượng kế hoạch')) and
                                str(row.get('Số lượng kế hoạch')).strip() and
                                str(row.get('Số lượng kế hoạch')).strip() != 'nan'):
                                try:
                                    new_so_luong_kh = float(row.get('Số lượng kế hoạch'))
                                    if new_so_luong_kh != vat_tu.so_luong_kh:
                                        vat_tu.so_luong_kh = new_so_luong_kh
                                        updated = True
                                except (ValueError, TypeError):
                                    pass

                            # Thông số kỹ thuật - chỉ cập nhật khi có giá trị và khác với giá trị hiện tại
                            if (pd.notna(row.get('Thông số kỹ thuật')) and
                                str(row.get('Thông số kỹ thuật')).strip() and
                                str(row.get('Thông số kỹ thuật')).strip() != 'nan' and
                                str(row.get('Thông số kỹ thuật')).strip() != (vat_tu.thong_so_ky_thuat or '')):
                                vat_tu.thong_so_ky_thuat = str(row.get('Thông số kỹ thuật')).strip()
                                updated = True

                            # Chỉ save và đếm khi có thay đổi
                            if updated:
                                vat_tu.save()
                                updated_count += 1
                                imported_count += 1
                                imported_ids.append(vat_tu.id)

                    except Exception as e:
                        errors.append(f"Dòng {index + 2}: {str(e)}")

            return Response({
                'message': f'Import thành công {imported_count} vật tư',
                'imported_count': imported_count,
                'created': created_count,
                'updated': updated_count,
                'imported_ids': imported_ids,
                'factory': ma_nha_may,
                'errors': errors
            })

        except Exception as e:
            return Response({'error': f'Lỗi import: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ImportKiemKeAPIView(APIView):
    """
    Import kiểm kê từ file Excel
    """
    permission_classes = [HasFactoryAccess, CanImportExcel]

    def post(self, request):
        file = request.FILES.get('file')
        ma_nha_may = request.data.get('ma_nha_may')

        if not file:
            return Response({'error': 'Không có file được upload'}, status=status.HTTP_400_BAD_REQUEST)

        if not ma_nha_may:
            return Response({'error': 'Thiếu mã nhà máy'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Đọc file Excel
            df = pd.read_excel(file)

            # Validate columns - Nhận cả format tiếng Việt và tiếng Anh
            required_columns_vietnamese = ['Mã Bravo', 'Số lượng tồn kho', 'Số lượng thực tế']
            required_columns_english = ['ma_bravo', 'so_luong', 'so_luong_thuc_te']

            # Kiểm tra format tiếng Việt
            missing_vietnamese = [col for col in required_columns_vietnamese if col not in df.columns]
            # Kiểm tra format tiếng Anh
            missing_english = [col for col in required_columns_english if col not in df.columns]

            if missing_vietnamese and missing_english:
                return Response({
                    'error': f'Thiếu các cột bắt buộc. Cần có: {", ".join(required_columns_vietnamese)} HOẶC {", ".join(required_columns_english)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Xác định format được sử dụng
            use_vietnamese_format = not missing_vietnamese

            # Import data
            imported_count = 0
            created_count = 0
            updated_count = 0
            errors = []

            # Lấy số thứ tự tiếp theo cho TẤT CẢ nhà máy (liên tục)
            max_stt = Bang_kiem_ke.objects.aggregate(max_stt=Max('so_thu_tu'))['max_stt'] or 0
            next_stt = max_stt + 1

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Tìm vật tư
                        try:
                            # Sử dụng format phù hợp
                            ma_bravo_key = 'Mã Bravo' if use_vietnamese_format else 'ma_bravo'
                            so_luong_key = 'Số lượng tồn kho' if use_vietnamese_format else 'so_luong'
                            so_luong_thuc_te_key = 'Số lượng thực tế' if use_vietnamese_format else 'so_luong_thuc_te'
                            ghi_chu_key = 'Ghi chú' if use_vietnamese_format else 'ghi_chu'

                            vat_tu = Bang_vat_tu.objects.get(
                                ma_bravo=row[ma_bravo_key],
                                bang_nha_may__ma_nha_may=ma_nha_may
                            )
                        except Bang_vat_tu.DoesNotExist:
                            ma_bravo_value = row['Mã Bravo'] if use_vietnamese_format else row['ma_bravo']
                            errors.append(f"Dòng {index + 2}: Không tìm thấy vật tư với mã {ma_bravo_value}")
                            continue

                        # Tạo hoặc cập nhật kiểm kê
                        kiem_ke, created = Bang_kiem_ke.objects.get_or_create(
                            vat_tu=vat_tu,
                            ma_nha_may=ma_nha_may,
                            defaults={
                                'so_thu_tu': next_stt + index,
                                'ma_bravo': row[ma_bravo_key],
                                'ten_vat_tu': vat_tu.ten_vat_tu,
                                'don_vi': vat_tu.don_vi,
                                'so_luong': float(row[so_luong_key]) if pd.notna(row[so_luong_key]) else 0,
                                'so_luong_thuc_te': float(row[so_luong_thuc_te_key]) if pd.notna(row[so_luong_thuc_te_key]) else 0,
                            }
                        )

                        if not created:
                            # Cập nhật nếu đã tồn tại
                            kiem_ke.so_luong = float(row[so_luong_key]) if pd.notna(row[so_luong_key]) else 0
                            kiem_ke.so_luong_thuc_te = float(row[so_luong_thuc_te_key]) if pd.notna(row[so_luong_thuc_te_key]) else 0
                            kiem_ke.save()

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                        imported_count += 1

                    except Exception as e:
                        errors.append(f"Dòng {index + 2}: {str(e)}")

            return Response({
                'message': f'Import thành công {imported_count} kiểm kê',
                'imported_count': imported_count,
                'created': created_count,
                'updated': updated_count,
                'errors': errors,
                'factory': ma_nha_may
            })

        except Exception as e:
            return Response({'error': f'Lỗi import: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ImportDeNghiNhapAPIView(APIView):
    """
    Import đề nghị nhập từ file Excel
    """
    permission_classes = [HasFactoryAccess, CanImportExcel]

    def post(self, request):
        file = request.FILES.get('file')
        ma_nha_may = request.data.get('ma_nha_may')
        nguoi_de_nghi = request.data.get('nguoi_de_nghi', '')

        if not file:
            return Response({'error': 'Không có file được upload'}, status=status.HTTP_400_BAD_REQUEST)

        if not ma_nha_may:
            return Response({'error': 'Thiếu mã nhà máy'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Đọc file Excel
            df = pd.read_excel(file)

            # Validate columns - Nhận cả format tiếng Việt và tiếng Anh
            required_columns_vietnamese = ['Mã Bravo', 'Số lượng yêu cầu', 'Đơn giá', 'Số đề nghị cấp', 'Bộ phận']
            required_columns_english = ['ma_bravo', 'so_luong', 'don_gia', 'so_de_nghi_cap', 'bo_phan']

            # Kiểm tra format tiếng Việt
            missing_vietnamese = [col for col in required_columns_vietnamese if col not in df.columns]
            # Kiểm tra format tiếng Anh
            missing_english = [col for col in required_columns_english if col not in df.columns]

            if missing_vietnamese and missing_english:
                return Response({
                    'error': f'Thiếu các cột bắt buộc. Cần có: {", ".join(required_columns_vietnamese)} HOẶC {", ".join(required_columns_english)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Xác định format được sử dụng
            use_vietnamese_format = not missing_vietnamese

            # Import data
            imported_count = 0
            errors = []

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Tìm vật tư
                        try:
                            # Sử dụng format phù hợp
                            ma_bravo_key = 'Mã Bravo' if use_vietnamese_format else 'ma_bravo'
                            so_luong_key = 'Số lượng yêu cầu' if use_vietnamese_format else 'so_luong'
                            don_gia_key = 'Đơn giá' if use_vietnamese_format else 'don_gia'
                            so_de_nghi_cap_key = 'Số đề nghị cấp' if use_vietnamese_format else 'so_de_nghi_cap'
                            bo_phan_key = 'Bộ phận' if use_vietnamese_format else 'bo_phan'
                            ghi_chu_key = 'Ghi chú' if use_vietnamese_format else 'ghi_chu'

                            vat_tu = Bang_vat_tu.objects.get(
                                ma_bravo=row[ma_bravo_key],
                                bang_nha_may__ma_nha_may=ma_nha_may
                            )
                        except Bang_vat_tu.DoesNotExist:
                            ma_bravo_value = row['Mã Bravo'] if use_vietnamese_format else row['ma_bravo']
                            errors.append(f"Dòng {index + 2}: Không tìm thấy vật tư với mã {ma_bravo_value}")
                            continue

                        # Tạo đề nghị nhập
                        de_nghi_nhap = Bang_de_nghi_nhap.objects.create(
                            vat_tu=vat_tu,
                            ma_bravo_text=vat_tu.ma_bravo,
                            ten_vat_tu=vat_tu.ten_vat_tu,
                            don_vi=vat_tu.don_vi,
                            so_luong=float(row[so_luong_key]) if pd.notna(row[so_luong_key]) else 0,
                            don_gia=float(row[don_gia_key]) if pd.notna(row[don_gia_key]) else 0,
                            thanh_tien=float(row[so_luong_key]) * float(row[don_gia_key]) if pd.notna(row[so_luong_key]) and pd.notna(row[don_gia_key]) else 0,
                            so_de_nghi_cap=row[so_de_nghi_cap_key],
                            bo_phan=row[bo_phan_key],
                            ghi_chu=row.get(ghi_chu_key, ''),
                            nguoi_de_nghi=nguoi_de_nghi,
                            ngay_de_nghi=timezone.now(),
                            stt=index + 1
                        )

                        imported_count += 1

                    except Exception as e:
                        errors.append(f"Dòng {index + 2}: {str(e)}")

            return Response({
                'message': f'Import thành công {imported_count} đề nghị nhập',
                'imported_count': imported_count,
                'errors': errors
            })

        except Exception as e:
            return Response({'error': f'Lỗi import: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ImportDeNghiXuatAPIView(APIView):
    """
    Import đề nghị xuất từ file Excel
    """
    permission_classes = [HasFactoryAccess, CanImportExcel]

    def post(self, request):
        file = request.FILES.get('file')
        ma_nha_may = request.data.get('ma_nha_may')
        nguoi_de_nghi = request.data.get('nguoi_de_nghi', '')

        if not file:
            return Response({'error': 'Không có file được upload'}, status=status.HTTP_400_BAD_REQUEST)

        if not ma_nha_may:
            return Response({'error': 'Thiếu mã nhà máy'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Đọc file Excel
            df = pd.read_excel(file)

            # Validate columns - Nhận cả format tiếng Việt và tiếng Anh
            required_columns_vietnamese = ['Mã vật tư', 'Số lượng yêu cầu']
            required_columns_vietnamese_bravo = ['Mã Bravo', 'Số lượng yêu cầu']
            required_columns_english = ['ma_bravo', 'so_luong']

            # Kiểm tra format tiếng Việt (Mã vật tư)
            missing_vietnamese = [col for col in required_columns_vietnamese if col not in df.columns]
            # Kiểm tra format tiếng Việt (Mã Bravo)
            missing_vietnamese_bravo = [col for col in required_columns_vietnamese_bravo if col not in df.columns]
            # Kiểm tra format tiếng Anh
            missing_english = [col for col in required_columns_english if col not in df.columns]

            if missing_vietnamese and missing_vietnamese_bravo and missing_english:
                return Response({
                    'error': f'Thiếu các cột bắt buộc. Cần có: {", ".join(required_columns_vietnamese)} HOẶC {", ".join(required_columns_vietnamese_bravo)} HOẶC {", ".join(required_columns_english)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Xác định format được sử dụng
            use_vietnamese_format = not missing_vietnamese
            use_vietnamese_bravo_format = not missing_vietnamese_bravo

            # Import data
            imported_count = 0
            errors = []

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Tìm vật tư
                        try:
                            # Sử dụng format phù hợp
                            if use_vietnamese_format:
                                ma_bravo_key = 'Mã vật tư'
                            elif use_vietnamese_bravo_format:
                                ma_bravo_key = 'Mã Bravo'
                            else:
                                ma_bravo_key = 'ma_bravo'

                            so_luong_key = 'Số lượng yêu cầu' if (use_vietnamese_format or use_vietnamese_bravo_format) else 'so_luong'
                            ghi_chu_key = 'Ghi chú' if (use_vietnamese_format or use_vietnamese_bravo_format) else 'ghi_chu'

                            vat_tu = Bang_vat_tu.objects.get(
                                ma_bravo=row[ma_bravo_key],
                                bang_nha_may__ma_nha_may=ma_nha_may
                            )
                        except Bang_vat_tu.DoesNotExist:
                            ma_bravo_value = row['Mã vật tư'] if use_vietnamese_format else row['ma_bravo']
                            errors.append(f"Dòng {index + 2}: Không tìm thấy vật tư với mã {ma_bravo_value}")
                            continue

                        # Tạo đề nghị xuất
                        de_nghi_xuat = Bang_de_nghi_xuat.objects.create(
                            vat_tu=vat_tu,
                            ma_bravo_text=vat_tu.ma_bravo,
                            ten_vat_tu=vat_tu.ten_vat_tu,
                            don_vi=vat_tu.don_vi,
                            so_luong=float(row[so_luong_key]) if pd.notna(row[so_luong_key]) else 0,
                            ghi_chu=row.get(ghi_chu_key, ''),
                            nguoi_de_nghi=nguoi_de_nghi,
                            ngay_de_nghi_xuat=timezone.now(),
                            stt=index + 1
                        )

                        imported_count += 1

                    except Exception as e:
                        errors.append(f"Dòng {index + 2}: {str(e)}")

            return Response({
                'message': f'Import thành công {imported_count} đề nghị xuất',
                'imported_count': imported_count,
                'errors': errors
            })

        except Exception as e:
            return Response({'error': f'Lỗi import: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ImportViTriAPIView(APIView):
    """
    Import vị trí từ file Excel
    """
    permission_classes = [HasFactoryAccess, CanImportExcel]

    def post(self, request):
        file = request.FILES.get('file')

        if not file:
            return Response({'error': 'Không có file được upload'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Đọc file Excel
            df = pd.read_excel(file)

            # Validate columns
            required_columns = ['Mã vị trí', 'Tên vị trí', 'Mã hệ thống']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return Response({
                    'error': f'Thiếu các cột bắt buộc: {", ".join(missing_columns)}'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Import data
            imported_count = 0
            errors = []

            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Tạo hoặc cập nhật vị trí
                        vi_tri, created = Bang_vi_tri.objects.get_or_create(
                            ma_vi_tri=row['Mã vị trí'],
                            defaults={
                                'ten_vi_tri': row['Tên vị trí'],
                                'ma_he_thong': row['Mã hệ thống'],
                                'ghi_chu': row.get('Ghi chú', ''),
                            }
                        )

                        if not created:
                            # Cập nhật nếu đã tồn tại
                            vi_tri.ten_vi_tri = row['Tên vị trí']
                            vi_tri.ma_he_thong = row['Mã hệ thống']
                            vi_tri.ghi_chu = row.get('Ghi chú', '')
                            vi_tri.save()

                        imported_count += 1

                    except Exception as e:
                        errors.append(f"Dòng {index + 2}: {str(e)}")

            return Response({
                'message': f'Import thành công {imported_count} vị trí',
                'imported_count': imported_count,
                'errors': errors
            })

        except Exception as e:
            return Response({'error': f'Lỗi import: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DownloadVatTuTemplateAPIView(APIView):
    """
    Download template Excel cho import vật tư (ĐÃ BỎ CỘT VỊ TRÍ)
    """
    permission_classes = [HasFactoryAccess, CanExportExcel]

    def get(self, request):
        import io
        from django.http import HttpResponse

        # Template mới - KHÔNG CÓ CỘT VỊ TRÍ VÀ MÃ NHÀ MÁY - Tự động từ dropdown!
        template_data = {
            'Tên vật tư': ['Ví dụ: Khí SF6', 'Ví dụ: Cầu chì 10A', 'Vật tư VIE', 'Vật tư USA'],
            'Mã Bravo': ['1.26.46.001.000.A8.000', '1.26.46.002.000.A8.000', '1.61.66.006.VIE.C3.000', '1.71.07.001.USA.C3.000'],
            'Đơn vị': ['Kg', 'Cái', 'Thùng', 'Bộ'],
            'Thông số kỹ thuật': ['Khí SF6, áp suất cao', 'Cầu chì 10A, 250V', 'Vật tư nhập khẩu VIE', 'Vật tư nhập khẩu USA'],
            'Số lượng tồn kho': [5, 10, 8, 3],
            'Số lượng kế hoạch': [15, 20, 12, 5]
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
            worksheet['A11'] = '📋 Chỉ cần điền: Tên vật tư | Mã Bravo | Đơn vị | Số lượng tồn kho | Số lượng kế hoạch'
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


class DownloadDeNghiXuatTemplateAPIView(APIView):
    """
    Download template Excel cho import đề nghị xuất
    """
    permission_classes = [HasFactoryAccess, CanExportExcel]

    def get(self, request):
        import io
        from django.http import HttpResponse

        # Template cho đề nghị xuất - Format giống template vật tư
        template_data = {
            'Tên vật tư': ['Ví dụ: Khí SF6', 'Ví dụ: Cầu chì 10A', 'Vật tư VIE', 'Vật tư USA'],
            'Mã Bravo': ['1.26.46.001.000.A8.000', '1.26.46.002.000.A8.000', '1.61.66.006.VIE.C3.000', '1.71.07.001.USA.C3.000'],
            'Đơn vị': ['Kg', 'Cái', 'Thùng', 'Bộ'],
            'Số lượng yêu cầu': [5, 10, 8, 3],
            'Người đề nghị': ['Nguyễn Văn A', 'Trần Thị B', 'Lê Văn C', 'Phạm Văn D'],
            'Ghi chú': ['Xuất cho bảo trì', 'Xuất cho dự án', 'Xuất khẩn cấp', 'Xuất theo kế hoạch']
        }

        df = pd.DataFrame(template_data)

        # Tạo file Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Template_DeNghiXuat', index=False)

            # Định dạng và thêm hướng dẫn
            worksheet = writer.sheets['Template_DeNghiXuat']

            # Set column widths cho 6 cột
            column_widths = [30, 25, 10, 15, 20, 30]
            for i, width in enumerate(column_widths, 1):
                worksheet.column_dimensions[chr(64 + i)].width = width

            # Thêm hướng dẫn
            worksheet['A7'] = '🎯 HƯỚNG DẪN IMPORT ĐỀ NGHỊ XUẤT:'
            worksheet['A8'] = '✅ Tên vật tư: Tên vật tư (tự động từ mã Bravo)'
            worksheet['A9'] = '✅ Mã Bravo: Mã Bravo của vật tư cần xuất (BẮT BUỘC)'
            worksheet['A10'] = '✅ Đơn vị: Đơn vị (tự động từ mã Bravo)'
            worksheet['A11'] = '✅ Số lượng yêu cầu: Số lượng cần xuất (phải <= tồn kho) (BẮT BUỘC)'
            worksheet['A12'] = '✅ Người đề nghị: Tên người đề nghị xuất (tùy chọn)'
            worksheet['A13'] = '✅ Ghi chú: Lý do xuất (tùy chọn)'
            worksheet['A14'] = '✅ KHÔNG CẦN điền mã nhà máy - Tự động từ dropdown!'
            worksheet['A15'] = '✅ File này đã có sẵn dữ liệu mẫu - Xóa và thay thế bằng dữ liệu thật'
            worksheet['A16'] = '✅ Lưu file và import lại'
            worksheet['A17'] = '✅ Kiểm tra kết quả import'

        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="template_de_nghi_xuat.xlsx"'

        return response


class DownloadDeNghiNhapTemplateAPIView(APIView):
    """
    Download template Excel cho import đề nghị nhập - Tiêu đề tiếng Việt
    """
    permission_classes = [HasFactoryAccess, CanExportExcel]

    def get(self, request):
        import io
        from django.http import HttpResponse
        import pandas as pd

        # Template cho đề nghị nhập - Format giống template vật tư
        template_data = {
            'Tên vật tư': ['Ví dụ: Khí SF6', 'Ví dụ: Dây curoa SPA 3752', 'Vật tư VIE', 'Vật tư USA'],
            'Mã Bravo': ['1.26.46.001.000.A8.000', '4.88.52.001.JPN.C7.000', '1.61.66.006.VIE.C3.000', '1.71.07.001.USA.C3.000'],
            'Đơn vị': ['Kg', 'Sợi', 'Thùng', 'Bộ'],
            'Số lượng yêu cầu': [5, 2, 8, 3],
            'Đơn giá': [100000, 50000, 75000, 120000],
            'Thành tiền': [500000, 100000, 600000, 360000],
            'Số đề nghị cấp': ['TEST001', 'TEST002', 'TEST003', 'TEST004'],
            'Bộ phận': ['Kế hoạch đầu tư', 'Kế hoạch đầu tư', 'Bảo trì', 'Vận hành'],
            'Người đề nghị': ['Nguyễn Văn A', 'Trần Thị B', 'Lê Văn C', 'Phạm Văn D'],
            'Ghi chú': ['Nhập cho dự án', 'Nhập cho bảo trì', 'Nhập khẩn cấp', 'Nhập theo kế hoạch']
        }

        df = pd.DataFrame(template_data)

        # Tạo file Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Template_DeNghiNhap', index=False)

            # Định dạng và thêm hướng dẫn
            worksheet = writer.sheets['Template_DeNghiNhap']

            # Set column widths cho 10 cột
            column_widths = [30, 25, 10, 15, 15, 15, 20, 20, 20, 30]
            for i, width in enumerate(column_widths, 1):
                worksheet.column_dimensions[chr(64 + i)].width = width

            # Thêm hướng dẫn
            worksheet['A7'] = '🎯 HƯỚNG DẪN IMPORT ĐỀ NGHỊ NHẬP:'
            worksheet['A8'] = '✅ Tên vật tư: Tên vật tư (tự động từ mã Bravo)'
            worksheet['A9'] = '✅ Mã Bravo: Mã Bravo của vật tư cần nhập (BẮT BUỘC)'
            worksheet['A10'] = '✅ Đơn vị: Đơn vị (tự động từ mã Bravo)'
            worksheet['A11'] = '✅ Số lượng yêu cầu: Số lượng cần nhập (BẮT BUỘC)'
            worksheet['A12'] = '✅ Đơn giá: Giá đơn vị (BẮT BUỘC)'
            worksheet['A13'] = '✅ Thành tiền: Số lượng × Đơn giá (tự động tính)'
            worksheet['A14'] = '✅ Số đề nghị cấp: Mã đề nghị (BẮT BUỘC)'
            worksheet['A15'] = '✅ Bộ phận: Bộ phận đề nghị (BẮT BUỘC)'
            worksheet['A16'] = '✅ Người đề nghị: Tên người đề nghị nhập (tùy chọn)'
            worksheet['A17'] = '✅ Ghi chú: Lý do nhập (tùy chọn)'
            worksheet['A18'] = '✅ KHÔNG CẦN điền mã nhà máy - Tự động từ dropdown!'
            worksheet['A19'] = '✅ File này đã có sẵn dữ liệu mẫu - Xóa và thay thế bằng dữ liệu thật'
            worksheet['A20'] = '✅ Lưu file và import lại'
            worksheet['A21'] = '✅ Kiểm tra kết quả import'

        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="template_de_nghi_nhap.xlsx"'

        return response


class DownloadKiemKeTemplateAPIView(APIView):
    """
    Download template Excel cho import kiểm kê - Tiêu đề tiếng Việt
    """
    permission_classes = [HasFactoryAccess, CanExportExcel]

    def get(self, request):
        import io
        from django.http import HttpResponse
        import pandas as pd

        # Template cho kiểm kê - Format giống template vật tư
        template_data = {
            'Tên vật tư': ['Ví dụ: Khí SF6', 'Ví dụ: Cầu chì 10A', 'Vật tư VIE', 'Vật tư USA'],
            'Mã Bravo': ['1.26.46.001.000.A8.000', '1.26.46.002.000.A8.000', '1.61.66.006.VIE.C3.000', '1.71.07.001.USA.C3.000'],
            'Đơn vị': ['Kg', 'Cái', 'Thùng', 'Bộ'],
            'Số lượng tồn kho': [5, 10, 8, 3],
            'Số lượng thực tế': [0, 0, 0, 0]  # Mặc định là 0, người dùng sẽ nhập khi kiểm kê
        }

        df = pd.DataFrame(template_data)

        # Tạo file Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Template_KiemKe', index=False)

            # Định dạng và thêm hướng dẫn
            worksheet = writer.sheets['Template_KiemKe']

            # Set column widths cho 5 cột
            column_widths = [30, 25, 10, 15, 15]
            for i, width in enumerate(column_widths, 1):
                worksheet.column_dimensions[chr(64 + i)].width = width

            # Thêm hướng dẫn
            worksheet['A7'] = '🎯 HƯỚNG DẪN IMPORT KIỂM KÊ:'
            worksheet['A8'] = '✅ Tên vật tư: Tên vật tư (tự động từ mã Bravo)'
            worksheet['A9'] = '✅ Mã Bravo: Mã Bravo của vật tư cần kiểm kê (BẮT BUỘC)'
            worksheet['A10'] = '✅ Đơn vị: Đơn vị (tự động từ mã Bravo)'
            worksheet['A11'] = '✅ Số lượng tồn kho: Số lượng theo sổ sách (BẮT BUỘC)'
            worksheet['A12'] = '✅ Số lượng thực tế: Số lượng thực tế khi kiểm kê (BẮT BUỘC)'
            worksheet['A13'] = '✅ KHÔNG CẦN điền mã nhà máy - Tự động từ dropdown!'
            worksheet['A14'] = '✅ File này đã có sẵn dữ liệu mẫu - Xóa và thay thế bằng dữ liệu thật'
            worksheet['A15'] = '✅ Lưu file và import lại'
            worksheet['A16'] = '✅ Kiểm tra kết quả import'

        output.seek(0)

        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="template_kiem_ke.xlsx"'

        return response
