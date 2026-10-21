"""Estimated water balance. Volumes: million m³; flows: m³/s."""
import math


def finite(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def calculate_inflow(start, end, volumes_start, volumes_end,
                     qcm_start, qcm_end, spill_start, spill_end):
    meta = {
        "method": "water_balance_endpoint_average_v1",
        "unit": "m3/s",
        "start": start.isoformat() if start else None,
        "end": end.isoformat(),
        "status": "no_previous_sample",
    }
    if start is None:
        return None, meta
    seconds = (end - start).total_seconds()
    meta["interval_seconds"] = seconds
    if seconds <= 0:
        meta["status"] = "non_increasing_timestamp"
        return None, meta
    values = [finite(v) for v in (
        *volumes_start, *volumes_end, qcm_start, qcm_end, spill_start, spill_end
    )]
    if (not volumes_start or len(volumes_start) != len(volumes_end)
            or any(v is None for v in values)):
        meta["status"] = "missing_or_invalid_input"
        return None, meta
    n = len(volumes_start)
    if any(v < 0 for v in values):
        meta["status"] = "negative_input"
        return None, meta
    delta = (sum(values[n:2*n]) - sum(values[:n])) * 1_000_000
    qcm = (values[-4] + values[-3]) / 2
    spill = (values[-2] + values[-1]) / 2
    result = delta / seconds + qcm + spill
    meta.update(
        status="estimated", delta_volume_m3=delta,
        qcm_average=qcm, spill_average=spill,
        volumes_start_million_m3=values[:n],
        volumes_end_million_m3=values[n:2*n],
        longer_than_30_minutes=seconds > 1800,
        negative_result=result < 0,
    )
    return result, meta
