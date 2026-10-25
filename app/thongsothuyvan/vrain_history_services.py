import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .vrain_history_models import (VrainStation, VrainSyncRun, VrainSourceSample, VrainRainfallRevision, VrainRainfallInterval, VrainSyncLease, VrainBackfillJob)
from .vrain_history_provider import VN, VrainHistoryError, fetch_history, fingerprint, parse_timestamp, rainfall

TEN = timedelta(minutes=10)


def contract_verified():
    return bool(getattr(settings, "VRAIN_INTERVAL_CONTRACT_VERIFIED", False))


def aligned(value):
    return timezone.is_aware(value) and value.minute % 10 == 0 and value.second == 0 and value.microsecond == 0


def validate_window(start, end):
    if not aligned(start) or not aligned(end) or not start < end or end - start > timedelta(hours=1) or end > timezone.now():
        raise VrainHistoryError("invalid_window")


def ingest(run, payload, received_at):
    counts = {"samples": 0, "created": 0, "revised": 0, "missing": 0, "rejected": 0, "outside_window": 0}
    stations = {s.source_station_code: s for s in VrainStation.objects.filter(enabled=True)}
    grouped = {}
    for row in payload["Data"]:
        station = stations.get(row["station_id"])
        if station is None:
            continue
        for data in row["value"]:
            try:
                stamp = parse_timestamp(data["time_point"])
            except VrainHistoryError:
                counts["rejected"] += 1
                continue
            # Evidence keeps outside-window samples, normalized records never do.
            if not run.window_start <= stamp <= run.window_end:
                counts["outside_window"] += 1
                continue
            key = (station.pk, stamp)
            if key in grouped and grouped[key] != data:
                raise VrainHistoryError("conflicting_duplicate")
            grouped[key] = data
    for (station_id, stamp), data in grouped.items():
        counts["samples"] += 1
        digest = fingerprint(data)
        sample, created = VrainSourceSample.objects.get_or_create(station_id=station_id, source_timestamp=stamp, defaults={"first_received_at": received_at, "last_received_at": received_at, "fingerprint": digest, "data": data})
        revision = None
        if created or sample.fingerprint != digest:
            revision = VrainRainfallRevision.objects.create(sample=sample, run=run, received_at=received_at, data=data, fingerprint=digest)
            counts["created" if created else "revised"] += 1
        else:
            revision = sample.revisions.order_by("-received_at", "-pk").first()
        sample.last_received_at = received_at
        sample.data, sample.fingerprint = data, digest
        sample.save(update_fields=["last_received_at", "data", "fingerprint"])
        if run.contract_verified and run.window_start < stamp <= run.window_end:
            if not aligned(stamp):
                counts["rejected"] += 1
                continue
            value = rainfall(data["depth"])
            VrainRainfallInterval.objects.update_or_create(station_id=station_id, interval_start=stamp - TEN, interval_end=stamp, defaults={"rainfall_mm": value, "status": "valid" if value is not None else "invalid", "quality_flags": [] if value is not None else ["invalid_depth"], "revision": revision})
    if run.contract_verified:
        for station in stations.values():
            stamp = run.window_start + TEN
            while stamp <= run.window_end:
                interval, created = VrainRainfallInterval.objects.get_or_create(station=station, interval_start=stamp - TEN, interval_end=stamp, defaults={"rainfall_mm": None, "status": "missing", "quality_flags": ["missing_sample"]})
                counts["missing"] += int(interval.status != "valid")
                stamp += TEN
    return counts


def sync_history(start=None, end=None, *, manual=False):
    if not manual and not getattr(settings, "VRAIN_HISTORY_ENABLED", False):
        return {"status": "disabled"}
    if end is None:
        end = timezone.now().astimezone(VN) - timedelta(minutes=2)
        end = end.replace(minute=end.minute // 10 * 10, second=0, microsecond=0)
    start = start or end - timedelta(hours=1)
    validate_window(start, end)
    token, now = str(uuid.uuid4()), timezone.now()
    VrainSyncLease.objects.get_or_create(name="history", defaults={"token": "", "expires_at": now})
    if not VrainSyncLease.objects.filter(name="history", expires_at__lte=now).update(token=token, expires_at=now + timedelta(minutes=5)):
        return {"status": "locked"}
    run = None
    try:
        run = VrainSyncRun.objects.create(window_start=start, window_end=end, contract_verified=contract_verified())
        payload = fetch_history(start, end)
        run.evidence, run.payload_hash = payload, fingerprint(payload)
        # Preserve safe evidence even if the normalized transaction fails.
        run.save(update_fields=["evidence", "payload_hash"])
        with transaction.atomic():
            lease = VrainSyncLease.objects.select_for_update().get(name="history")
            if lease.token != token or lease.expires_at <= timezone.now():
                raise VrainHistoryError("lease_expired")
            run.counts = ingest(run, payload, timezone.now())
            run.status = ("partial" if run.counts["missing"] or run.counts["rejected"] else "success") if run.contract_verified else "captured_unverified"
            if not run.counts["samples"]:
                run.status = "no_data"
            run.finished_at = timezone.now()
            run.save(update_fields=["counts", "status", "finished_at"])
        return {"status": run.status, "run_id": run.pk, "counts": run.counts}
    except Exception as error:
        code = str(error) if isinstance(error, VrainHistoryError) else "internal_error"
        if run:
            run.status, run.error_code, run.finished_at = "error", code, timezone.now()
            run.save(update_fields=["status", "error_code", "finished_at"])
        return {"status": "error", "error_code": code, "run_id": run.pk if run else None}
    finally:
        VrainSyncLease.objects.filter(name="history", token=token).update(expires_at=timezone.now())


def source_as_of(station, timestamp, known_at):
    """Reconstruct the version actually known at T, not the latest corrected value."""
    return VrainRainfallRevision.objects.filter(sample__station=station, sample__source_timestamp=timestamp, received_at__lte=known_at).order_by("-received_at", "-pk").first()


def advance_backfill(job):
    # A per-job row lock prevents two workers advancing the same cursor.
    with transaction.atomic():
        job = VrainBackfillJob.objects.select_for_update().get(pk=job.pk)
        if job.cursor >= job.window_end:
            job.status = "done"
            job.save(update_fields=["status"])
            return {"status": "done"}
        end = min(job.cursor + timedelta(hours=1), job.window_end)
        result = sync_history(job.cursor, end, manual=True)
        if result.get("run_id"):
            job.last_run_id = result["run_id"]
        if result["status"] in {"success", "captured_unverified"}:
            job.cursor = end
            job.status = "done" if end == job.window_end else "pending"
        else:
            job.status = "blocked"
        job.save(update_fields=["cursor", "status", "last_run"])
        return result
