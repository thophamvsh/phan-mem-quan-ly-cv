from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.factory_scope import (
    apply_request_factory_to_serializer,
    filter_queryset_by_factory,
    get_user_factory_name,
    has_all_factory_access,
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
