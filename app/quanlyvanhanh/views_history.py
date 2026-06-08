from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.factory_scope import has_profile_permission
from quanlyvanhanh.services.thongso_history_service import (
    HistoryQueryError,
    calculate_history,
)


class ThongSoLichSuView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not has_profile_permission(request.user, "can_view_operation_parameters"):
            return Response(
                {
                    "detail": (
                        "Tai khoan cua ban chua duoc cap quyen xem thong so van hanh. "
                        "Vui long lien he quan tri vien."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            payload = calculate_history(request.user, request.query_params)
        except HistoryQueryError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"detail": f"Loi khi truy van du lieu lich su: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(payload, status=status.HTTP_200_OK)
