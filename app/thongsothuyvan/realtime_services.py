import base64
import json
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    RealtimeUpdateState,
    SongHinhRealtimeSnapshot,
    SonghinhMnh,
    VinhSonRealtimeSnapshot,
    Vinhson_HoA,
    Vinhson_HoB,
    Vinhson_Hoc,
)

SONG_HINH_FLOOD_CAPACITY = 323.533

SONGHINH_REQUIRED_FIELDS = [
    "time_stamp",
    "MNTL",
    "MNHL",
    "PH1",
    "PH2",
    "PNM",
    "Qcm",
    "DM1",
    "DM2",
    "DM3",
    "DM4",
    "DM5",
    "DM6",
    "Qtran",
]

VINHSON_REQUIRED_FIELDS = [
    "time_stamp",
    "MNTLA",
    "MNTLB",
    "MNTLC",
    "MNHL",
    "PH1",
    "PH2",
    "Qcm",
    "Qtran",
]


@dataclass
class RealtimeSaveResult:
    plant: str
    saved: bool
    snapshot_id: int | None = None
    error: str = ""
    skipped: bool = False


def get_env_value(name):
    value = os.environ.get(name)
    if value:
        return value

    env_path = os.path.join(settings.BASE_DIR.parent, ".env")
    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, raw_value = line.split("=", 1)
            if key.strip() == name:
                return raw_value.strip().strip('"').strip("'")

    return None


def parse_realtime_timestamp(value):
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def get_capacity_by_level(model_class, mucnuoc):
    try:
        level = Decimal(str(mucnuoc))
    except (InvalidOperation, TypeError, ValueError):
        return None

    lower = (
        model_class.objects.filter(Mucnuoc__lte=level)
        .order_by("-Mucnuoc")
        .first()
    )
    upper = (
        model_class.objects.filter(Mucnuoc__gte=level)
        .order_by("Mucnuoc")
        .first()
    )

    if not lower and not upper:
        return None
    if lower and not upper:
        return float(lower.dungtich)
    if upper and not lower:
        return float(upper.dungtich)

    lower_level = lower.Mucnuoc
    upper_level = upper.Mucnuoc
    if lower_level == upper_level:
        return float(lower.dungtich)

    ratio = (level - lower_level) / (upper_level - lower_level)
    capacity = lower.dungtich + ratio * (upper.dungtich - lower.dungtich)
    return float(capacity)


def fetch_realtime_payload(prefix):
    realtime_url = get_env_value(f"{prefix}_URL")
    realtime_user = get_env_value(f"{prefix}_USER") or ""
    realtime_pass = get_env_value(f"{prefix}_PASS") or ""

    if not realtime_url:
        raise ValueError(f"Chua cau hinh {prefix}_URL trong .env backend.")

    headers = {"Accept": "application/json"}
    if realtime_user or realtime_pass:
        token = base64.b64encode(
            f"{realtime_user}:{realtime_pass}".encode("ascii")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {token}"

    try:
        upstream_request = Request(realtime_url, headers=headers, method="GET")
        with urlopen(upstream_request, timeout=15) as upstream_response:
            charset = upstream_response.headers.get_content_charset() or "utf-8"
            payload = upstream_response.read().decode(charset)
            return json.loads(payload)
    except HTTPError as exc:
        raise ValueError(f"Realtime API tra ve loi {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        raise ValueError(f"Khong ket noi duoc realtime API: {exc}") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Realtime API khong tra ve JSON hop le.") from exc


def enrich_songhinh_payload(payload_data):
    capacity = get_capacity_by_level(SonghinhMnh, payload_data.get("MNTL"))
    payload_data["dung_tich_ho"] = (
        round(capacity, 3) if capacity is not None else None
    )
    payload_data["dung_tich_phong_lu"] = (
        round(SONG_HINH_FLOOD_CAPACITY - capacity, 3)
        if capacity is not None
        else None
    )
    return payload_data


def enrich_vinhson_payload(payload_data):
    capacity_ho_a = get_capacity_by_level(Vinhson_HoA, payload_data.get("MNTLA"))
    capacity_ho_b = get_capacity_by_level(Vinhson_HoB, payload_data.get("MNTLB"))
    capacity_ho_c = get_capacity_by_level(Vinhson_Hoc, payload_data.get("MNTLC"))
    payload_data["dung_tich_ho_a"] = (
        round(capacity_ho_a, 3) if capacity_ho_a is not None else None
    )
    payload_data["dung_tich_ho_b"] = (
        round(capacity_ho_b, 3) if capacity_ho_b is not None else None
    )
    payload_data["dung_tich_ho_c"] = (
        round(capacity_ho_c, 3) if capacity_ho_c is not None else None
    )
    return payload_data


def validate_required_fields(payload_data, required_fields, plant_name):
    data_fields = [field for field in required_fields if field != "time_stamp"]
    if data_fields and all(
        payload_data.get(field) is None or payload_data.get(field) == ""
        for field in data_fields
    ):
        raise ValueError(f"{plant_name}: du lieu realtime rong, khong luu.")

    missing_fields = [
        field
        for field in required_fields
        if payload_data.get(field) is None or payload_data.get(field) == ""
    ]
    if missing_fields:
        raise ValueError(
            f"{plant_name}: du lieu null, khong luu. Field loi: {', '.join(missing_fields)}"
        )


def save_songhinh_realtime_snapshot():
    payload_data = enrich_songhinh_payload(fetch_realtime_payload("SONGHINH"))
    validate_required_fields(payload_data, SONGHINH_REQUIRED_FIELDS, "Song Hinh")
    snapshot = SongHinhRealtimeSnapshot.objects.create(
        time_stamp=parse_realtime_timestamp(payload_data["time_stamp"]),
        mntl=payload_data["MNTL"],
        mnhl=payload_data["MNHL"],
        ph1=payload_data["PH1"],
        ph2=payload_data["PH2"],
        pnm=payload_data["PNM"],
        qcm=payload_data["Qcm"],
        dm1=payload_data["DM1"],
        dm2=payload_data["DM2"],
        dm3=payload_data["DM3"],
        dm4=payload_data["DM4"],
        dm5=payload_data["DM5"],
        dm6=payload_data["DM6"],
        qtran=payload_data["Qtran"],
        dung_tich_ho=payload_data["dung_tich_ho"],
        dung_tich_phong_lu=payload_data["dung_tich_phong_lu"],
        raw_data=payload_data,
    )
    return RealtimeSaveResult("songhinh", True, snapshot_id=snapshot.id)


def save_vinhson_realtime_snapshot():
    payload_data = enrich_vinhson_payload(fetch_realtime_payload("VINHSON"))
    validate_required_fields(payload_data, VINHSON_REQUIRED_FIELDS, "Vinh Son")
    snapshot = VinhSonRealtimeSnapshot.objects.create(
        time_stamp=parse_realtime_timestamp(payload_data["time_stamp"]),
        mntla=payload_data["MNTLA"],
        mntla_td=payload_data.get("MNTLA_td"),
        mntlb=payload_data["MNTLB"],
        mntlc=payload_data["MNTLC"],
        mnhl=payload_data["MNHL"],
        ph1=payload_data["PH1"],
        ph2=payload_data["PH2"],
        qcm=payload_data["Qcm"],
        qtran=payload_data["Qtran"],
        dung_tich_ho_a=payload_data["dung_tich_ho_a"],
        dung_tich_ho_b=payload_data["dung_tich_ho_b"],
        dung_tich_ho_c=payload_data["dung_tich_ho_c"],
        raw_data=payload_data,
    )
    return RealtimeSaveResult("vinhson", True, snapshot_id=snapshot.id)


def claim_realtime_snapshot_run(interval_seconds=3600):
    now = timezone.now()

    with transaction.atomic():
        state, _ = RealtimeUpdateState.objects.select_for_update().get_or_create(pk=1)
        if (
            state.last_run_at
            and (now - state.last_run_at).total_seconds() < interval_seconds
        ):
            return False

        state.last_run_at = now
        state.save(update_fields=["last_run_at", "updated_at"])
        return True


def claim_realtime_snapshot_hourly_slot(grace_minutes=5):
    now = timezone.localtime(timezone.now())
    if now.minute > grace_minutes:
        return False

    current_slot = now.replace(minute=0, second=0, microsecond=0)

    with transaction.atomic():
        state, _ = RealtimeUpdateState.objects.select_for_update().get_or_create(pk=1)
        last_hourly_slot = (
            timezone.localtime(state.last_hourly_slot).replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            if state.last_hourly_slot
            else None
        )

        if last_hourly_slot == current_slot:
            return False

        state.last_run_at = timezone.now()
        state.last_hourly_slot = current_slot
        state.save(update_fields=["last_run_at", "last_hourly_slot", "updated_at"])
        return True


def save_all_realtime_snapshots(is_manual=False, mark_run=True, plants=None):
    state = RealtimeUpdateState.get_solo()
    now = timezone.now()
    if mark_run:
        state.last_run_at = now
    if is_manual:
        state.last_manual_run_at = now

    results = []
    errors = []
    save_funcs = {
        "songhinh": save_songhinh_realtime_snapshot,
        "vinhson": save_vinhson_realtime_snapshot,
    }
    selected_plants = list(save_funcs.keys()) if not plants else plants

    for plant in selected_plants:
        save_func = save_funcs.get(plant)
        if not save_func:
            error = f"Nha may realtime khong hop le: {plant}"
            errors.append(error)
            results.append(RealtimeSaveResult(plant, False, error=error))
            continue

        try:
            results.append(save_func())
        except Exception as exc:
            error = str(exc)
            errors.append(error)
            results.append(
                RealtimeSaveResult(
                    plant,
                    False,
                    error=error,
                )
            )

    if errors:
        state.last_error = " | ".join(errors)
        state.last_error_at = now
    else:
        state.last_error = ""
        state.last_error_at = None
        state.last_saved_at = now

    state.save()
    return state, results


def normalize_realtime_error(error):
    error = error or ""
    obsolete_errors = [
        "Vinh Son: du lieu null, khong luu. Field loi: MNTLA_td",
    ]

    if error.strip() in obsolete_errors:
        return ""

    return error


def clear_obsolete_realtime_error(state):
    if state.last_error and not normalize_realtime_error(state.last_error):
        state.last_error = ""
        state.last_error_at = None
        state.save(update_fields=["last_error", "last_error_at", "updated_at"])


def serialize_realtime_state(state=None):
    state = state or RealtimeUpdateState.get_solo()
    clear_obsolete_realtime_error(state)
    return {
        "auto_update_enabled": state.auto_update_enabled,
        "last_run_at": state.last_run_at,
        "last_hourly_slot": state.last_hourly_slot,
        "last_saved_at": state.last_saved_at,
        "last_manual_run_at": state.last_manual_run_at,
        "last_error": normalize_realtime_error(state.last_error),
        "last_error_at": state.last_error_at,
        "updated_at": state.updated_at,
    }
