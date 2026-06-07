from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.factory_scope import (
    apply_request_factory_to_serializer,
    filter_queryset_by_factory,
)
from quanlyvanhanh.models import ThietBi, ThongSoToMay
from quanlyvanhanh.serializers import (
    ThongSoToMayCreateSerializer,
    ThongSoToMaySerializer,
)
from quanlyvanhanh.services.thongso_tomay_service import (
    bulk_upsert_thong_so_to_may,
)


def _ensure_thiet_bi_access(user, thiet_bi):
    if not thiet_bi:
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


class ThongSoToMayViewSet(viewsets.ModelViewSet):
    """ViewSet quan ly thong so to may va legacy endpoints."""

    queryset = ThongSoToMay.objects.select_related("thiet_bi").all()
    serializer_class = ThongSoToMaySerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["thiet_bi", "ten_thong_so", "nha_may", "ngay_nhap"]
    search_fields = ["ten_thong_so", "ma_thong_so", "thiet_bi__ten", "ghi_chu"]
    ordering_fields = ["ten_thong_so", "ngay_nhap", "thoi_diem_nhap", "created_at"]
    ordering = ["-ngay_nhap", "-thoi_diem_nhap"]

    def get_serializer_class(self):
        if self.action in ["create", "bulk_upsert", "bulk_create"]:
            return ThongSoToMayCreateSerializer
        return ThongSoToMaySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return filter_queryset_by_factory(
            queryset,
            self.request.user,
            "nha_may",
            "string",
        )

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
    def by_date(self, request):
        date_value = request.query_params.get("date") or request.query_params.get("ngay")
        if not date_value:
            return Response(
                {"error": "Can cung cap date hoac ngay"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset().filter(ngay_nhap=date_value)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def by_device(self, request):
        device_id = request.query_params.get("device_id") or request.query_params.get("thiet_bi_id")
        device_code = request.query_params.get("device_code") or request.query_params.get("thiet_bi_ma")

        if not (device_id or device_code):
            return Response(
                {
                    "error": (
                        "Can cung cap device_id/thiet_bi_id "
                        "hoac device_code/thiet_bi_ma"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset()
        if device_id:
            queryset = queryset.filter(thiet_bi_id=device_id)
        else:
            queryset = queryset.filter(thiet_bi__ma_day_du=device_code)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        return self.bulk_upsert(request)

    @action(detail=False, methods=["post"])
    def bulk_upsert(self, request):
        data_list = request.data
        if not isinstance(data_list, list):
            return Response(
                {"error": "Du lieu phai la mot mang"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = bulk_upsert_thong_so_to_may(request.user, data_list)
        except PermissionDenied:
            raise
        except Exception as exc:
            return Response(
                {"error": f"Loi khi xu ly du lieu: {exc}"},
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
            status=(
                status.HTTP_201_CREATED
                if result["created"] > 0
                else status.HTTP_200_OK
            ),
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
                "message": f"Da xoa {deleted_count} thong so to may",
                "deleted_count": deleted_count,
            }
        )
