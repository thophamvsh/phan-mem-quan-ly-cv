from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from khovattu.models import Bang_nha_may
from core.factory_scope import (
    apply_request_factory_to_serializer,
    ensure_factory_code_allowed,
    filter_queryset_by_factory,
    get_user_factory_name,
    get_user_factory_code,
    has_all_factory_access,
    has_profile_permission,
)
from quanlyvanhanh.models import ThietBi, ThongSoVanHanh
from quanlyvanhanh.serializers import (
    ThongSoVanHanhCreateSerializer,
    ThongSoVanHanhSerializer,
)
from quanlyvanhanh.services.thongso_dien_service import (
    bulk_create_thong_so_van_hanh,
    get_scoped_thiet_bi,
)

# Cấu hình layout cột động của thông số vận hành điện theo nhà máy
DIEN_CONFIGS = {
    'SH': {
        'title': 'BẢNG NHẬP THÔNG SỐ VẬN HÀNH ĐIỆN SÔNG HÌNH',
        'layout': [
            {
                'group': 'TỔ MÁY H1',
                'device_code': 'SH.TB.H1',
                'columns': [
                    {'ten': 'Điện áp kích từ', 'ma': 'dien_ap_kich_tu_h1', 'don_vi': 'V'},
                    {'ten': 'Dòng điện kích từ', 'ma': 'dong_dien_kich_tu_h1', 'don_vi': 'A'},
                    {'ten': 'Điện áp', 'ma': 'dien_ap_h1', 'don_vi': 'kV'},
                    {'ten': 'Dòng điện', 'ma': 'dong_dien_h1', 'don_vi': 'A'},
                    {'ten': 'Công suất tác dụng', 'ma': 'cong_suat_tac_dung_h1', 'don_vi': 'MW'},
                    {'ten': 'Công suất phản kháng', 'ma': 'cong_suat_phan_khang_h1', 'don_vi': 'MVar'},
                    {'ten': 'Tần số', 'ma': 'tan_so_h1', 'don_vi': 'Hz'},
                ]
            },
            {
                'group': 'TỔ MÁY H2',
                'device_code': 'SH.TB.H2',
                'columns': [
                    {'ten': 'Điện áp kích từ', 'ma': 'dien_ap_kich_tu_h2', 'don_vi': 'V'},
                    {'ten': 'Dòng điện kích từ', 'ma': 'dong_dien_kich_tu_h2', 'don_vi': 'A'},
                    {'ten': 'Điện áp', 'ma': 'dien_ap_h2', 'don_vi': 'kV'},
                    {'ten': 'Dòng điện', 'ma': 'dong_dien_h2', 'don_vi': 'A'},
                    {'ten': 'Công suất tác dụng', 'ma': 'cong_suat_tac_dung_h2', 'don_vi': 'MW'},
                    {'ten': 'Công suất phản kháng', 'ma': 'cong_suat_phan_khang_h2', 'don_vi': 'MVar'},
                    {'ten': 'Tần số', 'ma': 'tan_so_h2', 'don_vi': 'Hz'},
                ]
            },
            {
                'group': 'TRẠM PHÂN PHỐI',
                'device_code': 'SH.TB.TPP',
                'columns': [
                    {'ten': 'Tổng P máy phát', 'ma': 'tong_p_may_phat', 'don_vi': 'MW'},
                    {'ten': 'Tổng Q máy phát', 'ma': 'tong_q_may_phat', 'don_vi': 'MVar'},
                    {'ten': 'Điện áp ĐZ 172', 'ma': 'dien_ap_172', 'don_vi': 'kV', 'sub_device': '110.172'},
                    {'ten': 'Dòng điện ĐZ 172', 'ma': 'dong_dien_172', 'don_vi': 'A', 'sub_device': '110.172'},
                    {'ten': 'Công suất tác dụng ĐZ 172', 'ma': 'cong_suat_tac_dung_172', 'don_vi': 'MW', 'sub_device': '110.172'},
                    {'ten': 'Công suất phản kháng ĐZ 172', 'ma': 'cong_suat_phan_khang_172', 'don_vi': 'MVar', 'sub_device': '110.172'},
                    {'ten': 'Điện áp ĐZ 174', 'ma': 'dien_ap_174', 'don_vi': 'kV', 'sub_device': '110.174'},
                    {'ten': 'Dòng điện ĐZ 174', 'ma': 'dong_dien_174', 'don_vi': 'A', 'sub_device': '110.174'},
                    {'ten': 'Công suất tác dụng ĐZ 174', 'ma': 'cong_suat_tac_dung_174', 'don_vi': 'MW', 'sub_device': '110.174'},
                    {'ten': 'Công suất phản kháng ĐZ 174', 'ma': 'cong_suat_phan_khang_174', 'don_vi': 'MVar', 'sub_device': '110.174'},
                    {'ten': 'Điện áp ĐZ 471', 'ma': 'dien_ap_471', 'don_vi': 'kV', 'sub_device': '22.471'},
                    {'ten': 'Dòng điện ĐZ 471', 'ma': 'dong_dien_471', 'don_vi': 'A', 'sub_device': '22.471'},
                    {'ten': 'Công suất tác dụng ĐZ 471', 'ma': 'cong_suat_tac_dung_471', 'don_vi': 'MW', 'sub_device': '22.471'},
                    {'ten': 'Công suất phản kháng ĐZ 471', 'ma': 'cong_suat_phan_khang_471', 'don_vi': 'MVar', 'sub_device': '22.471'},
                    {'ten': 'Điện áp ĐZ 472', 'ma': 'dien_ap_472', 'don_vi': 'kV', 'sub_device': '22.472'},
                    {'ten': 'Dòng điện ĐZ 472', 'ma': 'dong_dien_472', 'don_vi': 'A', 'sub_device': '22.472'},
                    {'ten': 'Công suất tác dụng ĐZ 472', 'ma': 'cong_suat_tac_dung_472', 'don_vi': 'MW', 'sub_device': '22.472'},
                    {'ten': 'Công suất phản kháng ĐZ 472', 'ma': 'cong_suat_phan_khang_472', 'don_vi': 'MVar', 'sub_device': '22.472'},
                    {'ten': 'Tổng P 22kV', 'ma': 'tong_p_22kv', 'don_vi': 'MW'},
                ]
            }
        ]
    },
    'VS': {
        'title': 'BẢNG NHẬP THÔNG SỐ VẬN HÀNH ĐIỆN VĨNH SƠN',
        'layout': [
            {
                'group': 'MÁY PHÁT H1',
                'device_code': 'VS.TB.H1',
                'columns': [
                    {'ten': 'Ukt', 'ma': 'dien_ap_kich_tu_h1', 'don_vi': 'V'},
                    {'ten': 'Ikt', 'ma': 'dong_dien_kich_tu_h1', 'don_vi': 'A'},
                    {'ten': 'U', 'ma': 'dien_ap_h1', 'don_vi': 'kV'},
                    {'ten': 'P', 'ma': 'cong_suat_tac_dung_h1', 'don_vi': 'MW'},
                    {'ten': 'Q', 'ma': 'cong_suat_phan_khang_h1', 'don_vi': 'MVar'},
                    {'ten': 'f', 'ma': 'tan_so_h1', 'don_vi': 'Hz'},
                ]
            },
            {
                'group': 'MÁY PHÁT H2',
                'device_code': 'VS.TB.H2',
                'columns': [
                    {'ten': 'Ukt', 'ma': 'dien_ap_kich_tu_h2', 'don_vi': 'V'},
                    {'ten': 'Ikt', 'ma': 'dong_dien_kich_tu_h2', 'don_vi': 'A'},
                    {'ten': 'U', 'ma': 'dien_ap_h2', 'don_vi': 'kV'},
                    {'ten': 'P', 'ma': 'cong_suat_tac_dung_h2', 'don_vi': 'MW'},
                    {'ten': 'Q', 'ma': 'cong_suat_phan_khang_h2', 'don_vi': 'MVar'},
                    {'ten': 'f', 'ma': 'tan_so_h2', 'don_vi': 'Hz'},
                ]
            },
            {
                'group': 'TRẠM PHÂN PHỐI 110 kV',
                'device_code': 'VS.TB.TPP',
                'columns': [
                    {'ten': 'I1', 'ma': 'dong_dien_thanh_cai', 'don_vi': 'A'},
                    {'ten': 'I171', 'ma': 'dong_dien_171', 'don_vi': 'A', 'sub_device': '171'},
                    {'ten': 'P171', 'ma': 'cong_suat_tac_dung_171', 'don_vi': 'MW', 'sub_device': '171'},
                    {'ten': 'Q171', 'ma': 'cong_suat_phan_khang_171', 'don_vi': 'MVar', 'sub_device': '171'},
                    {'ten': 'U171', 'ma': 'dien_ap_171', 'don_vi': 'kV', 'sub_device': '171'},
                    {'ten': 'I2', 'ma': 'dong_dien_172', 'don_vi': 'A', 'sub_device': '172'},
                    {'ten': 'P172', 'ma': 'cong_suat_tac_dung_172', 'don_vi': 'MW', 'sub_device': '172'},
                    {'ten': 'Q172', 'ma': 'cong_suat_phan_khang_172', 'don_vi': 'MVar', 'sub_device': '172'},
                    {'ten': 'U172', 'ma': 'dien_ap_172', 'don_vi': 'kV', 'sub_device': '172'},
                ]
            },
            {
                'group': 'MBA T1, T2',
                'device_code': 'VS.TB.TPP',
                'columns': [
                    {'ten': 'Nđ\nø T1', 'ma': 'nhiet_do_cuon_day_t1', 'don_vi': '°C', 'sub_device': 'T1'},
                    {'ten': 'NPA\nT1', 'ma': 'nac_phan_ap_t1', 'don_vi': '', 'sub_device': 'T1'},
                    {'ten': 'Nđ\nø T2', 'ma': 'nhiet_do_cuon_day_t2', 'don_vi': '°C', 'sub_device': 'T2'},
                    {'ten': 'NPA\nT2', 'ma': 'nac_phan_ap_t2', 'don_vi': '', 'sub_device': 'T2'},
                ]
            },
            {
                'group': 'Áp suất khí máy cắt 110kV',
                'device_code': 'VS.TB.TPP',
                'columns': [
                    {'ten': '131', 'ma': 'ap_suat_khi_131', 'don_vi': 'MPa', 'sub_device': '131'},
                    {'ten': '132', 'ma': 'ap_suat_khi_132', 'don_vi': 'MPa', 'sub_device': '132'},
                    {'ten': '171', 'ma': 'ap_suat_khi_171', 'don_vi': 'MPa', 'sub_device': '171'},
                    {'ten': '172', 'ma': 'ap_suat_khi_172', 'don_vi': 'MPa', 'sub_device': '172'},
                    {'ten': '112', 'ma': 'ap_suat_khi_112', 'don_vi': 'MPa', 'sub_device': '112'},
                ]
            },
            {
                'group': 'MBA tự dùng TD91',
                'device_code': 'VS.TB.TD.LV.TD1',
                'columns': [
                    {'ten': 'U', 'ma': 'dien_ap_td91', 'don_vi': 'V'},
                    {'ten': 'I', 'ma': 'dong_dien_td91', 'don_vi': 'A'},
                    {'ten': 'P', 'ma': 'cong_suat_td91', 'don_vi': 'kW'},
                ]
            },
            {
                'group': 'MBA tự dùng TD92',
                'device_code': 'VS.TB.TD.LV.TD2',
                'columns': [
                    {'ten': 'U', 'ma': 'dien_ap_td92', 'don_vi': 'V'},
                    {'ten': 'I', 'ma': 'dong_dien_td92', 'don_vi': 'A'},
                    {'ten': 'P', 'ma': 'cong_suat_td92', 'don_vi': 'kW'},
                ]
            }
        ]
    }
}


def get_factory_config(factory_code):
    """Lấy cấu hình động thông số vận hành điện theo nhà máy"""
    if not factory_code:
        factory_code = 'SH'
    config = DIEN_CONFIGS.get(factory_code, DIEN_CONFIGS['SH'])
    if factory_code != 'SH':
        # Clone và customize factory prefix sang nhà máy tương ứng
        cloned_layout = []
        for grp in config['layout']:
            new_grp = dict(grp)
            new_grp['device_code'] = grp['device_code'].replace('VS.TB', f'{factory_code}.TB')
            cloned_layout.append(new_grp)
        return {
            'title': config['title'],
            'layout': cloned_layout
        }
    return config


def _ensure_thiet_bi_access(user, thiet_bi):
    if not thiet_bi or has_all_factory_access(user):
        return

    allowed = filter_queryset_by_factory(
        ThietBi.objects.filter(pk=thiet_bi.pk),
        user,
        "nha_may",
        "string",
    ).exists()
    if not allowed:
        raise PermissionDenied(
            "Ban khong co quyen thao tac voi thiet bi cua nha may nay."
        )


class ThongSoVanHanhViewSet(viewsets.ModelViewSet):
    """ViewSet quan ly thong so van hanh dien."""

    queryset = ThongSoVanHanh.objects.select_related("thiet_bi").all()
    serializer_class = ThongSoVanHanhSerializer

    def check_permissions(self, request):
        super().check_permissions(request)
        
        # Check custom profile permissions based on action
        if self.action in ["list", "retrieve", "by_device", "config"]:
            if not has_profile_permission(request.user, "can_view_operation_parameters"):
                self.permission_denied(
                    request,
                    message="Tài khoản của bạn chưa được cấp quyền xem thông số vận hành. Vui lòng liên hệ quản trị viên."
                )
        elif self.action in ["create", "update", "partial_update", "bulk_create", "bulk_upsert"]:
            if not has_profile_permission(request.user, "can_edit_operation_parameters"):
                self.permission_denied(
                    request,
                    message="Tài khoản của bạn chưa được cấp quyền thêm/sửa thông số vận hành. Vui lòng liên hệ quản trị viên."
                )
        elif self.action in ["destroy", "delete_by_day"]:
            if not has_profile_permission(request.user, "can_delete_operation_parameters"):
                self.permission_denied(
                    request,
                    message="Tài khoản của bạn chưa được cấp quyền xóa dữ liệu thông số vận hành. Vui lòng liên hệ quản trị viên."
                )
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["thiet_bi", "don_vi", "nha_may", "ky_hieu_van_hanh", "ngay_nhap"]
    search_fields = [
        "ten_thong_so",
        "ma_thong_so",
        "gia_tri",
        "ghi_chu",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
    ]
    ordering_fields = ["ten_thong_so", "thiet_bi__ten", "thoi_diem_nhap", "ngay_nhap"]
    ordering = ["-thoi_diem_nhap", "thiet_bi__ten", "ten_thong_so"]

    def get_serializer_class(self):
        if self.action in ["create", "bulk_create"]:
            return ThongSoVanHanhCreateSerializer
        return ThongSoVanHanhSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = filter_queryset_by_factory(
            queryset,
            self.request.user,
            "nha_may",
            "string",
        )

        thiet_bi_id = self.request.query_params.get("thiet_bi_id")
        if thiet_bi_id:
            queryset = queryset.filter(thiet_bi_id=thiet_bi_id)

        thiet_bi_ma = self.request.query_params.get("thiet_bi_ma")
        if thiet_bi_ma:
            queryset = queryset.filter(thiet_bi__ma_day_du=thiet_bi_ma)

        return queryset

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get("thiet_bi"))
        serializer.save(
            **apply_request_factory_to_serializer(
                self.request.user,
                serializer,
                "nha_may",
                "string",
            )
        )

    def perform_update(self, serializer):
        _ensure_thiet_bi_access(
            self.request.user,
            serializer.validated_data.get("thiet_bi", serializer.instance.thiet_bi),
        )
        serializer.save(
            **apply_request_factory_to_serializer(
                self.request.user,
                serializer,
                "nha_may",
                "string",
            )
        )

    @action(detail=False, methods=["get"])
    def by_thiet_bi(self, request):
        thiet_bi_id = request.query_params.get("thiet_bi_id")
        thiet_bi_ma = request.query_params.get("thiet_bi_ma")
        include_children = (
            request.query_params.get("include_children", "true").lower() == "true"
        )

        thiet_bi = get_scoped_thiet_bi(request.user, thiet_bi_id, thiet_bi_ma)
        if not thiet_bi:
            return Response(
                {"error": "Thiet bi khong ton tai"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if include_children:
            if thiet_bi.ma_day_du:
                child_devices = filter_queryset_by_factory(
                    ThietBi.objects.filter(
                        ma_day_du__startswith=f"{thiet_bi.ma_day_du}."
                    ),
                    request.user,
                    "nha_may",
                    "string",
                )
                device_ids = [thiet_bi.id, *child_devices.values_list("id", flat=True)]
            else:
                device_ids = [thiet_bi.id]
            queryset = self.get_queryset().filter(thiet_bi_id__in=device_ids)
        else:
            queryset = self.get_queryset().filter(thiet_bi=thiet_bi)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def thong_ke(self, request):
        try:
            queryset = self.get_queryset()
            don_vi_stats = queryset.values("don_vi").annotate(
                count=Count("id")
            ).order_by("-count")
            nha_may_stats = queryset.values("nha_may").annotate(
                count=Count("id")
            ).order_by("-count")
            thiet_bi_stats = queryset.values(
                "thiet_bi__ten",
                "thiet_bi__ma_day_du",
            ).annotate(count=Count("id")).order_by("-count")[:10]

            return Response(
                {
                    "total_count": queryset.count(),
                    "don_vi_stats": list(don_vi_stats),
                    "nha_may_stats": list(nha_may_stats),
                    "thiet_bi_stats": list(thiet_bi_stats),
                }
            )
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response(
                {"error": "Du lieu phai la mot mang"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = bulk_create_thong_so_van_hanh(request.user, data)
        except PermissionDenied:
            raise
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                **result,
                "message": (
                    f"Da tao {result['created']} ban ghi moi, "
                    f"cap nhat {result['updated']} ban ghi, "
                    f"xoa {result.get('deleted', 0)} ban ghi"
                ),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["put"])
    def bulk_update(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response(
                {"error": "Du lieu phai la mot mang"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = [item.get("id") for item in data if item.get("id")]
        if not ids:
            return Response(
                {"error": "Can cung cap ID cho cac ban ghi can cap nhat"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instances = {obj.id: obj for obj in self.get_queryset().filter(id__in=ids)}
        updated_data = []

        try:
            for item in data:
                obj_id = item.get("id")
                if obj_id not in instances:
                    continue

                thiet_bi_id = item.get("thiet_bi") or item.get("thiet_bi_id")
                if thiet_bi_id:
                    thiet_bi_obj = get_scoped_thiet_bi(request.user, thiet_bi_id)
                    if not thiet_bi_obj:
                        raise PermissionDenied(
                            "Ban khong co quyen cap nhat thong so cho thiet bi nay."
                        )
                    item["thiet_bi"] = thiet_bi_obj.id

                if not has_all_factory_access(request.user):
                    item["nha_may"] = get_user_factory_name(request.user)

                serializer = self.get_serializer(
                    instances[obj_id],
                    data=item,
                    partial=True,
                )
                if not serializer.is_valid():
                    return Response(
                        serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                serializer.save(
                    **apply_request_factory_to_serializer(
                        request.user,
                        serializer,
                        "nha_may",
                        "string",
                    )
                )
                updated_data.append(serializer.data)

            return Response(updated_data)
        except PermissionDenied:
            raise
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["delete"])
    def bulk_delete(self, request):
        ids = request.data.get("ids", [])
        if not ids:
            return Response(
                {"error": "Can cung cap danh sach ID can xoa"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deleted_count = self.get_queryset().filter(id__in=ids).delete()[0]
        return Response(
            {
                "message": f"Da xoa {deleted_count} thong so van hanh",
                "deleted_count": deleted_count,
            }
        )

    @action(detail=False, methods=["delete"])
    def delete_by_day(self, request):
        thiet_bi_ma = request.query_params.get("thiet_bi_ma")
        thiet_bi_id = request.query_params.get("thiet_bi_id")
        ngay_str = request.query_params.get("ngay")

        if not ngay_str:
            return Response(
                {"error": "Can cung cap tham so ngay (ngay)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(ngay_nhap=ngay_str)
        if thiet_bi_id:
            queryset = queryset.filter(thiet_bi_id=thiet_bi_id)
        elif thiet_bi_ma:
            queryset = queryset.filter(thiet_bi__ma_day_du=thiet_bi_ma)

        deleted_count = queryset.delete()[0]
        return Response(
            {
                "message": f"Da xoa {deleted_count} thong so van hanh",
                "deleted_count": deleted_count,
            }
        )

    @action(detail=False, methods=["get"])
    def config(self, request):
        """API trả về cấu hình cột động theo nhà máy của tài khoản đang đăng nhập"""
        requested_factory_code = request.query_params.get("factory_code")
        factory_code = (
            requested_factory_code or get_user_factory_code(request.user) or 'SH'
        ).upper()
        if factory_code not in DIEN_CONFIGS:
            return Response(
                {"error": "Nha may khong co cau hinh thong so van hanh dien."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ensure_factory_code_allowed(request.user, factory_code)
        config = get_factory_config(factory_code)
        factory = Bang_nha_may.objects.filter(ma_nha_may__iexact=factory_code).first()
        return Response({
            **config,
            "factory_code": factory_code,
            "nha_may": factory.ten_nha_may if factory else factory_code,
        })
