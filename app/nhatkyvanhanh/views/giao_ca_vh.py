from django.utils import timezone
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from nhatkyvanhanh.models import SogiaonhancaVH, ChiTietSoGiaoNhanCaVH, LuuYChiDaoSoGiaoNhanCaVH
from nhatkyvanhanh.serializers import (
    SogiaonhancaVHSerializer,
    ChiTietSoGiaoNhanCaVHSerializer,
    LuuYChiDaoSoGiaoNhanCaVHSerializer,
)
from nhatkyvanhanh.permissions import (
    CanViewShiftHandoverLogs,
    CanCreateShiftHandoverLogs,
    CanReceiveShiftHandoverLogs,
    CanEditShiftHandoverLogs,
    CanDeleteShiftHandoverLogs,
    IsShiftLogCreator,
    IsNotShiftLogCreator,
)
from .helpers import (
    _sync_truc_ktvh_from_admin_shift_log,
    _dong_bo_chu_ky_so_giao_nhan,
    _shift_log_locked,
    _can_edit_shift_log,
    _can_delete_shift_log,
    _is_creator_of_shift_log,
    _can_create_shift_detail,
    _can_update_shift_detail,
    _can_create_shift_directive,
    _can_view_shift_directives,
    _can_update_shift_directive,
)


class SogiaonhancaVHFilterSet(django_filters.FilterSet):
    ngay_truc_tu = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="gte")
    ngay_truc_den = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="lte")

    class Meta:
        model = SogiaonhancaVH
        fields = [
            "nha_may",
            "ca_truc",
            "trang_thai",
            "ngay_truc",
            "ngay_truc_tu",
            "ngay_truc_den",
            "user_giao_ca",
            "user_nhan_ca",
        ]


class SogiaonhancaVHViewSet(viewsets.ModelViewSet):
    serializer_class = SogiaonhancaVHSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SogiaonhancaVHFilterSet
    search_fields = [
        "dia_diem",
        "truc_chinh",
        "truc_phu",
        "truc_ktvh",
        "noi_dung_chi_tiets__tieu_de",
        "noi_dung_chi_tiets__noi_dung",
        "luu_y",
        "user_giao_ca__email",
        "user_giao_ca__username",
        "user_nhan_ca__email",
        "user_nhan_ca__username",
    ]
    ordering_fields = [
        "ngay_truc",
        "thoi_gian_bat_dau_ca",
        "thoi_gian_giao_ca",
        "created_at",
        "updated_at",
    ]
    ordering = ["-ngay_truc", "-thoi_gian_bat_dau_ca", "-thoi_gian_giao_ca", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewShiftHandoverLogs]
        if self.action == "create":
            permission_classes = [CanCreateShiftHandoverLogs]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [CanEditShiftHandoverLogs]
        elif self.action == "destroy":
            permission_classes = [CanDeleteShiftHandoverLogs]
        elif self.action == "ky_nhan_ca":
            permission_classes = [CanReceiveShiftHandoverLogs, IsNotShiftLogCreator]
        elif self.action == "ky_giao_ca":
            permission_classes = [CanViewShiftHandoverLogs, IsShiftLogCreator]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SogiaonhancaVH.objects.select_related(
            "nha_may",
            "user_giao_ca",
            "user_nhan_ca",
            "nguoi_tao",
        ).prefetch_related(
            "noi_dung_chi_tiets__nguoi_tao",
            "luu_y_chi_daos__nguoi_tao",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        so = serializer.save(
            user_giao_ca=self.request.user,
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        _sync_truc_ktvh_from_admin_shift_log(so)
        _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
        so.save()

    def perform_update(self, serializer):
        if _shift_log_locked(serializer.instance):
            raise PermissionDenied("So giao nhan ca da co du 2 chu ky, khong duoc chinh sua.")
        if not _can_edit_shift_log(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so giao nhan ca.")
        so = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        _sync_truc_ktvh_from_admin_shift_log(so)
        _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
        so.save()

    def perform_destroy(self, instance):
        if _shift_log_locked(instance):
            raise PermissionDenied("So giao nhan ca da co du 2 chu ky, khong duoc xoa.")
        if not _can_delete_shift_log(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so giao nhan ca.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def ky_giao_ca(self, request, pk=None):
        so = self.get_object()
        if not so.nhan_ca_ky_at:
            return Response(
                {"detail": "Can ky nhan ca truoc khi ky giao ca."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not so.giao_ca_ky_at:
            so.giao_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="noi-dung-chi-tiet")
    def tao_noi_dung_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if _shift_log_locked(so):
            return Response(
                {"detail": "So giao nhan ca da co du 2 chu ky, khong duoc them noi dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_create_shift_detail(request.user, so):
            return Response(
                {"detail": "Chi user giao ca moi duoc them noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ChiTietSoGiaoNhanCaVHSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"noi-dung-chi-tiet/(?P<chi_tiet_id>[^/.]+)",
    )
    def cap_nhat_noi_dung_chi_tiet(self, request, pk=None, chi_tiet_id=None):
        so = self.get_object()
        if _shift_log_locked(so):
            return Response(
                {"detail": "So giao nhan ca da co du 2 chu ky, khong duoc cap nhat noi dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            chi_tiet = so.noi_dung_chi_tiets.get(pk=chi_tiet_id)
        except ChiTietSoGiaoNhanCaVH.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay noi dung chi tiet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _can_update_shift_detail(request.user, so, chi_tiet):
            return Response(
                {"detail": "Chi user giao ca tao noi dung moi duoc cap nhat noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            chi_tiet.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = ChiTietSoGiaoNhanCaVHSerializer(
            chi_tiet,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="luu-y-chi-dao")
    def tao_luu_y_chi_dao(self, request, pk=None):
        so = self.get_object()
        if not _can_create_shift_directive(request.user, so):
            return Response(
                {"detail": "User khong co quyen tao luu y chi dao."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = LuuYChiDaoSoGiaoNhanCaVHSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"luu-y-chi-dao/(?P<directive_id>[^/.]+)",
    )
    def cap_nhat_luu_y_chi_dao(self, request, pk=None, directive_id=None):
        so = self.get_object()
        if not _can_view_shift_directives(request.user):
            return Response(
                {"detail": "User khong co quyen xem luu y chi dao."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            directive = so.luu_y_chi_daos.get(pk=directive_id)
        except LuuYChiDaoSoGiaoNhanCaVH.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay luu y chi dao."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _can_update_shift_directive(request.user, directive):
            return Response(
                {"detail": "Chi user tao luu y chi dao moi duoc cap nhat hoac xoa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            directive.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = LuuYChiDaoSoGiaoNhanCaVHSerializer(
            directive,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ky_nhan_ca(self, request, pk=None):
        so = self.get_object()
        if so.user_nhan_ca_id and so.user_nhan_ca_id != request.user.id:
            return Response(
                {"detail": "So da duoc gan user nhan ca khac."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not so.nhan_ca_ky_at:
            if not so.user_nhan_ca_id:
                so.user_nhan_ca = request.user
            so.nhan_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)
