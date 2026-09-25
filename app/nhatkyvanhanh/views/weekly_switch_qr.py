from datetime import datetime, time
import unicodedata

from auditlog.models import LogEntry
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.factory_scope import (
    ensure_factory_allowed,
    get_user_factory,
    has_all_factory_access,
)
from core.throttles import (
    WeeklySwitchQRReadRateThrottle,
    WeeklySwitchQRWriteRateThrottle,
)
from nhatkyvanhanh.models import (
    ChiTietChuyenDoiThietBi,
    LanChuyenDoiThietBi,
    MauChuyenDoiThietBi,
    SoChuyenDoiThietBiTuan,
)
from nhatkyvanhanh.permissions import (
    CanEditWeeklyEquipmentSwitchLogs,
    CanViewWeeklyEquipmentSwitchLogs,
)
from nhatkyvanhanh.serializers import (
    ChiTietChuyenDoiThietBiSerializer,
    WeeklySwitchQRCreateLanSerializer,
    WeeklySwitchQRLookupQuerySerializer,
    WeeklySwitchQRResolveQuerySerializer,
    WeeklySwitchQRSaveSerializer,
)
from nhatkyvanhanh.weekly_switch_pairs import (
    find_weekly_pair,
    is_complementary_weekly_group,
    opposite_weekly_status,
)
from tochuc.models import NhaMay

from .helpers import (
    _can_edit_weekly_equipment_switch_log,
    _get_previous_weekly_switch_log,
    _weekly_switch_log_locked,
)


def _error_response(*, detail, code, http_status, business_status=None, errors=None):
    payload = {"detail": detail, "code": code}
    if business_status:
        payload["status"] = business_status
    if errors is not None:
        payload["errors"] = errors
    return Response(payload, status=http_status)


def _template_payload(template):
    return {
        "identity": str(template.pk),
        "thiet_bi_id": template.thiet_bi_id,
        "thiet_bi_ten": template.thiet_bi.ten,
        "thiet_bi_ma_day_du": template.thiet_bi.ma_day_du,
        "thiet_bi_ma": template.thiet_bi.ma,
        "khu_vuc": (
            template.khu_vuc.ten_khu_vuc
            if template.khu_vuc_id
            else template.get_to_may_display()
        ),
        "nhom_thiet_bi": template.nhom_thiet_bi,
        "plant": {
            "id": template.nha_may_id,
            "code": template.nha_may.ma_nha_may,
            "name": template.nha_may.ten_nha_may,
        },
    }


def _normalize_group_name(value):
    normalized = unicodedata.normalize("NFD", (value or "").strip().casefold())
    normalized = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    return " ".join(normalized.replace("_", " ").split())


def _is_vinh_son_machine_group(template):
    return (
        (getattr(template.nha_may, "ma_nha_may", "") or "").strip().upper()
        == "VS"
        and _normalize_group_name(template.nhom_thiet_bi) == "to may"
    )


def _template_group_key(template):
    group_name = (template.nhom_thiet_bi or "").strip()
    if _is_vinh_son_machine_group(template):
        return (template.nha_may_id, "vinh_son_machine_group", "to may")
    area_key = template.khu_vuc_id or f"legacy:{template.to_may}"
    return (
        template.nha_may_id,
        area_key,
        group_name.casefold() if group_name else f"device:{template.pk}",
    )


def _group_templates(template):
    """Return active template members represented by any QR in the group."""
    queryset = MauChuyenDoiThietBi.objects.select_related(
        "nha_may", "khu_vuc", "thiet_bi"
    ).filter(nha_may=template.nha_may, dang_su_dung=True)
    group_name = (template.nhom_thiet_bi or "").strip()
    if not _is_vinh_son_machine_group(template):
        if template.khu_vuc_id:
            queryset = queryset.filter(khu_vuc_id=template.khu_vuc_id)
        else:
            queryset = queryset.filter(khu_vuc__isnull=True, to_may=template.to_may)
    if group_name:
        queryset = queryset.filter(nhom_thiet_bi__iexact=group_name)
    else:
        queryset = queryset.filter(pk=template.pk)
    return list(queryset.order_by("khu_vuc__thu_tu", "to_may", "thu_tu", "created_at"))


def _group_type(template, members):
    if len(members) == 2 and is_complementary_weekly_group(
        template.nhom_thiet_bi
    ):
        return "cap_du_phong"
    if len(members) > 1:
        return "nhom_dong_bo"
    return "don_le"


def _group_payload(template, members):
    return {
        "identity": str(template.pk),
        "name": template.nhom_thiet_bi or template.thiet_bi.ten,
        "type": _group_type(template, members),
        "member_count": len(members),
        "area": (
            "Các khu vực thuộc nhóm Tổ máy"
            if _is_vinh_son_machine_group(template)
            else template.khu_vuc.ten_khu_vuc
            if template.khu_vuc_id
            else template.get_to_may_display()
        ),
    }


def _rows_for_templates(run_rows, templates):
    device_ids = {item.thiet_bi_id for item in templates}
    return [row for row in run_rows if row.thiet_bi_id in device_ids]


def _serialize_group_row(row, request):
    payload = ChiTietChuyenDoiThietBiSerializer(
        row, context={"request": request}
    ).data
    previous = payload.get("trang_thai_tuan_truoc") or ""
    payload["suggested_status"] = opposite_weekly_status(previous)
    payload["version"] = row.updated_at.isoformat()
    payload["qr_confirmation"] = _qr_confirmation_payload(row)
    return payload


def _user_display(user):
    if not user:
        return ""
    profile = getattr(user, "profile", None)
    profile_name = getattr(profile, "ho_ten", "") if profile else ""
    if profile_name:
        return profile_name.strip()
    full_name = " ".join(
        filter(
            None,
            (
                getattr(user, "first_name", ""),
                getattr(user, "last_name", ""),
            ),
        )
    ).strip()
    return full_name or getattr(user, "username", "") or getattr(user, "email", "")


def _append_audit_metadata(instance, *, source, request, metadata):
    entry = (
        LogEntry.objects.get_for_object(instance)
        .order_by("-timestamp", "-id")
        .first()
    )
    if not entry:
        return
    additional_data = (
        entry.additional_data if isinstance(entry.additional_data, dict) else {}
    )
    additional_data.update(
        {
            "source": source,
            "qr_user_id": request.user.pk,
            "qr_user_display": _user_display(request.user),
            "server_time": timezone.localtime().isoformat(),
            **metadata,
        }
    )
    LogEntry.objects.filter(pk=entry.pk).update(additional_data=additional_data)


def _qr_confirmation_payload(row):
    entry = (
        LogEntry.objects.get_for_object(row)
        .select_related("actor")
        .order_by("-timestamp", "-id")
        .first()
    )
    metadata = (
        entry.additional_data
        if entry and isinstance(entry.additional_data, dict)
        else {}
    )
    is_confirmed = bool(
        entry
        and metadata.get("source") in {
            "weekly_switch_qr",
            "weekly_switch_qr_pair_sync",
            "weekly_switch_qr_group",
        }
        and metadata.get("confirmed")
    )
    if not is_confirmed:
        return {
            "confirmed": False,
            "confirmed_at": None,
            "confirmed_by": "",
        }
    actor_name = _user_display(entry.actor) or metadata.get(
        "qr_user_display", ""
    )
    return {
        "confirmed": True,
        "confirmed_at": metadata.get("server_time")
        or timezone.localtime(entry.timestamp).isoformat(),
        "confirmed_by": actor_name,
    }


def _switch_time_for_log(log):
    now = timezone.localtime()
    if log.tuan_bat_dau <= now.date() <= log.tuan_ket_thuc:
        return now
    naive = datetime.combine(log.tuan_bat_dau, time(hour=8))
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _paired_device_payload(rows, row):
    members = find_weekly_pair(rows, row)
    if len(members) != 2:
        return None
    companion = next(member for member in members if member.pk != row.pk)
    return {
        "id": str(companion.pk),
        "thiet_bi_ten": companion.thiet_bi.ten,
        "thiet_bi_ma_day_du": companion.thiet_bi.ma_day_du,
        "trang_thai": companion.trang_thai,
        "trang_thai_display": (
            companion.get_trang_thai_display() if companion.trang_thai else ""
        ),
    }


class WeeklySwitchQuickEntryViewSet(viewsets.ViewSet):
    """Resolve and safely update one weekly-switch row from a physical QR."""

    def get_permissions(self):
        permission_classes = [CanViewWeeklyEquipmentSwitchLogs]
        if self.action in {"save", "create_lan"}:
            permission_classes = [CanEditWeeklyEquipmentSwitchLogs]
        return [permission() for permission in permission_classes]

    def get_throttles(self):
        if self.action in {"resolve", "lookup"}:
            return [WeeklySwitchQRReadRateThrottle()]
        if self.action in {"save", "create_lan"}:
            return [WeeklySwitchQRWriteRateThrottle()]
        return super().get_throttles()

    def _get_template(self, identity):
        template = (
            MauChuyenDoiThietBi.objects.select_related(
                "nha_may", "khu_vuc", "thiet_bi"
            )
            .filter(pk=identity)
            .first()
        )
        if not template:
            return None, _error_response(
                detail="Không tìm thấy thiết bị tương ứng với mã QR.",
                code="template_not_found",
                business_status="template_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        ensure_factory_allowed(self.request.user, template.nha_may)
        if not template.dang_su_dung:
            return None, _error_response(
                detail="Thiết bị này đã ngừng theo dõi trong mẫu tuần.",
                code="inactive_template",
                business_status="inactive_template",
                http_status=status.HTTP_409_CONFLICT,
            )
        return template, None

    @action(detail=False, methods=["get"], url_path="resolve")
    def resolve(self, request):
        serializer = WeeklySwitchQRResolveQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return _error_response(
                detail="Mã QR hoặc kỳ sổ không hợp lệ.",
                code="invalid_qr_payload",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        template, error = self._get_template(data["identity"])
        if error:
            return error

        iso = timezone.localdate().isocalendar()
        year = data.get("year", iso.year)
        week = data.get("week", iso.week)
        logs = SoChuyenDoiThietBiTuan.objects.select_related(
            "nha_may", "nguoi_tao", "nguoi_duyet"
        ).filter(nha_may=template.nha_may, nam=year, tuan=week)

        shift = data.get("shift")
        if shift:
            logs = logs.filter(ca_truc=shift)
        else:
            count = logs.count()
            if count > 1:
                available = [
                    {
                        "shift": log.ca_truc,
                        "log_id": str(log.pk),
                        "da_khoa": _weekly_switch_log_locked(log),
                    }
                    for log in logs.order_by("ca_truc")
                ]
                return Response(
                    {
                        "status": "shift_required",
                        "code": "shift_required",
                        "detail": "Tuần này có nhiều sổ. Vui lòng chọn ca trực.",
                        "available_shifts": available,
                        "plant": _template_payload(template)["plant"],
                        "year": year,
                        "week": week,
                    }
                )

        log = logs.first()
        if not log:
            return Response(
                {
                    "status": "log_not_found",
                    "code": "log_not_found",
                    "detail": "Chưa có Sổ chuyển đổi thiết bị cho tuần và ca đã chọn.",
                    "can_create": False,
                    "create_defaults": {
                        "nha_may": template.nha_may_id,
                        "nam": year,
                        "tuan": week,
                        "ca_truc": shift,
                    },
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        is_locked = _weekly_switch_log_locked(log)
        can_edit = bool(
            not is_locked
            and _can_edit_weekly_equipment_switch_log(request.user, log)
        )
        runs = list(log.lan_chuyen_dois.order_by("thoi_gian", "created_at")[:2])
        if not runs:
            return Response(
                {
                    "status": "lan_not_found",
                    "code": "lan_not_found",
                    "detail": "Sổ tuần chưa được khởi tạo lần chuyển đổi.",
                    "can_initialize": can_edit,
                    "log_summary": self._log_summary(log),
                    "plant": _template_payload(template)["plant"],
                }
            )
        if len(runs) > 1:
            return _error_response(
                detail="Sổ tuần có nhiều lần chuyển đổi bất thường.",
                code="multiple_switch_entries_found",
                http_status=status.HTTP_409_CONFLICT,
            )

        run = runs[0]
        run_rows = list(
            run.chi_tiets.select_related("thiet_bi", "khu_vuc").all()
        )
        group_templates = _group_templates(template)
        group_rows = _rows_for_templates(run_rows, group_templates)
        if not group_rows:
            return _error_response(
                detail="Sổ tuần chưa có nhóm thiết bị tương ứng với mã QR.",
                code="row_not_found",
                business_status="row_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        if len(group_rows) != len(group_templates):
            return _error_response(
                detail="Nhóm thiết bị trong sổ tuần không đầy đủ so với mẫu đang áp dụng.",
                code="incomplete_group",
                http_status=status.HTTP_409_CONFLICT,
            )

        row_data = _serialize_group_row(group_rows[0], request)
        response_status = "locked" if is_locked else "editable"
        return Response(
            {
                "status": response_status,
                "server_time": timezone.localtime().isoformat(),
                "log_summary": self._log_summary(log),
                "lan_summary": {
                    "id": str(run.pk),
                    "thoi_gian": run.thoi_gian.isoformat(),
                    "nguoi_thuc_hien": str(run.nguoi_thuc_hien or ""),
                },
                "plant": _template_payload(template)["plant"],
                "group": _group_payload(template, group_templates),
                "rows": [
                    _serialize_group_row(item, request) for item in group_rows
                ],
                "can_edit": can_edit,
                # Keep legacy fields while old clients are still deployed.
                "version": group_rows[0].updated_at.isoformat(),
                "qr_confirmation": _qr_confirmation_payload(group_rows[0]),
                "paired_device": _paired_device_payload(
                    group_rows, group_rows[0]
                ),
                "row": row_data,
            }
        )

    @staticmethod
    def _log_summary(log):
        return {
            "id": str(log.pk),
            "nam": log.nam,
            "tuan": log.tuan,
            "ca_truc": log.ca_truc,
            "tuan_bat_dau": log.tuan_bat_dau,
            "tuan_ket_thuc": log.tuan_ket_thuc,
            "trang_thai": log.trang_thai,
            "da_khoa": _weekly_switch_log_locked(log),
        }

    @action(detail=False, methods=["get"], url_path="lookup")
    def lookup(self, request):
        serializer = WeeklySwitchQRLookupQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return _error_response(
                detail="Mã thiết bị không hợp lệ.",
                code="invalid_lookup_payload",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        user_factory = get_user_factory(request.user)
        plant_code = data.get("plant")
        if has_all_factory_access(request.user):
            if not plant_code:
                return _error_response(
                    detail="Vui lòng chọn nhà máy trước khi tìm thiết bị.",
                    code="plant_required",
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            plant_query = Q(ma_nha_may__iexact=plant_code)
            if str(plant_code).isdigit():
                plant_query |= Q(pk=int(plant_code))
            plant = NhaMay.objects.filter(plant_query).first()
            if not plant:
                return _error_response(
                    detail="Không tìm thấy nhà máy.",
                    code="plant_not_found",
                    http_status=status.HTTP_404_NOT_FOUND,
                )
        else:
            plant = user_factory
            if plant_code:
                ensure_factory_allowed(request.user, plant_code)

        code = data["code"]
        templates = MauChuyenDoiThietBi.objects.select_related(
            "nha_may", "khu_vuc", "thiet_bi"
        ).filter(nha_may=plant, dang_su_dung=True)
        exact = templates.filter(
            Q(thiet_bi__ma_day_du__iexact=code) | Q(thiet_bi__ma__iexact=code)
        )
        matches = list(exact.order_by("thu_tu", "created_at")[:21])
        if not matches:
            matches = list(
                templates.filter(
                    Q(thiet_bi__ma_day_du__icontains=code)
                    | Q(thiet_bi__ma__icontains=code)
                    | Q(thiet_bi__ten__icontains=code)
                ).order_by("thu_tu", "created_at")[:21]
            )
        if not matches:
            return _error_response(
                detail="Không tìm thấy thiết bị phù hợp.",
                code="equipment_not_found",
                business_status="equipment_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        grouped_matches = {}
        for item in matches:
            group_key = _template_group_key(item)
            grouped_matches.setdefault(group_key, item)
        representatives = list(grouped_matches.values())
        results = []
        for item in representatives[:20]:
            payload = _template_payload(item)
            payload["group"] = _group_payload(item, _group_templates(item))
            results.append(payload)
        if len(representatives) == 1:
            return Response({"status": "resolved", "result": results[0]})
        return Response(
            {
                "status": "equipment_selection_required",
                "results": results,
                "truncated": len(representatives) > 20,
            }
        )

    @action(detail=False, methods=["post"], url_path="save")
    def save(self, request):
        serializer = WeeklySwitchQRSaveSerializer(data=request.data)
        if not serializer.is_valid():
            code = "validation_error"
            if isinstance(serializer.errors, dict):
                code = serializer.errors.get("code", code)
            return _error_response(
                detail="Dữ liệu cập nhật không hợp lệ.",
                code=code,
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        template, error = self._get_template(data["identity"])
        if error:
            return error

        with transaction.atomic():
            log = (
                SoChuyenDoiThietBiTuan.objects.select_for_update()
                .filter(pk=data["log_id"], nha_may=template.nha_may)
                .first()
            )
            if not log:
                return _error_response(
                    detail="Sổ tuần không khớp với thiết bị đã quét.",
                    code="broken_relation_chain",
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            if _weekly_switch_log_locked(log):
                return _error_response(
                    detail="Sổ chuyển đổi thiết bị tuần đã được duyệt và khóa.",
                    code="log_locked",
                    business_status="locked",
                    http_status=status.HTTP_409_CONFLICT,
                )
            if not _can_edit_weekly_equipment_switch_log(request.user, log):
                return _error_response(
                    detail="Bạn không có quyền cập nhật sổ tuần này.",
                    code="permission_denied",
                    http_status=status.HTTP_403_FORBIDDEN,
                )
            run = (
                LanChuyenDoiThietBi.objects.select_for_update()
                .filter(pk=data["lan_id"], so=log)
                .first()
            )
            run_rows = []
            if run:
                run_rows = list(
                    ChiTietChuyenDoiThietBi.objects.select_for_update(of=("self",))
                    .select_related("thiet_bi", "khu_vuc")
                    .filter(lan_chuyen_doi=run)
                )
            group_templates = _group_templates(template)
            group_rows = _rows_for_templates(run_rows, group_templates)
            if not run or not group_rows or len(group_rows) != len(group_templates):
                return _error_response(
                    detail="Dữ liệu sổ, lần chuyển đổi và nhóm thiết bị không đồng nhất.",
                    code="broken_relation_chain",
                    http_status=status.HTTP_400_BAD_REQUEST,
                )

            rows_by_id = {str(item.pk): item for item in group_rows}
            submitted_items = data.get("items") or []
            submitted_by_id = {
                str(item["row_id"]): item for item in submitted_items
            }
            group_type = _group_type(template, group_templates)
            using_group_payload = bool(data.get("working_device_id") or submitted_items)

            if using_group_payload and set(submitted_by_id) != set(rows_by_id):
                return _error_response(
                    detail="Vui lòng gửi đầy đủ trạng thái của tất cả thiết bị trong nhóm.",
                    code="incomplete_group_payload",
                    http_status=status.HTTP_400_BAD_REQUEST,
                )

            for row_id, submitted in submitted_by_id.items():
                current = rows_by_id[row_id]
                if current.updated_at != submitted["expected_updated_at"]:
                    return Response(
                        {
                            "detail": "Dữ liệu vừa được người khác cập nhật. Vui lòng xem lại.",
                            "code": "concurrent_modification",
                            "row_id": row_id,
                            "current_status": current.trang_thai,
                            "current_updated_at": current.updated_at.isoformat(),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

            updates = []
            legacy_primary_id = None
            if data.get("working_device_id"):
                if group_type != "cap_du_phong":
                    return _error_response(
                        detail="Chỉ nhóm thiết bị dự phòng mới được chọn một thiết bị làm việc.",
                        code="invalid_group_mode",
                        http_status=status.HTTP_400_BAD_REQUEST,
                    )
                working_id = data["working_device_id"]
                if working_id not in {item.thiet_bi_id for item in group_rows}:
                    return _error_response(
                        detail="Thiết bị làm việc không thuộc nhóm đã quét.",
                        code="invalid_working_device",
                        http_status=status.HTTP_400_BAD_REQUEST,
                    )
                for item in group_rows:
                    submitted = submitted_by_id[str(item.pk)]
                    updates.append(
                        (
                            item,
                            "lam_viec" if item.thiet_bi_id == working_id else "du_phong",
                            submitted.get("ghi_chu", item.ghi_chu),
                        )
                    )
            elif submitted_items:
                for row_id, submitted in submitted_by_id.items():
                    updates.append(
                        (
                            rows_by_id[row_id],
                            submitted["trang_thai"],
                            submitted.get("ghi_chu", rows_by_id[row_id].ghi_chu),
                        )
                    )
            else:
                # Compatibility with device-level QR payloads already deployed.
                row = next(
                    item for item in group_rows
                    if item.thiet_bi_id == template.thiet_bi_id
                )
                legacy_primary_id = row.pk
                if row.updated_at != data["expected_updated_at"]:
                    return Response(
                        {
                            "detail": "Dữ liệu vừa được người khác cập nhật. Vui lòng xem lại.",
                            "code": "concurrent_modification",
                            "current_status": row.trang_thai,
                            "current_updated_at": row.updated_at.isoformat(),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                updates.append((row, data["trang_thai"], data.get("ghi_chu", row.ghi_chu)))
                pair_members = find_weekly_pair(group_rows, row)
                if len(pair_members) == 2:
                    companion = next(item for item in pair_members if item.pk != row.pk)
                    updates.append((companion, opposite_weekly_status(data["trang_thai"]), companion.ghi_chu))

            operation_id = str(timezone.now().timestamp()).replace(".", "-")
            for row, new_status, new_note in updates:
                old_values = {"trang_thai": row.trang_thai, "ghi_chu": row.ghi_chu}
                row.trang_thai = new_status
                row.ghi_chu = new_note
                row.save(update_fields=["trang_thai", "ghi_chu", "updated_at"])
                _append_audit_metadata(
                    row,
                    source=(
                        "weekly_switch_qr"
                        if legacy_primary_id == row.pk
                        else "weekly_switch_qr_pair_sync"
                        if legacy_primary_id
                        else "weekly_switch_qr_group"
                    ),
                    request=request,
                    metadata={
                        "identity": str(template.pk),
                        "group_name": template.nhom_thiet_bi,
                        "group_type": group_type,
                        "operation_id": operation_id,
                        "client_time": data.get("client_time").isoformat() if data.get("client_time") else None,
                        "old_values": old_values,
                        "new_values": {"trang_thai": row.trang_thai, "ghi_chu": row.ghi_chu},
                        "confirmed": data["confirmed"],
                    },
                )

        paired_update = None
        if legacy_primary_id and len(group_rows) == 2:
            primary = next(item for item in group_rows if item.pk == legacy_primary_id)
            paired_update = _paired_device_payload(group_rows, primary)
        return Response(
            {
                "status": "saved",
                "server_time": timezone.localtime().isoformat(),
                "group": _group_payload(template, group_templates),
                "rows": [_serialize_group_row(item, request) for item in group_rows],
                "version": group_rows[0].updated_at.isoformat(),
                "qr_confirmation": _qr_confirmation_payload(group_rows[0]),
                "paired_update": paired_update,
                "row": _serialize_group_row(group_rows[0], request),
            }
        )

    @action(detail=False, methods=["post"], url_path="create-lan")
    def create_lan(self, request):
        serializer = WeeklySwitchQRCreateLanSerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                detail="Dữ liệu khởi tạo không hợp lệ.",
                code="validation_error",
                errors=serializer.errors,
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        log_id = serializer.validated_data["log_id"]
        with transaction.atomic():
            log = (
                SoChuyenDoiThietBiTuan.objects.select_for_update()
                .filter(pk=log_id)
                .first()
            )
            if not log:
                return _error_response(
                    detail="Không tìm thấy Sổ chuyển đổi thiết bị tuần.",
                    code="log_not_found",
                    http_status=status.HTTP_404_NOT_FOUND,
                )
            ensure_factory_allowed(request.user, log.nha_may)
            if _weekly_switch_log_locked(log):
                return _error_response(
                    detail="Sổ chuyển đổi thiết bị tuần đã được duyệt và khóa.",
                    code="log_locked",
                    business_status="locked",
                    http_status=status.HTTP_409_CONFLICT,
                )
            if not _can_edit_weekly_equipment_switch_log(request.user, log):
                return _error_response(
                    detail="Bạn không có quyền khởi tạo lần chuyển đổi.",
                    code="permission_denied",
                    http_status=status.HTTP_403_FORBIDDEN,
                )

            runs = list(log.lan_chuyen_dois.order_by("created_at")[:2])
            if len(runs) > 1:
                return _error_response(
                    detail="Sổ tuần có nhiều lần chuyển đổi bất thường.",
                    code="multiple_switch_entries_found",
                    http_status=status.HTTP_409_CONFLICT,
                )
            if runs:
                run = runs[0]
                return Response(
                    {
                        "status": "ready",
                        "log_id": str(log.pk),
                        "lan_id": str(run.pk),
                        "created": False,
                        "seeded_row_count": run.chi_tiets.count(),
                        "server_time": timezone.localtime().isoformat(),
                    }
                )

            templates = list(
                MauChuyenDoiThietBi.objects.select_related("thiet_bi", "khu_vuc")
                .filter(nha_may=log.nha_may, dang_su_dung=True)
                .order_by("khu_vuc__thu_tu", "to_may", "thu_tu", "created_at")
            )
            if not templates:
                return _error_response(
                    detail="Nhà máy chưa có mẫu chuyển đổi thiết bị tuần đang hoạt động.",
                    code="template_not_found",
                    http_status=status.HTTP_400_BAD_REQUEST,
                )
            device_ids = [item.thiet_bi_id for item in templates]
            if len(device_ids) != len(set(device_ids)):
                return _error_response(
                    detail="Một thiết bị đang có nhiều mẫu hoạt động. Vui lòng chuẩn hóa mẫu trước.",
                    code="duplicate_active_template",
                    http_status=status.HTTP_409_CONFLICT,
                )

            previous = _get_previous_weekly_switch_log(log)
            previous_statuses = {}
            if previous:
                previous_runs = list(
                    previous.lan_chuyen_dois.order_by(
                        "-thoi_gian", "-created_at"
                    )[:2]
                )
                if len(previous_runs) == 1:
                    previous_statuses = {
                        item.thiet_bi_id: item.trang_thai
                        for item in previous_runs[0].chi_tiets.all()
                    }

            run = LanChuyenDoiThietBi.objects.create(
                so=log,
                thoi_gian=_switch_time_for_log(log),
                nguoi_thuc_hien=request.user,
            )
            rows = ChiTietChuyenDoiThietBi.objects.bulk_create(
                [
                    ChiTietChuyenDoiThietBi(
                        lan_chuyen_doi=run,
                        thiet_bi=template.thiet_bi,
                        khu_vuc=template.khu_vuc,
                        to_may=template.to_may,
                        ten_khu_vuc_snapshot=(
                            template.khu_vuc.ten_khu_vuc
                            if template.khu_vuc_id
                            else template.get_to_may_display()
                        ),
                        nhom_thiet_bi=template.nhom_thiet_bi,
                        thu_tu=template.thu_tu,
                        trang_thai={
                            "lam_viec": "du_phong",
                            "du_phong": "lam_viec",
                        }.get(previous_statuses.get(template.thiet_bi_id), ""),
                    )
                    for template in templates
                ]
            )
            _append_audit_metadata(
                run,
                source="weekly_switch_qr_create_lan",
                request=request,
                metadata={"seeded_row_count": len(rows)},
            )

        return Response(
            {
                "status": "created",
                "log_id": str(log.pk),
                "lan_id": str(run.pk),
                "created": True,
                "seeded_row_count": len(rows),
                "server_time": timezone.localtime().isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )
