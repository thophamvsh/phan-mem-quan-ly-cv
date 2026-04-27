from rest_framework.decorators import action
from rest_framework.response import Response
from  rest_framework import viewsets, filters, status
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
import io
from core.factory_scope import (
    apply_request_factory_to_serializer,
    filter_queryset_by_factory,
    get_user_factory_name,
    has_all_factory_access,
)
from .models import ThietBi, VatTu, ThietBiVatTu, ThongSoVanHanh, AnToanThietBi, DinhKem, ThongSoToMay
from .serializers import (
    ThietBiSerializer, ThietBiListSerializer, ThietBiDetailSerializer,
    VatTuSerializer, ThietBiVatTuSerializer, ThongSoVanHanhSerializer,
    ThongSoVanHanhCreateSerializer, AnToanThietBiSerializer, DinhKemSerializer,
    ThongSoToMaySerializer, ThongSoToMayCreateSerializer
)


def _ensure_thiet_bi_access(user, thiet_bi):
    if not thiet_bi or has_all_factory_access(user):
        return
    allowed = filter_queryset_by_factory(
        ThietBi.objects.filter(pk=thiet_bi.pk),
        user,
        'nha_may',
        'string',
    ).exists()
    if not allowed:
        raise PermissionDenied("Bạn không có quyền thao tác với thiết bị của nhà máy này.")


class ThietBiViewSet(viewsets.ModelViewSet):
    """ViewSet cho quản lý thiết bị"""
    queryset = ThietBi.objects.all()
    serializer_class = ThietBiSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['loai', 'trang_thai', 'nha_che_tao', 'nha_cung_cap', 'cap', 'cha']
    search_fields = ['ten', 'ma', 'ma_day_du', 'so_serial', 'mo_ta_ky_thuat']
    ordering_fields = ['ten', 'ma_day_du', 'thu_tu', 'do_uu_tien', 'cap']
    ordering = ['cha__id', 'thu_tu', 'ten']

    def get_serializer_class(self):
        if self.action == 'list':
            return ThietBiListSerializer
        elif self.action == 'retrieve':
            return ThietBiDetailSerializer
        return ThietBiSerializer

    def get_queryset(self):
        """
        Override get_queryset để tìm kiếm linh hoạt hơn
        Tìm kiếm theo từng phần của mã thiết bị (split by '.')
        """
        queryset = super().get_queryset()
        queryset = filter_queryset_by_factory(queryset, self.request.user, 'nha_may', 'string')

        # Lấy search parameter từ query params
        search_param = self.request.query_params.get('q', None)

        if search_param:
            # Kiểm tra xem có phải là filter cascade không (có dấu chấm và >= 3 parts)
            # Ví dụ: "SH.TB.H1" là filter cascade
            # Còn "0K36" hoặc "GOV" là search keyword
            parts = search_param.split('.')
            is_cascade_filter = len(parts) >= 3

            if is_cascade_filter:
                # Filter cascade: tìm thiết bị có ma_day_du bắt đầu với search_param
                # hoặc chính xác bằng search_param
                queryset = queryset.filter(
                    Q(ma_day_du__startswith=search_param) | Q(ma_day_du=search_param)
                )
            else:
                # Search keyword: tìm kiếm linh hoạt trong nhiều trường
                search_query = Q()

                # Tìm kiếm trong các trường cơ bản
                search_query |= Q(ten__icontains=search_param)
                search_query |= Q(ma__icontains=search_param)
                search_query |= Q(ma_day_du__icontains=search_param)
                search_query |= Q(so_serial__icontains=search_param)
                search_query |= Q(mo_ta_ky_thuat__icontains=search_param)
                search_query |= Q(nha_che_tao__icontains=search_param)
                search_query |= Q(nha_cung_cap__icontains=search_param)
                search_query |= Q(nha_may__icontains=search_param)
                search_query |= Q(nuoc_san_xuat__icontains=search_param)

                queryset = queryset.filter(search_query).distinct()

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, 'nha_may', 'string')
        )

    def perform_update(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, 'nha_may', 'string')
        )

    @action(detail=True, methods=['get'])
    def con(self, request, pk=None):
        """Lấy danh sách thiết bị con"""
        thiet_bi = self.get_object()
        con = thiet_bi.con.all()
        serializer = ThietBiListSerializer(con, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def cay_phan_cap(self, request):
        """Lấy cây phân cấp thiết bị"""
        # Lấy tất cả thiết bị cấp 0 (không có cha)
        goc = self.get_queryset().filter(cha__isnull=True).order_by('thu_tu', 'ten')
        serializer = ThietBiDetailSerializer(goc, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def tim_kiem(self, request):
        """Tìm kiếm thiết bị theo nhiều tiêu chí"""
        query = request.query_params.get('q', '')
        if query:
            queryset = self.get_queryset().filter(
                Q(ten__icontains=query) |
                Q(ma__icontains=query) |
                Q(ma_day_du__icontains=query) |
                Q(so_serial__icontains=query)
            )
        else:
            queryset = self.get_queryset()

        serializer = ThietBiListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def cap_0_codes(self, request):
        """Lấy danh sách mã thiết bị cấp 0 từ tất cả thiết bị"""
        try:
            # Lấy tất cả thiết bị với ma_day_du
            all_thiet_bi = self.get_queryset().filter(
                ma_day_du__isnull=False
            ).values('ma_day_du', 'ten')

            # Extract mã cấp 0 và lấy tên từ thiết bị có ma_day_du trùng với mã cấp 0
            cap_0_info = {}  # {code: {'ten': ten, 'ma': ma}}

            for tb in all_thiet_bi:
                ma_day_du = tb['ma_day_du']
                if ma_day_du:
                    parts = ma_day_du.split('.')
                    if len(parts) >= 3:
                        cap_0_code = '.'.join(parts[:3])

                        # Nếu ma_day_du trùng với mã cấp 0, lấy tên thật
                        if ma_day_du == cap_0_code:
                            cap_0_info[cap_0_code] = {
                                'ten': tb['ten'],
                                'ma': parts[-1]
                            }
                        # Nếu chưa có thiết bị cấp 0 này, tạo với tên mặc định
                        elif cap_0_code not in cap_0_info:
                            cap_0_info[cap_0_code] = {
                                'ten': f'Thiết bị {parts[-1]}',
                                'ma': parts[-1]
                            }

            # Tạo danh sách thiết bị cấp 0
            cap_0_devices = []
            for code in sorted(cap_0_info.keys()):
                info = cap_0_info[code]
                cap_0_devices.append({
                    'id': code,
                    'ma': info['ma'],
                    'ten': info['ten'],
                    'ma_day_du': code,
                    'cap': 0
                })

            return Response(cap_0_devices)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def cap_1_by_parent(self, request):
        """Lấy danh sách thiết bị cấp 1 theo thiết bị cấp 0 được chọn"""
        try:
            parent_code = request.query_params.get('parent_code', '')
            if not parent_code:
                return Response([])

            # Lấy tất cả thiết bị có ma_day_du bắt đầu với parent_code
            all_thiet_bi = self.get_queryset().filter(
                ma_day_du__startswith=parent_code + '.'
            ).values('ma_day_du', 'ten', 'cap')

            # Extract mã cấp 1 từ ma_day_du
            # Ví dụ: parent_code="SH.TB.H1", ma_day_du="SH.TB.H1.GOV.TCC1.2F1" -> "SH.TB.H1.GOV"
            cap_1_info = {}  # {code: {'ten': ten, 'ma': ma}}

            for tb in all_thiet_bi:
                ma_day_du = tb['ma_day_du']
                if ma_day_du and ma_day_du.startswith(parent_code + '.'):
                    parts = ma_day_du.split('.')
                    if len(parts) >= 4:  # parent_code + 1 level
                        cap_1_code = '.'.join(parts[:4])  # SH.TB.H1.GOV

                        # Nếu ma_day_du trùng với mã cấp 1, lấy tên thật
                        if ma_day_du == cap_1_code:
                            cap_1_info[cap_1_code] = {
                                'ten': tb['ten'],
                                'ma': parts[3]  # GOV
                            }
                        # Nếu chưa có thiết bị cấp 1 này, tạo với tên mặc định
                        elif cap_1_code not in cap_1_info:
                            cap_1_info[cap_1_code] = {
                                'ten': f'Thiết bị {parts[3]}',
                                'ma': parts[3]
                            }

            # Tạo danh sách thiết bị cấp 1
            cap_1_devices = []
            for code in sorted(cap_1_info.keys()):
                info = cap_1_info[code]
                cap_1_devices.append({
                    'id': code,
                    'ma': info['ma'],
                    'ten': info['ten'],
                    'ma_day_du': code,
                    'cap': 1
                })

            return Response(cap_1_devices)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    @action(detail=False, methods=['get'])
    def cap_2_by_parent(self, request):
        """Lấy danh sách thiết bị cấp 2 theo thiết bị cấp 0 được chọn"""
        try:
            parent_code = request.query_params.get('parent_code', '')
            if not parent_code:
                return Response([])

            # Lấy tất cả thiết bị có ma_day_du bắt đầu với parent_code
            all_thiet_bi = self.get_queryset().filter(
                ma_day_du__startswith=parent_code + '.'
            ).values('ma_day_du', 'ten', 'cap')

            # Extract mã cấp 2 từ ma_day_du
            # Ví dụ: parent_code="SH.TB.H1", ma_day_du="SH.TB.H1.GOV.TCC1.2F1" -> "SH.TB.H1.GOV"
            cap_2_info = {}  # {code: {'ten': ten, 'ma': ma}}

            for tb in all_thiet_bi:
                ma_day_du = tb['ma_day_du']
                if ma_day_du and ma_day_du.startswith(parent_code + '.'):
                    parts = ma_day_du.split('.')
                    if len(parts) >= 5:  # parent_code + 2 level
                        cap_2_code = '.'.join(parts[:5])  # SH.TB.H1.GOV

                        # Nếu ma_day_du trùng với mã cấp 2, lấy tên thật
                        if ma_day_du == cap_2_code:
                            cap_2_info[cap_2_code] = {
                                'ten': tb['ten'],
                                'ma': parts[4]
                            }
                        # Nếu chưa có thiết bị cấp 2 này, tạo với tên mặc định
                        elif cap_2_code not in cap_2_info:
                            cap_2_info[cap_2_code] = {
                                'ten': f'Thiết bị {parts[4]}',
                                'ma': parts[4]
                            }

            # Tạo danh sách thiết bị cấp 2
            cap_2_devices = []
            for code in sorted(cap_2_info.keys()):
                info = cap_2_info[code]
                cap_2_devices.append({
                    'id': code,
                    'ma': info['ma'],
                    'ten': info['ten'],
                    'ma_day_du': code,
                    'cap': 2
                })

            return Response(cap_2_devices)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VatTuViewSet(viewsets.ModelViewSet):
    """ViewSet cho quản lý vật tư"""
    queryset = VatTu.objects.all()
    serializer_class = VatTuSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['nha_che_tao', 'nha_cung_cap', 'don_vi_tinh']
    search_fields = ['ma_vat_tu', 'ten_vat_tu', 'quy_cach']
    ordering_fields = ['ma_vat_tu', 'ten_vat_tu']
    ordering = ['ma_vat_tu']


class ThietBiVatTuViewSet(viewsets.ModelViewSet):
    """ViewSet cho quản lý vật tư gắn với thiết bị"""
    queryset = ThietBiVatTu.objects.all()
    serializer_class = ThietBiVatTuSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['thiet_bi', 'vat_tu']
    search_fields = ['thiet_bi__ten', 'vat_tu__ten_vat_tu', 'ghi_chu']
    ordering_fields = ['thiet_bi__ten', 'vat_tu__ten_vat_tu']
    ordering = ['thiet_bi__ten', 'vat_tu__ten_vat_tu']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('thiet_bi', 'vat_tu')
        return filter_queryset_by_factory(queryset, self.request.user, 'thiet_bi__nha_may', 'string')

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get('thiet_bi'))
        serializer.save()

    def perform_update(self, serializer):
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get('thiet_bi', serializer.instance.thiet_bi),
        )
        serializer.save()


class ThongSoVanHanhViewSet(viewsets.ModelViewSet):
    """ViewSet cho quản lý thông số vận hành"""
    queryset = ThongSoVanHanh.objects.select_related('thiet_bi').all()
    serializer_class = ThongSoVanHanhSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['thiet_bi', 'don_vi', 'nha_may', 'ky_hieu_van_hanh', 'ngay_nhap']
    search_fields = ['ten_thong_so', 'ma_thong_so', 'gia_tri', 'ghi_chu', 'thiet_bi__ten', 'thiet_bi__ma_day_du']
    ordering_fields = ['ten_thong_so', 'thiet_bi__ten', 'thoi_diem_nhap', 'ngay_nhap']
    ordering = ['-thoi_diem_nhap', 'thiet_bi__ten', 'ten_thong_so']

    def get_serializer_class(self):
        """Sử dụng serializer phù hợp cho từng action"""
        if self.action in ['create', 'bulk_create']:
            return ThongSoVanHanhCreateSerializer
        return ThongSoVanHanhSerializer

    def get_queryset(self):
        """Override get_queryset để hỗ trợ tìm kiếm theo thiết bị"""
        queryset = super().get_queryset()
        queryset = filter_queryset_by_factory(queryset, self.request.user, 'nha_may', 'string')

        # Filter theo thiết bị nếu có tham số thiet_bi_id
        thiet_bi_id = self.request.query_params.get('thiet_bi_id')
        if thiet_bi_id:
            queryset = queryset.filter(thiet_bi_id=thiet_bi_id)

        # Filter theo mã thiết bị nếu có tham số thiet_bi_ma
        thiet_bi_ma = self.request.query_params.get('thiet_bi_ma')
        if thiet_bi_ma:
            queryset = queryset.filter(thiet_bi__ma_day_du=thiet_bi_ma)

        return queryset

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get('thiet_bi'))
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, 'nha_may', 'string')
        )

    def perform_update(self, serializer):
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get('thiet_bi', serializer.instance.thiet_bi),
        )
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, 'nha_may', 'string')
        )

    @action(detail=False, methods=['get'])
    def by_thiet_bi(self, request):
        """Lấy thông số vận hành theo thiết bị (bao gồm thiết bị con)"""
        thiet_bi_id = request.query_params.get('thiet_bi_id')
        thiet_bi_ma = request.query_params.get('thiet_bi_ma')
        include_children = request.query_params.get('include_children', 'true').lower() == 'true'

        if thiet_bi_id:
            # Lấy thiết bị chính
            from .models import ThietBi
            try:
                thiet_bi = filter_queryset_by_factory(
                    ThietBi.objects.all(), request.user, 'nha_may', 'string'
                ).get(id=thiet_bi_id)
            except ThietBi.DoesNotExist:
                return Response(
                    {'error': 'Thiết bị không tồn tại'},
                    status=status.HTTP_404_NOT_FOUND
                )
        elif thiet_bi_ma:
            # Lấy thiết bị chính
            from .models import ThietBi
            try:
                thiet_bi = filter_queryset_by_factory(
                    ThietBi.objects.all(), request.user, 'nha_may', 'string'
                ).get(ma_day_du=thiet_bi_ma)
            except ThietBi.DoesNotExist:
                return Response(
                    {'error': 'Thiết bị không tồn tại'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            return Response(
                {'error': 'Cần cung cấp thiet_bi_id hoặc thiet_bi_ma'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if include_children:
            # Lấy tất cả thiết bị con (recursive)
            def get_all_children(thiet_bi):
                children = filter_queryset_by_factory(
                    ThietBi.objects.filter(cha=thiet_bi),
                    request.user,
                    'nha_may',
                    'string',
                )
                all_children = list(children)
                for child in children:
                    all_children.extend(get_all_children(child))
                return all_children

            # Lấy tất cả thiết bị (chính + con)
            all_thiet_bi = [thiet_bi] + get_all_children(thiet_bi)
            all_thiet_bi_ids = [tb.id for tb in all_thiet_bi]

            # Lấy thông số của tất cả thiết bị
            queryset = self.get_queryset().filter(thiet_bi_id__in=all_thiet_bi_ids)
        else:
            # Chỉ lấy thông số của thiết bị chính
            queryset = self.get_queryset().filter(thiet_bi=thiet_bi)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def thong_ke(self, request):
        """Lấy thống kê thông số vận hành"""
        try:
            # Tổng số thông số
            total_count = self.get_queryset().count()

            # Thống kê theo đơn vị
            don_vi_stats = self.get_queryset().values('don_vi').annotate(
                count=Count('id')
            ).order_by('-count')

            # Thống kê theo nhà máy
            nha_may_stats = self.get_queryset().values('nha_may').annotate(
                count=Count('id')
            ).order_by('-count')

            # Thống kê theo thiết bị
            thiet_bi_stats = self.get_queryset().values(
                'thiet_bi__ten', 'thiet_bi__ma_day_du'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:10]

            return Response({
                'total_count': total_count,
                'don_vi_stats': list(don_vi_stats),
                'nha_may_stats': list(nha_may_stats),
                'thiet_bi_stats': list(thiet_bi_stats)
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Tạo nhiều thông số vận hành cùng lúc (sử dụng get_or_create để tránh duplicate)"""
        try:
            data = request.data
            if not isinstance(data, list):
                return Response(
                    {'error': 'Dữ liệu phải là một mảng'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            created_objects = []
            updated_objects = []

            for item_data in data:
                if not has_all_factory_access(request.user):
                    item_data['nha_may'] = get_user_factory_name(request.user)
                # Chấp nhận cả thiet_bi và thiet_bi_id từ FE
                thiet_bi_id_val = item_data.get('thiet_bi') or item_data.get('thiet_bi_id')
                thiet_bi_obj = filter_queryset_by_factory(
                    ThietBi.objects.all(),
                    request.user,
                    'nha_may',
                    'string',
                ).filter(id=thiet_bi_id_val).first()
                if not thiet_bi_obj:
                    raise PermissionDenied("Bạn không có quyền nhập thông số cho thiết bị này.")

                # Sử dụng update_or_create với chỉ 3 fields trong constraint
                obj, created = ThongSoVanHanh.objects.update_or_create(
                    thiet_bi_id=thiet_bi_id_val,
                    ten_thong_so=item_data.get('ten_thong_so'),
                    thoi_diem_nhap=item_data.get('thoi_diem_nhap'),
                    defaults=item_data
                )

                if created:
                    created_objects.append(obj)
                else:
                    updated_objects.append(obj)

            return Response({
                'created': len(created_objects),
                'updated': len(updated_objects),
                'message': f'Đã tạo {len(created_objects)} bản ghi mới, cập nhật {len(updated_objects)} bản ghi'
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['put'])
    def bulk_update(self, request):
        """Cập nhật nhiều thông số vận hành cùng lúc"""
        try:
            data = request.data
            if not isinstance(data, list):
                return Response(
                    {'error': 'Dữ liệu phải là một mảng'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Lấy danh sách ID từ dữ liệu
            ids = [item.get('id') for item in data if item.get('id')]
            if not ids:
                return Response(
                    {'error': 'Cần cung cấp ID cho các bản ghi cần cập nhật'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Lấy các bản ghi hiện tại
            instances = {obj.id: obj for obj in self.get_queryset().filter(id__in=ids)}

            # Cập nhật từng bản ghi
            updated_data = []
            for item in data:
                obj_id = item.get('id')
                if obj_id in instances:
                    serializer = self.get_serializer(instances[obj_id], data=item, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        updated_data.append(serializer.data)
                    else:
                        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            return Response(updated_data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        """Xóa nhiều thông số vận hành cùng lúc"""
        try:
            ids = request.data.get('ids', [])
            if not ids:
                return Response(
                    {'error': 'Cần cung cấp danh sách ID cần xóa'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            deleted_count = self.get_queryset().filter(id__in=ids).delete()[0]
            return Response({
                'message': f'Đã xóa {deleted_count} thông số vận hành',
                'deleted_count': deleted_count
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnToanThietBiViewSet(viewsets.ModelViewSet):
    """ViewSet cho quản lý an toàn thiết bị"""
    queryset = AnToanThietBi.objects.all()
    serializer_class = AnToanThietBiSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['thiet_bi', 'bao_ho_lao_dong']
    search_fields = ['moi_nguy', 'bien_phap', 'bao_ho_lao_dong', 'ghi_chu']
    ordering_fields = ['thiet_bi__ten', 'moi_nguy']
    ordering = ['thiet_bi__ten', 'moi_nguy']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('thiet_bi')
        return filter_queryset_by_factory(queryset, self.request.user, 'thiet_bi__nha_may', 'string')

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get('thiet_bi'))
        serializer.save()

    def perform_update(self, serializer):
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get('thiet_bi', serializer.instance.thiet_bi),
        )
        serializer.save()


class DinhKemViewSet(viewsets.ModelViewSet):
    """ViewSet cho quản lý đính kèm"""
    queryset = DinhKem.objects.all()
    serializer_class = DinhKemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['thiet_bi', 'dinh_dang']
    search_fields = ['tieu_de', 'thiet_bi__ten']
    ordering_fields = ['tieu_de', 'ngay_tai_len']
    ordering = ['-ngay_tai_len']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('thiet_bi')
        return filter_queryset_by_factory(queryset, self.request.user, 'thiet_bi__nha_may', 'string')

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get('thiet_bi'))
        serializer.save()

    def perform_update(self, serializer):
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get('thiet_bi', serializer.instance.thiet_bi),
        )
        serializer.save()


class ThongSoToMayViewSet(viewsets.ModelViewSet):
    """ViewSet cho quản lý thông số tổ máy - Tối ưu cho legacy support"""
    queryset = ThongSoToMay.objects.select_related('thiet_bi').all()
    serializer_class = ThongSoToMaySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['thiet_bi', 'ten_thong_so', 'nha_may', 'ngay_nhap']
    search_fields = ['ten_thong_so', 'ma_thong_so', 'thiet_bi__ten', 'ghi_chu']
    ordering_fields = ['ten_thong_so', 'ngay_nhap', 'thoi_diem_nhap', 'created_at']
    ordering = ['-ngay_nhap', '-thoi_diem_nhap']

    def get_serializer_class(self):
        """Sử dụng serializer phù hợp cho từng action"""
        if self.action in ['create', 'bulk_upsert']:
            return ThongSoToMayCreateSerializer
        return ThongSoToMaySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return filter_queryset_by_factory(queryset, self.request.user, 'nha_may', 'string')

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get('thiet_bi'))
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, 'nha_may', 'string')
        )

    def perform_update(self, serializer):
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get('thiet_bi', serializer.instance.thiet_bi),
        )
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, 'nha_may', 'string')
        )

    @action(detail=False, methods=['post'])
    def bulk_upsert(self, request):
        """
        Tạo/cập nhật nhiều thông số tổ máy cùng lúc.
        Sử dụng update_or_create để tránh duplicate.
        """
        try:
            data_list = request.data
            if not isinstance(data_list, list):
                return Response(
                    {'error': 'Dữ liệu phải là một mảng'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            created_count = 0
            updated_count = 0

            for item_data in data_list:
                if not has_all_factory_access(request.user):
                    item_data['nha_may'] = get_user_factory_name(request.user)
                thiet_bi_obj = filter_queryset_by_factory(
                    ThietBi.objects.all(),
                    request.user,
                    'nha_may',
                    'string',
                ).filter(id=item_data.get('thiet_bi')).first()
                if not thiet_bi_obj:
                    raise PermissionDenied("Bạn không có quyền nhập thông số cho thiết bị này.")
                # Validate data
                serializer = ThongSoToMayCreateSerializer(data=item_data)
                serializer.is_valid(raise_exception=True)
                validated_data = serializer.validated_data

                # Sử dụng update_or_create với unique constraint
                obj, created = ThongSoToMay.objects.update_or_create(
                    thiet_bi=validated_data['thiet_bi'],
                    ten_thong_so=validated_data['ten_thong_so'],
                    thoi_diem_nhap=validated_data['thoi_diem_nhap'],
                    ngay_nhap=validated_data['ngay_nhap'],
                    defaults=validated_data
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            return Response({
                'created': created_count,
                'updated': updated_count,
                'message': f'Đã tạo {created_count} bản ghi mới, cập nhật {updated_count} bản ghi'
            }, status=status.HTTP_201_CREATED if created_count > 0 else status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Lỗi khi xử lý dữ liệu: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
