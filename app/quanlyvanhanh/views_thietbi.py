import io

import qrcode
from django.db.models import Q
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from core.factory_scope import (
    apply_request_factory_to_serializer,
    filter_queryset_by_factory,
    has_all_factory_access,
)
from quanlyvanhanh.models import ThietBi
from quanlyvanhanh.serializers import (
    ThietBiDetailSerializer,
    ThietBiListSerializer,
    ThietBiSerializer,
)


class ThietBiPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "limit"
    max_page_size = 200


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


class ThietBiViewSet(viewsets.ModelViewSet):
    """ViewSet quan ly thiet bi."""

    queryset = ThietBi.objects.all()
    serializer_class = ThietBiSerializer
    pagination_class = ThietBiPageNumberPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["loai", "trang_thai", "nha_che_tao", "nha_cung_cap", "cap", "cha"]
    search_fields = [
        "ten",
        "ma",
        "ma_day_du",
        "ma_van_hanh",
        "so_serial",
        "mo_ta_ky_thuat",
    ]
    ordering_fields = ["ten", "ma_day_du", "thu_tu", "do_uu_tien", "cap"]
    ordering = ["cha__id", "thu_tu", "ten"]

    def get_serializer_class(self):
        if self.action == "list":
            return ThietBiListSerializer
        if self.action == "retrieve":
            return ThietBiDetailSerializer
        return ThietBiSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = filter_queryset_by_factory(
            queryset,
            self.request.user,
            "nha_may",
            "string",
        )

        factory_param = (
            self.request.query_params.get("nha_may")
            or self.request.query_params.get("ma_nha_may")
        )
        if factory_param and str(factory_param).lower() != "all":
            factory_value = str(factory_param).strip()
            factory_query = (
                Q(nha_may__iexact=factory_value)
                | Q(ma_day_du__istartswith=f"{factory_value}.")
            )

            try:
                from khovattu.models import Bang_nha_may

                factory = Bang_nha_may.objects.filter(
                    Q(ma_nha_may__iexact=factory_value)
                    | Q(ten_nha_may__iexact=factory_value)
                ).first()
                if factory:
                    factory_query |= Q(nha_may__iexact=factory.ma_nha_may)
                    factory_query |= Q(nha_may__iexact=factory.ten_nha_may)
                    factory_query |= Q(nha_may__icontains=factory.ten_nha_may)
                    factory_query |= Q(ma_day_du__istartswith=f"{factory.ma_nha_may}.")
            except Exception:
                pass

            queryset = queryset.filter(factory_query)

        search_param = self.request.query_params.get("q")
        if search_param:
            search_param = str(search_param).strip()
            parts = [part for part in search_param.split(".") if part]

            if len(parts) >= 3 and all(part.isalnum() for part in parts[:3]):
                queryset = queryset.filter(
                    Q(ma_day_du__istartswith=search_param)
                    | Q(ma_day_du__iexact=search_param)
                )
            else:
                tokens = [token for token in search_param.replace(".", " ").split() if token]
                for token in tokens:
                    token_query = (
                        Q(ten__unaccent__icontains=token)
                        | Q(cha__ten__unaccent__icontains=token)
                        | Q(cha__cha__ten__unaccent__icontains=token)
                        | Q(cha__cha__cha__ten__unaccent__icontains=token)
                        | Q(cha__cha__cha__cha__ten__unaccent__icontains=token)
                        | Q(ma__unaccent__icontains=token)
                        | Q(ma_day_du__icontains=token)
                        | Q(ma_van_hanh__unaccent__icontains=token)
                        | Q(so_serial__unaccent__icontains=token)
                        | Q(mo_ta_ky_thuat__unaccent__icontains=token)
                    )
                    queryset = queryset.filter(token_query)

        return queryset

    def perform_create(self, serializer):
        _ensure_thiet_bi_access(self.request.user, serializer.validated_data.get("cha"))
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
            serializer.validated_data.get("cha", serializer.instance.cha),
        )
        serializer.save(
            **apply_request_factory_to_serializer(
                self.request.user,
                serializer,
                "nha_may",
                "string",
            )
        )

    @action(detail=True, methods=["get"])
    def con(self, request, pk=None):
        thiet_bi = self.get_object()
        con = thiet_bi.con.all()
        serializer = ThietBiListSerializer(con, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def qr(self, request, pk=None):
        thiet_bi = self.get_object()
        qr_data = thiet_bi.ma_day_du or str(thiet_bi.pk)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type="image/png")
        response["Content-Disposition"] = (
            f'inline; filename="QR_{thiet_bi.ma_day_du.replace(".", "_")}.png"'
        )
        return response

    @action(detail=False, methods=["get"])
    def qr_export_items(self, request):
        queryset = self.filter_queryset(self.get_queryset()).order_by("ma_day_du")
        serializer = ThietBiListSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def cay_phan_cap(self, request):
        goc = self.get_queryset().filter(cha__isnull=True).order_by("thu_tu", "ten")
        serializer = ThietBiDetailSerializer(goc, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def tim_kiem(self, request):
        query = request.query_params.get("q", "")
        if query:
            queryset = self.get_queryset().filter(
                Q(ten__icontains=query)
                | Q(ma__icontains=query)
                | Q(ma_day_du__icontains=query)
                | Q(so_serial__icontains=query)
            )
        else:
            queryset = self.get_queryset()

        serializer = ThietBiListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def cap_0_codes(self, request):
        try:
            all_thiet_bi = self.get_queryset().filter(
                ma_day_du__isnull=False
            ).values("ma_day_du", "ten")
            cap_0_info = {}

            for tb in all_thiet_bi:
                ma_day_du = tb["ma_day_du"]
                if ma_day_du:
                    parts = ma_day_du.split(".")
                    if len(parts) >= 3:
                        cap_0_code = ".".join(parts[:3])

                        if ma_day_du == cap_0_code:
                            cap_0_info[cap_0_code] = {
                                "ten": tb["ten"],
                                "ma": parts[-1],
                            }
                        elif cap_0_code not in cap_0_info:
                            cap_0_info[cap_0_code] = {
                                "ten": f"Thiet bi {parts[-1]}",
                                "ma": parts[-1],
                            }

            cap_0_devices = []
            for code in sorted(cap_0_info.keys()):
                info = cap_0_info[code]
                cap_0_devices.append({
                    "id": code,
                    "ma": info["ma"],
                    "ten": info["ten"],
                    "ma_day_du": code,
                    "cap": 0,
                })

            return Response(cap_0_devices)
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def cap_1_by_parent(self, request):
        try:
            parent_code = request.query_params.get("parent_code", "")
            if not parent_code:
                return Response([])

            all_thiet_bi = self.get_queryset().filter(
                ma_day_du__startswith=parent_code + "."
            ).values("ma_day_du", "ten", "cap")
            cap_1_info = {}

            for tb in all_thiet_bi:
                ma_day_du = tb["ma_day_du"]
                if ma_day_du and ma_day_du.startswith(parent_code + "."):
                    parts = ma_day_du.split(".")
                    if len(parts) >= 4:
                        cap_1_code = ".".join(parts[:4])

                        if ma_day_du == cap_1_code:
                            cap_1_info[cap_1_code] = {
                                "ten": tb["ten"],
                                "ma": parts[3],
                            }
                        elif cap_1_code not in cap_1_info:
                            cap_1_info[cap_1_code] = {
                                "ten": f"Thiet bi {parts[3]}",
                                "ma": parts[3],
                            }

            cap_1_devices = []
            for code in sorted(cap_1_info.keys()):
                info = cap_1_info[code]
                cap_1_devices.append({
                    "id": code,
                    "ma": info["ma"],
                    "ten": info["ten"],
                    "ma_day_du": code,
                    "cap": 1,
                })

            return Response(cap_1_devices)
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["get"])
    def cap_2_by_parent(self, request):
        try:
            parent_code = request.query_params.get("parent_code", "")
            if not parent_code:
                return Response([])

            all_thiet_bi = self.get_queryset().filter(
                ma_day_du__startswith=parent_code + "."
            ).values("ma_day_du", "ten", "cap")
            cap_2_info = {}

            for tb in all_thiet_bi:
                ma_day_du = tb["ma_day_du"]
                if ma_day_du and ma_day_du.startswith(parent_code + "."):
                    parts = ma_day_du.split(".")
                    if len(parts) >= 5:
                        cap_2_code = ".".join(parts[:5])

                        if ma_day_du == cap_2_code:
                            cap_2_info[cap_2_code] = {
                                "ten": tb["ten"],
                                "ma": parts[4],
                            }
                        elif cap_2_code not in cap_2_info:
                            cap_2_info[cap_2_code] = {
                                "ten": f"Thiet bi {parts[4]}",
                                "ma": parts[4],
                            }

            cap_2_devices = []
            for code in sorted(cap_2_info.keys()):
                info = cap_2_info[code]
                cap_2_devices.append({
                    "id": code,
                    "ma": info["ma"],
                    "ten": info["ten"],
                    "ma_day_du": code,
                    "cap": 2,
                })

            return Response(cap_2_devices)
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
