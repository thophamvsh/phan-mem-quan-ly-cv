from decimal import Decimal

from auditlog.models import LogEntry
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from core.factory_scope import ensure_factory_allowed
from core.throttles import (
    MonthlySwitchQRResolveRateThrottle,
    MonthlySwitchQRSaveRateThrottle,
)
from nhatkyvanhanh.models import (
    ChiTietChuyenDoiTBThang,
    MauChuyenDoiTBThang,
    SoChuyenDoiTBThang,
)
from nhatkyvanhanh.permissions import (
    CanEditMonthlyEquipmentSwitchLogs,
    CanViewMonthlyEquipmentSwitchLogs,
    has_profile_permission,
)
from nhatkyvanhanh.serializers import (
    ChiTietChuyenDoiTBThangSerializer,
    MonthlySwitchQRResolveQuerySerializer,
    MonthlySwitchQRSaveSerializer,
)
from nhatkyvanhanh.services import MonthlySwitchCalculationService

from .helpers import (
    _can_edit_monthly_equipment_switch_log,
    _monthly_switch_log_locked,
)


def _error_response(
    *, detail, code, http_status, business_status=None, errors=None
):
    payload = {"detail": detail, "code": code}
    if business_status:
        payload["status"] = business_status
    if errors is not None:
        payload["errors"] = errors
    return Response(payload, status=http_status)


def _decimal_snapshot(row):
    return {
        "cuoi_thang": str(row.cuoi_thang.quantize(Decimal("0.001"))),
        "nhap_trong_thang": str(
            row.nhap_trong_thang.quantize(Decimal("0.001"))
        ),
        "thuc_hien": str(row.thuc_hien.quantize(Decimal("0.001"))),
        "luy_ke_nam": str(row.luy_ke_nam.quantize(Decimal("0.001"))),
        "ghi_chu": row.ghi_chu,
    }


def _append_qr_audit_metadata(row, *, request, identity, client_time, old_values):
    entry = (
        LogEntry.objects.get_for_object(row)
        .filter(action=LogEntry.Action.UPDATE)
        .order_by("-timestamp", "-id")
        .first()
    )
    if not entry:
        return

    metadata = entry.additional_data if isinstance(entry.additional_data, dict) else {}
    metadata.update(
        {
            "source": "monthly_switch_qr",
            "identity": str(identity),
            "scan_mode": "device",
            "qr_user_id": request.user.pk,
            "client_time": client_time.isoformat() if client_time else None,
            "server_time": timezone.localtime().isoformat(),
            "old_values": old_values,
            "new_values": _decimal_snapshot(row),
        }
    )
    LogEntry.objects.filter(pk=entry.pk).update(additional_data=metadata)


class MonthlySwitchQuickEntryViewSet(viewsets.ViewSet):
    """Resolve and safely update one monthly-switch row from a physical QR."""

    def get_permissions(self):
        permission_classes = [CanViewMonthlyEquipmentSwitchLogs]
        if self.action == "save":
            permission_classes = [CanEditMonthlyEquipmentSwitchLogs]
        return [permission() for permission in permission_classes]

    def get_throttles(self):
        if self.action == "resolve":
            return [MonthlySwitchQRResolveRateThrottle()]
        if self.action == "save":
            return [MonthlySwitchQRSaveRateThrottle()]
        return super().get_throttles()

    @action(detail=False, methods=["get"], url_path="resolve")
    def resolve(self, request):
        query = MonthlySwitchQRResolveQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                detail="Mã QR hoặc kỳ sổ không hợp lệ.",
                code="invalid_qr_payload",
                errors=query.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        data = query.validated_data

        template = (
            MauChuyenDoiTBThang.objects.select_related("nha_may", "thiet_bi")
            .filter(ma_dinh_danh=data["identity"])
            .first()
        )
        if not template:
            return _error_response(
                detail="Không tìm thấy thiết bị tương ứng với mã QR.",
                code="template_not_found",
                business_status="template_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        ensure_factory_allowed(request.user, template.nha_may)
        if not template.dang_su_dung:
            return _error_response(
                detail="Thiết bị này đã ngừng theo dõi trong mẫu tháng.",
                code="inactive_template",
                business_status="inactive_template",
                http_status=status.HTTP_409_CONFLICT,
            )

        local_date = timezone.localdate()
        year = data.get("year", local_date.year)
        month = data.get("month", local_date.month)
        log = (
            SoChuyenDoiTBThang.objects.select_related("nha_may", "nguoi_tao")
            .filter(nha_may=template.nha_may, nam=year, thang=month)
            .first()
        )
        if not log:
            can_create = has_profile_permission(
                request.user, "can_create_monthly_equipment_switch_logs"
            )
            return Response(
                {
                    "status": "log_not_found",
                    "code": "log_not_found",
                    "detail": (
                        "Chưa có Sổ chuyển đổi thiết bị cho tháng hiện tại."
                    ),
                    "can_create": can_create,
                    "create_defaults": {
                        "nha_may": template.nha_may_id,
                        "nam": year,
                        "thang": month,
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        row = log.chi_tiets.filter(ma_dinh_danh=template.ma_dinh_danh).first()
        if not row:
            return _error_response(
                detail="Sổ tháng chưa có dòng thiết bị tương ứng với mã QR.",
                code="row_not_found",
                business_status="row_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        is_locked = _monthly_switch_log_locked(log)
        can_edit = bool(
            not is_locked
            and _can_edit_monthly_equipment_switch_log(request.user, log)
        )
        response_status = "locked" if is_locked else "editable"
        row_data = ChiTietChuyenDoiTBThangSerializer(
            row,
            context={"request": request},
        ).data
        return Response(
            {
                "status": response_status,
                "server_time": timezone.localtime().isoformat(),
                "log_summary": {
                    "id": str(log.pk),
                    "nam": log.nam,
                    "thang": log.thang,
                    "ca_truc": log.ca_truc,
                    "trang_thai": log.trang_thai,
                    "da_khoa": is_locked,
                },
                "plant": {
                    "id": template.nha_may_id,
                    "code": template.nha_may.ma_nha_may,
                    "name": template.nha_may.ten_nha_may,
                },
                "can_edit": can_edit,
                "version": row.updated_at.isoformat(),
                "row": row_data,
            }
        )

    @action(detail=False, methods=["post"], url_path="save")
    def save(self, request):
        unexpected_fields = sorted(
            set(request.data) - set(MonthlySwitchQRSaveSerializer().fields)
        )
        if unexpected_fields:
            return _error_response(
                detail=(
                    "Payload chứa trường không được phép cập nhật: "
                    + ", ".join(unexpected_fields)
                ),
                code="unexpected_fields",
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MonthlySwitchQRSaveSerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                detail="Dữ liệu cập nhật không hợp lệ.",
                code="validation_error",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data

        with transaction.atomic():
            log = (
                SoChuyenDoiTBThang.objects.select_for_update()
                .filter(pk=data["log_id"])
                .first()
            )
            if not log:
                return _error_response(
                    detail="Không tìm thấy Sổ chuyển đổi thiết bị tháng.",
                    code="log_not_found",
                    http_status=status.HTTP_404_NOT_FOUND,
                )

            ensure_factory_allowed(request.user, log.nha_may)
            if _monthly_switch_log_locked(log):
                return _error_response(
                    detail="Sổ chuyển đổi thiết bị tháng đã được duyệt và khóa.",
                    code="log_locked",
                    business_status="locked",
                    http_status=status.HTTP_409_CONFLICT,
                )
            if not _can_edit_monthly_equipment_switch_log(request.user, log):
                return _error_response(
                    detail="Bạn không có quyền cập nhật sổ tháng này.",
                    code="permission_denied",
                    http_status=status.HTTP_403_FORBIDDEN,
                )

            row = (
                ChiTietChuyenDoiTBThang.objects.select_for_update()
                .filter(so=log, ma_dinh_danh=data["identity"])
                .first()
            )
            if not row:
                return _error_response(
                    detail="Không tìm thấy dòng thiết bị trong sổ tháng.",
                    code="row_not_found",
                    http_status=status.HTTP_404_NOT_FOUND,
                )
            if row.updated_at != data["expected_updated_at"]:
                return _error_response(
                    detail=(
                        "Dữ liệu thiết bị này vừa được cập nhật bởi một người dùng "
                        "khác. Vui lòng tải lại số liệu mới nhất."
                    ),
                    code="concurrent_modification",
                    http_status=status.HTTP_409_CONFLICT,
                )

            old_values = _decimal_snapshot(row)
            update_payload = {
                field: data[field]
                for field in ("cuoi_thang", "nhap_trong_thang", "ghi_chu")
                if field in data
            }
            try:
                propagation = MonthlySwitchCalculationService.update_rows_and_propagate(
                    log,
                    [{"id": row.pk, **update_payload}],
                    serializer_context={"request": request},
                )
            except DRFValidationError as exc:
                return _error_response(
                    detail="Số liệu nhập không phù hợp với quy tắc của sổ tháng.",
                    code="validation_error",
                    errors=exc.detail,
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            row.refresh_from_db()
            _append_qr_audit_metadata(
                row,
                request=request,
                identity=data["identity"],
                client_time=data.get("client_time"),
                old_values=old_values,
            )

        return Response(
            {
                "status": "saved",
                "server_time": timezone.localtime().isoformat(),
                "version": row.updated_at.isoformat(),
                "row": ChiTietChuyenDoiTBThangSerializer(
                    row,
                    context={"request": request},
                ).data,
                "propagation": propagation,
            }
        )
