from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
import tablib

from .models import NguongThongSo, ThietBi
from .serializers import NguongThongSoSerializer
from .admin import NguongThongSoResource

class NguongThongSoViewSet(viewsets.ModelViewSet):
    """ViewSet xử lý cấu hình ngưỡng thông số (alarm, trip, rated)"""
    queryset = NguongThongSo.objects.all().order_by('nha_may', 'thiet_bi__ma_day_du', 'ma_thong_so')
    serializer_class = NguongThongSoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Lọc theo nhà máy
        nha_may = self.request.query_params.get('nha_may')
        if nha_may:
            queryset = queryset.filter(nha_may=nha_may)
            
        # Lọc theo thiết bị cụ thể
        thiet_bi_id = self.request.query_params.get('thiet_bi')
        if thiet_bi_id:
            queryset = queryset.filter(thiet_bi_id=thiet_bi_id)
            
        # Tìm kiếm theo từ khóa
        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(
                Q(ma_thong_so__icontains=q) |
                Q(ten_thong_so__icontains=q) |
                Q(thiet_bi__ten__icontains=q) |
                Q(thiet_bi__ma_day_du__icontains=q)
            )
        return queryset

    @action(detail=False, methods=['get'])
    def excel_template(self, request):
        """Tải file template Excel trống cho ngưỡng thông số"""
        try:
            resource = NguongThongSoResource()
            # Xuất dataset rỗng để lấy tiêu đề cột
            dataset = resource.export(NguongThongSo.objects.none())
            response = HttpResponse(
                dataset.xlsx,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="NguongThongSo_Template.xlsx"'
            return response
        except Exception as e:
            return JsonResponse({'error': f'Lỗi hệ thống: {str(e)}'}, status=500)

    @action(detail=False, methods=['get'])
    def excel_export(self, request):
        """Xuất toàn bộ ngưỡng thông số (theo bộ lọc) ra file Excel"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            resource = NguongThongSoResource()
            dataset = resource.export(queryset)
            response = HttpResponse(
                dataset.xlsx,
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="NguongThongSo_Export.xlsx"'
            return response
        except Exception as e:
            return JsonResponse({'error': f'Lỗi hệ thống: {str(e)}'}, status=500)

    @action(detail=False, methods=['post'])
    def excel_import(self, request):
        """Import/cập nhật hàng loạt ngưỡng thông số từ file Excel"""
        try:
            if 'file' not in request.FILES:
                return JsonResponse({'error': 'Không tìm thấy file tải lên.'}, status=400)
            file = request.FILES['file']
            
            dataset = tablib.Dataset()
            dataset.load(file.read(), format='xlsx')
            
            resource = NguongThongSoResource()
            result = resource.import_data(dataset, dry_run=False)
            
            if result.has_errors():
                error_list = []
                for row in result.rows:
                    for error in row.errors:
                        error_list.append(f"Dòng {row.row_number}: {str(error.error)}")
                return JsonResponse({
                    'error': 'Import thất bại với các lỗi sau:',
                    'details': error_list
                }, status=400)
                
            total_saved = result.totals["update"] + result.totals["new"]
            return JsonResponse({
                'message': f'Import thành công {total_saved} dòng dữ liệu!'
            })
        except Exception as e:
            return JsonResponse({'error': f'Lỗi hệ thống: {str(e)}'}, status=500)
