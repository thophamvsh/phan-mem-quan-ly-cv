import hashlib
import json
import logging
import uuid
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .rain_forecast_models import RainForecastFetch, RainForecastLocation, RainForecastLock, RainForecastRevision
from .rain_forecast_provider import ForecastError, fetch_forecast

logger = logging.getLogger(__name__)
VN = ZoneInfo("Asia/Ho_Chi_Minh")


def refresh_forecasts():
    if not getattr(settings, "RAIN_FORECAST_ENABLED", False):
        return {"status": "disabled"}
    token = str(uuid.uuid4())
    # Per-location leases bound individual HTTP calls, not an unbounded batch.
    results = {}
    for location in RainForecastLocation.objects.filter(enabled=True).order_by("code"):
        now = timezone.now()
        RainForecastLock.objects.get_or_create(name=location.code, defaults={"token": "", "expires_at": now})
        acquired = RainForecastLock.objects.filter(name=location.code, expires_at__lte=now).update(
            token=token, expires_at=now + timedelta(minutes=5))
        if not acquired:
            results[location.code] = "locked"
            continue
        attempt = RainForecastFetch.objects.create(location=location, started_at=now)
        try:
            data = fetch_forecast(location.latitude, location.longitude)
            today = timezone.now().astimezone(VN).date().isoformat()
            if data["daily"][0]["date"] != today or not any(row["precipitation"] is not None for row in data["daily"]):
                raise ForecastError("no_current_forecast")
            data["requested_latitude"] = float(location.latitude)
            data["requested_longitude"] = float(location.longitude)
            data["location_name"] = location.name
            digest = hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()
            with transaction.atomic():
                # Renew/check ownership before committing after a stalled worker.
                lease = RainForecastLock.objects.select_for_update().get(name=location.code)
                if lease.token != token or lease.expires_at <= timezone.now():
                    raise ForecastError("lease_expired")
                latest = location.revisions.order_by("-received_at", "-pk").first()
                if latest is None or latest.fingerprint != digest:
                    latest = RainForecastRevision.objects.create(location=location, received_at=timezone.now(), fingerprint=digest, data=data)
                attempt.revision = latest
                attempt.status = "success"
                attempt.finished_at = timezone.now()
                attempt.save(update_fields=["revision", "status", "finished_at"])
            results[location.code] = "success"
        except Exception as error:
            # Do not persist raw exceptions: HTTP URLs may contain credentials.
            attempt.status = "error"
            attempt.error_code = str(error) if isinstance(error, ForecastError) else "internal_error"
            attempt.finished_at = timezone.now()
            attempt.save(update_fields=["status", "error_code", "finished_at"])
            logger.warning("Rain forecast failed location=%s code=%s", location.code, attempt.error_code)
            results[location.code] = attempt.error_code
        finally:
            RainForecastLock.objects.filter(name=location.code, token=token).update(expires_at=timezone.now())
    return {"status": "success" if results and all(v == "success" for v in results.values()) else "partial", "locations": results}


def location_forecast(location, now=None):
    now = now or timezone.now()
    today = now.astimezone(VN).date()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(7)]
    latest_fetch = location.fetches.order_by("-started_at", "-pk").first()
    success = location.fetches.filter(status="success", revision__isnull=False).select_related("revision").order_by("-finished_at", "-pk").first()
    base = {"code": location.code, "label": location.name, "note": location.note,
            "scope": "point_forecast", "status": "unavailable", "fetched_at": None,
            "source_issued_at": None, "revision_id": None, "daily": []}
    stored = {}
    if success:
        revision = success.revision
        # Coordinate changes require a new fetch; never relabel old data as a new point.
        if (revision.data.get("requested_latitude"), revision.data.get("requested_longitude")) != (float(location.latitude), float(location.longitude)):
            success = None
        else:
            stored = {row["date"]: row for row in revision.data["daily"]}
            base.update(fetched_at=success.finished_at.isoformat(), revision_id=revision.pk,
                        revision_received_at=revision.received_at.isoformat(),
                        source_issued_at=revision.source_issued_at.isoformat() if revision.source_issued_at else None)
    for day in dates:
        row = stored.get(day, {})
        base["daily"].append({"date": day, "precipitation_mm": row.get("precipitation"),
                              "probability_max_pct": row.get("precipitation_probability"),
                              "weather_code": row.get("weather_code"), "quality_flags": row.get("quality_flags", ["missing_day"])})
    if success:
        coverage = sum(row["precipitation_mm"] is not None for row in base["daily"])
        stale = (now - success.finished_at).total_seconds() > getattr(settings, "RAIN_FORECAST_STALE_HOURS", 6) * 3600
        failed = latest_fetch is not None and latest_fetch.status == "error"
        # First receipt is not a model issue time, but bounds how long unchanged data is trusted.
        stale |= (now - success.revision.received_at).total_seconds() > 24 * 3600
        base["status"] = "unavailable" if not coverage else "stale" if stale or failed else "partial" if coverage < 7 else "fresh"
    return base


def chatbot_forecast(latitude, longitude, *, location_code=None):
    """Old tool return shape. Configured points use persisted forecasts when enabled.

    Legacy/unconfigured points retain bounded HTTP fetching with a shared cache;
    no simulated rain enters this path. Caller tool authorization stays unchanged.
    """
    if getattr(settings, "RAIN_FORECAST_ENABLED", False):
        locations = RainForecastLocation.objects.filter(enabled=True)
        location = locations.filter(code=location_code).first() if location_code else locations.filter(latitude=latitude, longitude=longitude).first()
        if location:
            summary = location_forecast(location)
            if summary["status"] in {"stale", "unavailable"}:
                raise ForecastError("forecast_unavailable_or_stale")
            revision = location.revisions.get(pk=summary["revision_id"])
            today = timezone.now().astimezone(VN).date().isoformat()
            return [row for row in revision.data["daily"] if row["date"] >= today]
    key = "rain-chat-v1:" + hashlib.sha256(f"{latitude}:{longitude}".encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    lock_key = key + ":lock"
    if not cache.add(lock_key, True, 30):
        raise ForecastError("forecast_busy")
    try:
        data = fetch_forecast(latitude, longitude, hourly=False)["daily"]
        cache.set(key, data, 900)
        return data
    finally:
        cache.delete(lock_key)
