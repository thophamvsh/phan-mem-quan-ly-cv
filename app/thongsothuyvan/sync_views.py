from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .google_sheet_services import (
    GOOGLE_SHEET_SYNC_START_DATE,
    INSUFFICIENT_SAN_LUONG_MESSAGE,
    INVALID_SYNC_DATE_MESSAGE,
    MIN_SAN_LUONG_FILLED_FIELDS,
    SAN_LUONG_SYNC_FIELDS,
    GoogleSheetHydrologyService,
    GoogleSheetSyncError,
    count_san_luong_filled_fields,
    get_allowed_sync_date,
    get_env_value,
    get_gio_phat_rows,
    get_gio_phat_sheet_row_number,
    get_gspread_client,
    get_san_luong_rows,
    get_san_luong_sheet_row_number,
    get_spreadsheet_id,
    get_sync_date_error,
    is_date_after_allowed,
    is_san_luong_row_complete_enough,
    parse_cot_c,
    parse_date,
    parse_filter_date,
    parse_gio_phat_records,
    parse_gio_phat_records_with_metadata,
    parse_item_date,
    parse_san_luong_records,
    parse_san_luong_records_with_metadata,
    parse_to_may,
    prefix_sheet_range_rows,
    safe_float,
    safe_float_vinhson_decimal,
    safe_int_vinhson,
)
from .plants import normalize_plant_code
from .views.views_sanxuat import user_can_access_plant


def user_can_modify_hydrology_object(user, obj):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    created_by_id = getattr(obj, "created_by_id", None)
    return created_by_id is None or created_by_id == user.id


def user_can_write_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(
        profile
        and (
            profile.can_create_hydrology_data
            or profile.can_edit_hydrology_data
        )
    )


def _preview_payload(result, message):
    return {
        "success": True,
        "data": result.data,
        "rows": result.data,
        "skipped_rows": result.skipped_rows,
        "warnings": result.warnings,
        "source_range": result.source_range,
        "message": message,
    }


def _google_sheet_error_response(exc):
    return Response({"error": exc.user_message}, status=status.HTTP_502_BAD_GATEWAY)


class PreviewGoogleSheetAPIView(APIView):
    """API đọc dữ liệu từ Google Sheet để hiển thị, chưa lưu vào DB."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        nhamay = normalize_plant_code(request.query_params.get("nhamay", "songhinh"))
        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Bạn không có quyền truy cập dữ liệu của nhà máy này."},
                status=status.HTTP_403_FORBIDDEN,
            )

        filter_date_str = request.query_params.get("date")
        filter_date = parse_filter_date(filter_date_str)
        if filter_date_str and not filter_date:
            return Response({"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"}, status=400)

        sync_date_error = get_sync_date_error(filter_date_str, filter_date)
        if sync_date_error:
            return Response(sync_date_error, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = GoogleSheetHydrologyService().preview_san_luong(nhamay, filter_date)
        except GoogleSheetSyncError as exc:
            return _google_sheet_error_response(exc)

        return Response(
            _preview_payload(
                result,
                f"Đã lấy dữ liệu thành công từ tab Sản lượng ({nhamay})",
            )
        )


class SaveGoogleSheetDataAPIView(APIView):
    """API lưu dữ liệu sản lượng đã xem trước vào database."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_can_write_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen dong bo du lieu thuy van."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data_list = request.data.get("data", [])
        nhamay = normalize_plant_code(request.query_params.get("nhamay", "songhinh"))
        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Bạn không có quyền đồng bộ dữ liệu của nhà máy này."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not data_list:
            return Response({"error": "Không có dữ liệu để lưu"}, status=400)

        allowed_sync_date = get_allowed_sync_date()
        invalid_date_rows = [
            item for item in data_list
            if item.get("thoi_gian") and is_date_after_allowed(item.get("thoi_gian"), allowed_sync_date)
        ]
        if invalid_date_rows:
            return Response(
                {
                    "success": False,
                    "error": INVALID_SYNC_DATE_MESSAGE,
                    "max_allowed_date": str(allowed_sync_date),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        insufficient_rows = [
            item for item in data_list
            if item.get("thoi_gian") and not is_san_luong_row_complete_enough(item)
        ]
        if insufficient_rows:
            return Response(
                {
                    "success": False,
                    "error": INSUFFICIENT_SAN_LUONG_MESSAGE,
                    "detail": (
                        f"Co {len(insufficient_rows)} dong chi co vai cot co du lieu, "
                        "nen he thong khong cap nhat de tranh ghi de du lieu cu."
                    ),
                    "min_filled_fields": MIN_SAN_LUONG_FILLED_FIELDS,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = GoogleSheetHydrologyService().save_san_luong(
                data_list=data_list,
                nhamay=nhamay,
                user=request.user,
                can_modify=user_can_modify_hydrology_object,
            )
        except PermissionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                "success": True,
                "message": (
                    f"Đã lưu thành công. Tạo mới: {result.saved_count}, "
                    f"Cập nhật: {result.updated_count}"
                ),
            }
        )


class PreviewGioPhatAPIView(APIView):
    """API đọc dữ liệu từ tab Giờ phát."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        nhamay = normalize_plant_code(request.query_params.get("nhamay", "songhinh"))
        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Bạn không có quyền truy cập dữ liệu của nhà máy này."},
                status=status.HTTP_403_FORBIDDEN,
            )

        filter_date_str = request.query_params.get("date")
        filter_date = parse_filter_date(filter_date_str)
        if filter_date_str and not filter_date:
            return Response({"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"}, status=400)

        sync_date_error = get_sync_date_error(filter_date_str, filter_date)
        if sync_date_error:
            return Response(sync_date_error, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = GoogleSheetHydrologyService().preview_gio_phat(nhamay, filter_date)
        except GoogleSheetSyncError as exc:
            return _google_sheet_error_response(exc)

        return Response(_preview_payload(result, "Đã lấy dữ liệu thành công từ tab Giờ phát"))


class SaveGioPhatAPIView(APIView):
    """API lưu dữ liệu Giờ phát vào database."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_can_write_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen dong bo du lieu gio phat."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data_list = request.data.get("data", [])
        nhamay = normalize_plant_code(request.query_params.get("nhamay", "songhinh"))
        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Bạn không có quyền đồng bộ dữ liệu của nhà máy này."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not data_list:
            return Response({"error": "Không có dữ liệu để lưu"}, status=400)

        allowed_sync_date = get_allowed_sync_date()
        invalid_date_rows = [
            item for item in data_list
            if item.get("ngay") and is_date_after_allowed(item.get("ngay"), allowed_sync_date)
        ]
        if invalid_date_rows:
            return Response(
                {
                    "success": False,
                    "error": INVALID_SYNC_DATE_MESSAGE,
                    "max_allowed_date": str(allowed_sync_date),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = GoogleSheetHydrologyService().save_gio_phat(
                data_list=data_list,
                nhamay=nhamay,
                user=request.user,
                can_modify=user_can_modify_hydrology_object,
            )
        except PermissionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_403_FORBIDDEN)

        return Response(
            {
                "success": True,
                "message": (
                    f"Đã lưu thành công. Tạo mới: {result.saved_count}, "
                    f"Cập nhật: {result.updated_count}"
                ),
            }
        )
