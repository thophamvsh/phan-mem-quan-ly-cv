from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from ..models.phan_cong_nhiem_vu_hc import BangPhanCongNhiemVuHC, ChiTietNhiemVuThuTrongTuan
from ..serializers.phan_cong_nhiem_vu_hc import (
    BangPhanCongNhiemVuHCSerializer,
    DEFAULT_DUTY_ROSTER_ITEMS,
    DEFAULT_GHI_CHU,
)
from ..permissions import (
    CanViewAdminShiftDutyRosters,
    CanCreateAdminShiftDutyRosters,
    CanEditAdminShiftDutyRosters,
    CanDeleteAdminShiftDutyRosters,
)


class BangPhanCongNhiemVuHCViewSet(viewsets.ModelViewSet):
    queryset = BangPhanCongNhiemVuHC.objects.select_related("nha_may", "nguoi_tao").prefetch_related("chi_tiets")
    serializer_class = BangPhanCongNhiemVuHCSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["nha_may", "thang", "nam"]
    ordering_fields = ["nam", "thang", "created_at"]
    ordering = ["-nam", "-thang"]

    def get_permissions(self):
        if self.action in ["list", "retrieve", "lay_mau_mac_dinh"]:
            permission_classes = [permissions.IsAuthenticated, CanViewAdminShiftDutyRosters]
        elif self.action in ["create", "sao_chep_thang"]:
            permission_classes = [permissions.IsAuthenticated, CanCreateAdminShiftDutyRosters]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [permissions.IsAuthenticated, CanEditAdminShiftDutyRosters]
        elif self.action == "destroy":
            permission_classes = [permissions.IsAuthenticated, CanDeleteAdminShiftDutyRosters]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"])
    def lay_mau_mac_dinh(self, request):
        return Response({
            "tieu_de": "BẢNG PHÂN LÀM VỆ SINH CA KT-VH",
            "dia_diem_lap": "Sông Hinh",
            "ghi_chu": DEFAULT_GHI_CHU,
            "chi_tiets": DEFAULT_DUTY_ROSTER_ITEMS,
        })

    @action(detail=False, methods=["post"])
    def sao_chep_thang(self, request):
        nha_may_id = request.data.get("nha_may")
        tu_thang = request.data.get("tu_thang")
        tu_nam = request.data.get("tu_nam")
        den_thang = request.data.get("den_thang")
        den_nam = request.data.get("den_nam")

        if not all([den_thang, den_nam]):
            return Response(
                {"detail": "Vui lòng chọn tháng và năm đích để sao chép."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if BangPhanCongNhiemVuHC.objects.filter(
            nha_may_id=nha_may_id, thang=den_thang, nam=den_nam
        ).exists():
            return Response(
                {"detail": f"Bảng phân công Tháng {int(den_thang):02d}/{den_nam} đã tồn tại."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        source_roster = None
        if tu_thang and tu_nam:
            source_roster = BangPhanCongNhiemVuHC.objects.filter(
                nha_may_id=nha_may_id, thang=tu_thang, nam=tu_nam
            ).prefetch_related("chi_tiets").first()

        if not source_roster:
            # Fallback to closest previous month
            source_roster = BangPhanCongNhiemVuHC.objects.filter(
                nha_may_id=nha_may_id
            ).exclude(thang=den_thang, nam=den_nam).order_by("-nam", "-thang").prefetch_related("chi_tiets").first()

        title = f"BẢNG PHÂN LÀM VỆ SINH CA KT-VH THÁNG {int(den_thang):02d}/{den_nam}"
        notes = source_roster.ghi_chu if source_roster else DEFAULT_GHI_CHU
        location = source_roster.dia_diem_lap if source_roster else "Sông Hinh"

        new_roster = BangPhanCongNhiemVuHC.objects.create(
            nha_may_id=nha_may_id,
            thang=den_thang,
            nam=den_nam,
            tieu_de=title,
            dia_diem_lap=location,
            ghi_chu=notes,
            nguoi_tao=request.user,
        )

        if source_roster and source_roster.chi_tiets.exists():
            for detail in source_roster.chi_tiets.all():
                ChiTietNhiemVuThuTrongTuan.objects.create(
                    bang_phan_cong=new_roster,
                    stt=detail.stt,
                    thu=detail.thu,
                    noi_dung_nhiem_vu=detail.noi_dung_nhiem_vu,
                )
        else:
            for item in DEFAULT_DUTY_ROSTER_ITEMS:
                ChiTietNhiemVuThuTrongTuan.objects.create(
                    bang_phan_cong=new_roster, **item
                )

        serializer = self.get_serializer(new_roster)
        return Response(serializer.data, status=status.HTTP_201_CREATED)