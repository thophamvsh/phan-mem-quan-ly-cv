import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied
from django.db import transaction

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from nhatkyvanhanh.models import MauChuyenDoiThietBi, SoChuyenDoiThietBiTuan, LanChuyenDoiThietBi, ChiTietChuyenDoiThietBi
from nhatkyvanhanh.serializers import (
    MauChuyenDoiThietBiSerializer,
    SoChuyenDoiThietBiTuanSerializer,
    LanChuyenDoiThietBiSerializer,
)
from nhatkyvanhanh.permissions import (
    CanViewOperationLogbooks,
    CanCreateOperationLogbooks,
    CanViewWeeklyEquipmentSwitchLogs,
    CanCreateWeeklyEquipmentSwitchLogs,
    CanEditWeeklyEquipmentSwitchLogs,
    CanDeleteWeeklyEquipmentSwitchLogs,
)
from .helpers import (
    _can_edit_weekly_equipment_switch_log,
    _can_delete_weekly_equipment_switch_log,
    _get_song_hinh_factory,
    _create_default_switch_templates,
    _can_delete_weekly_equipment_switch_entry,
    _can_edit_weekly_equipment_switch_entry,
)


class MauChuyenDoiThietBiFilterSet(django_filters.FilterSet):
    class Meta:
        model = MauChuyenDoiThietBi
        fields = ["nha_may", "to_may", "dang_su_dung", "thiet_bi"]


class MauChuyenDoiThietBiViewSet(viewsets.ModelViewSet):
    serializer_class = MauChuyenDoiThietBiSerializer
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MauChuyenDoiThietBiFilterSet
    search_fields = [
        "nhom_thiet_bi",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
        "nha_may__ma_nha_may",
        "nha_may__ten_nha_may",
    ]
    ordering_fields = ["to_may", "thu_tu", "created_at", "updated_at"]
    ordering = ["to_may", "thu_tu", "created_at"]

    def get_permissions(self):
        permission_classes = [CanViewOperationLogbooks]
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [CanCreateOperationLogbooks]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = MauChuyenDoiThietBi.objects.select_related(
            "nha_may",
            "thiet_bi",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_update(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )


class SoChuyenDoiThietBiTuanFilterSet(django_filters.FilterSet):
    tuan_tu = django_filters.NumberFilter(field_name="tuan", lookup_expr="gte")
    tuan_den = django_filters.NumberFilter(field_name="tuan", lookup_expr="lte")
    ngay_tu = django_filters.DateFilter(field_name="tuan_ket_thuc", lookup_expr="gte")
    ngay_den = django_filters.DateFilter(field_name="tuan_bat_dau", lookup_expr="lte")

    class Meta:
        model = SoChuyenDoiThietBiTuan
        fields = ["nha_may", "nam", "tuan", "ca_truc", "tuan_tu", "tuan_den", "ngay_tu", "ngay_den", "nguoi_tao"]


class SoChuyenDoiThietBiTuanViewSet(viewsets.ModelViewSet):
    serializer_class = SoChuyenDoiThietBiTuanSerializer
    parser_classes = [JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SoChuyenDoiThietBiTuanFilterSet
    search_fields = [
        "nguoi_tao__email",
        "nguoi_tao__username",
        "ca_truc",
        "lan_chuyen_dois__ghi_chu_chung",
        "lan_chuyen_dois__chi_tiets__ghi_chu",
        "lan_chuyen_dois__chi_tiets__thiet_bi__ten",
        "lan_chuyen_dois__chi_tiets__thiet_bi__ma_day_du",
    ]
    ordering_fields = ["nam", "tuan", "tuan_bat_dau", "created_at", "updated_at"]
    ordering = ["-nam", "-tuan", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewWeeklyEquipmentSwitchLogs]
        if self.action == "create":
            permission_classes = [CanCreateWeeklyEquipmentSwitchLogs]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [CanEditWeeklyEquipmentSwitchLogs]
        elif self.action == "destroy":
            permission_classes = [CanDeleteWeeklyEquipmentSwitchLogs]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = (
            SoChuyenDoiThietBiTuan.objects.select_related(
                "nha_may",
                "nguoi_tao",
            )
            .prefetch_related(
                "lan_chuyen_dois",
                "lan_chuyen_dois__nguoi_thuc_hien",
                "lan_chuyen_dois__chi_tiets",
                "lan_chuyen_dois__chi_tiets__thiet_bi",
            )
            .all()
            .distinct()
        )
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        factory_data = apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        if not factory_data.get("nha_may") and not serializer.validated_data.get("nha_may"):
            factory_data["nha_may"] = _get_song_hinh_factory()
        serializer.save(
            nguoi_tao=self.request.user,
            **factory_data
        )

    def perform_update(self, serializer):
        if not _can_edit_weekly_equipment_switch_log(self.request.user, serializer.instance):
            raise PermissionDenied("Ban khong co quyen cap nhat so chuyen doi thiet bi tuan nay.")
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )

    def perform_destroy(self, instance):
        if not _can_delete_weekly_equipment_switch_log(self.request.user, instance):
            raise PermissionDenied("Ban khong co quyen xoa so chuyen doi thiet bi tuan nay.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"], url_path="tao-lan-chuyen-doi")
    def tao_lan_chuyen_doi(self, request, pk=None):
        so = self.get_object()
        target_nha_may = so.nha_may or _get_song_hinh_factory()
        if not _can_edit_weekly_equipment_switch_log(request.user, so):
            return Response(
                {"detail": "Ban khong co quyen them lan chuyen doi thiet bi."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if so.lan_chuyen_dois.exists():
            return Response(
                {"detail": "Moi so tuan chi duoc tao mot lan chuyen doi thiet bi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LanChuyenDoiThietBiSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        templates = list(
            MauChuyenDoiThietBi.objects.select_related("thiet_bi")
            .filter(dang_su_dung=True)
            .filter(nha_may=target_nha_may)
            .order_by("to_may", "thu_tu", "created_at")
        )
        if not templates:
            _create_default_switch_templates(target_nha_may)
            templates = list(
                MauChuyenDoiThietBi.objects.select_related("thiet_bi")
                .filter(dang_su_dung=True)
                .filter(nha_may=target_nha_may)
                .order_by("to_may", "thu_tu", "created_at")
            )
        if not templates:
            return Response(
                {"detail": "Chua co mau chuyen doi thiet bi cho nha may nay va khong tim thay thiet bi phu hop de tao mau mac dinh."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            lan = serializer.save(so=so, nguoi_thuc_hien=request.user)
            ChiTietChuyenDoiThietBi.objects.bulk_create(
                [
                    ChiTietChuyenDoiThietBi(
                        lan_chuyen_doi=lan,
                        thiet_bi=template.thiet_bi,
                        to_may=template.to_may,
                        nhom_thiet_bi=template.nhom_thiet_bi,
                        thu_tu=template.thu_tu,
                    )
                    for template in templates
                ]
            )

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"lan-chuyen-doi/(?P<lan_id>[^/.]+)",
    )
    def cap_nhat_lan_chuyen_doi(self, request, pk=None, lan_id=None):
        so = self.get_object()
        try:
            lan = so.lan_chuyen_dois.get(pk=lan_id)
        except LanChuyenDoiThietBi.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay lan chuyen doi thiet bi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "DELETE":
            if not _can_delete_weekly_equipment_switch_entry(request.user, lan):
                return Response(
                    {"detail": "Ban khong co quyen xoa lan chuyen doi thiet bi nay."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            lan.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        if not _can_edit_weekly_equipment_switch_entry(request.user, lan):
            return Response(
                {"detail": "Ban khong co quyen cap nhat lan chuyen doi thiet bi nay."},
                status=status.HTTP_403_FORBIDDEN,
            )

        lan_serializer = LanChuyenDoiThietBiSerializer(
            lan,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        lan_serializer.is_valid(raise_exception=True)

        chi_tiets = request.data.get("chi_tiets", [])
        chi_tiet_map = {str(item.id): item for item in lan.chi_tiets.all()}
        allowed_statuses = {choice[0] for choice in ChiTietChuyenDoiThietBi.TrangThai.choices}
        for payload in chi_tiets:
            trang_thai_value = payload.get("trang_thai")
            if trang_thai_value and trang_thai_value not in allowed_statuses:
                return Response(
                    {"detail": f"Trang thai khong hop le: {trang_thai_value}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            lan_serializer.save()
            for payload in chi_tiets:
                chi_tiet = chi_tiet_map.get(str(payload.get("id")))
                if not chi_tiet:
                    continue
                trang_thai_value = payload.get("trang_thai", chi_tiet.trang_thai)
                chi_tiet.trang_thai = trang_thai_value or ""
                chi_tiet.ghi_chu = payload.get("ghi_chu", chi_tiet.ghi_chu)
                chi_tiet.save(update_fields=["trang_thai", "ghi_chu", "updated_at"])

        response_serializer = self.get_serializer(self.get_object())
        return Response(response_serializer.data, status=status.HTTP_200_OK)
