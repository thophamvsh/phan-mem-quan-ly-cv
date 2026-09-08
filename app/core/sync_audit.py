import hashlib
import json
import os
import re
from datetime import date, datetime
from functools import wraps

from django.utils import timezone

from .models import DataSyncAudit


SENSITIVE_KEY = re.compile(
    r"(^|[_\-.])(password|passwd|pwd|token|secret|authorization|credential|api[_-]?key)($|[_\-.])",
    re.IGNORECASE,
)
SENSITIVE_TEXT = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)((?:password|passwd|pwd|token|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+"),
)


def _safe_text(value):
    cleaned = str(value or "")
    for pattern in SENSITIVE_TEXT:
        cleaned = pattern.sub(lambda match: f"{match.group(1)}[ĐÃ ẨN]", cleaned)
    return cleaned


def _safe_value(value, key=None):
    if key is not None and SENSITIVE_KEY.search(str(key)):
        return "[ĐÃ ẨN]"
    if isinstance(value, dict):
        return {str(k): _safe_value(v, k) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value[:100]]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _safe_text(value)[:1000]


def safe_filename(value):
    return os.path.basename(str(value or "").replace("\\", "/"))[:255]


def uploaded_file_sha256(uploaded_file):
    if not uploaded_file:
        return ""
    digest = hashlib.sha256()
    position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else None
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    if position is not None:
        uploaded_file.seek(position)
    return digest.hexdigest()


def resolve_sync_plant(code):
    from tochuc.models import NhaMay

    aliases = {
        "songhinh": "SH",
        "vinhson": "VS",
        "thuongkontum": "TKT",
    }
    normalized = str(code or "").strip().replace("-", "").replace("_", "").lower()
    short_code = aliases.get(normalized, str(code or "").strip().upper())
    return NhaMay.objects.filter(ma_nha_may__iexact=short_code).first()


def data_date_bounds(rows, *keys):
    values = []
    for row in rows or []:
        raw = next((row.get(key) for key in keys if row.get(key)), None)
        if not raw:
            continue
        if isinstance(raw, datetime):
            values.append(raw.date())
        elif isinstance(raw, date):
            values.append(raw)
        else:
            try:
                values.append(date.fromisoformat(str(raw)[:10]))
            except ValueError:
                continue
    return (min(values), max(values)) if values else (None, None)


def record_data_sync(
    *, actor, nha_may, source, data_type, status, started_at,
    processed_count=0, created_count=0, updated_count=0,
    skipped_count=0, failed_count=0, filename="", checksum_sha256="",
    date_from=None, date_to=None, error_summary="", metadata=None,
):
    """Persist a compact, sanitized summary after a sync attempt."""
    return DataSyncAudit.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        nha_may=nha_may,
        source=source,
        data_type=str(data_type)[:64],
        status=status,
        filename=safe_filename(filename),
        checksum_sha256=str(checksum_sha256 or "")[:64],
        date_from=date_from,
        date_to=date_to,
        processed_count=max(int(processed_count or 0), 0),
        created_count=max(int(created_count or 0), 0),
        updated_count=max(int(updated_count or 0), 0),
        skipped_count=max(int(skipped_count or 0), 0),
        failed_count=max(int(failed_count or 0), 0),
        error_summary=_safe_text(error_summary)[:2000],
        metadata=_safe_value(metadata or {}),
        started_at=started_at,
        finished_at=timezone.now(),
    )


def audit_excel_import(data_type):
    """Record one compact audit row for an Excel import API attempt."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            request = next(
                (item for item in args if hasattr(item, "FILES") and hasattr(item, "user")),
                None,
            )
            started_at = timezone.now()
            uploaded_file = request.FILES.get("file") if request is not None else None
            checksum = uploaded_file_sha256(uploaded_file) if uploaded_file else ""

            try:
                response = view(*args, **kwargs)
            except Exception as exc:
                _record_excel_response(
                    request=request,
                    uploaded_file=uploaded_file,
                    checksum=checksum,
                    data_type=data_type,
                    started_at=started_at,
                    status_code=500,
                    payload={"error": str(exc)},
                )
                raise

            payload = getattr(response, "data", None)
            if payload is None and getattr(response, "content", None):
                try:
                    payload = json.loads(response.content.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = {}
            _record_excel_response(
                request=request,
                uploaded_file=uploaded_file,
                checksum=checksum,
                data_type=data_type,
                started_at=started_at,
                status_code=getattr(response, "status_code", 500),
                payload=payload if isinstance(payload, dict) else {},
            )
            return response

        return wrapped

    return decorator


def _record_excel_response(
    *, request, uploaded_file, checksum, data_type, started_at, status_code, payload,
):
    if (
        request is None
        or uploaded_file is None
        or not getattr(getattr(request, "user", None), "is_authenticated", False)
    ):
        return

    request_data = getattr(request, "data", None) or getattr(request, "POST", {})
    plant_code = (
        request_data.get("factory_code")
        or request_data.get("nha_may")
        or getattr(request, "query_params", {}).get("factory_code")
    )
    if not plant_code:
        try:
            from core.factory_scope import get_user_factory_code

            plant_code = get_user_factory_code(request.user)
        except (AttributeError, TypeError):
            plant_code = None

    imported = payload.get("imported_count", payload.get("success_count", 0)) or 0
    created = payload.get("created", 0) or 0
    updated = payload.get("updated", 0) or 0
    errors = payload.get("errors") or payload.get("details") or []
    failed = len(errors) if isinstance(errors, list) else int(status_code >= 400)
    sync_status = (
        DataSyncAudit.Status.PARTIAL
        if status_code == 207
        else DataSyncAudit.Status.SUCCESS
        if 200 <= status_code < 300
        else DataSyncAudit.Status.FAILED
    )
    date_value = request_data.get("import_date") or request_data.get("ngay")
    try:
        import_date = date.fromisoformat(str(date_value)[:10]) if date_value else None
    except ValueError:
        import_date = None

    record_data_sync(
        actor=request.user,
        nha_may=resolve_sync_plant(plant_code),
        source=DataSyncAudit.Source.EXCEL,
        data_type=data_type,
        status=sync_status,
        started_at=started_at,
        processed_count=max(int(imported), int(created) + int(updated)),
        created_count=created,
        updated_count=updated,
        failed_count=failed,
        filename=uploaded_file.name,
        checksum_sha256=checksum,
        date_from=import_date,
        date_to=import_date,
        error_summary=payload.get("error", ""),
        metadata={"http_status": status_code},
    )
