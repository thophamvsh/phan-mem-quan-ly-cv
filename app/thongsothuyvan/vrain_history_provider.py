"""VRAIN transport and allowlisting, without inferring interval semantics."""
import hashlib
import json
import math
import random
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from .vrain_credentials import _get_api_key

VN = ZoneInfo("Asia/Ho_Chi_Minh")


class VrainHistoryError(RuntimeError):
    """Safe fixed error code, never a response body or URL."""


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def parse_timestamp(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=VN)
    except (TypeError, ValueError):
        raise VrainHistoryError("invalid_timestamp") from None


def rainfall(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal("99999999") or result.as_tuple().exponent < -4:
            return None
        return result
    except (InvalidOperation, ValueError, TypeError):
        return None


def sanitize(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("Data"), list):
        raise VrainHistoryError("invalid_payload")
    if len(payload["Data"]) > 1000:
        raise VrainHistoryError("payload_too_large")
    result = []
    total = 0
    for row in payload["Data"]:
        if not isinstance(row, dict) or not isinstance(row.get("station_id"), str) or not row["station_id"].isdigit():
            raise VrainHistoryError("invalid_station")
        values = row.get("value")
        if not isinstance(values, list):
            raise VrainHistoryError("invalid_samples")
        total += len(values)
        if total > 20000:
            raise VrainHistoryError("payload_too_large")
        samples = []
        for item in values:
            if not isinstance(item, dict):
                raise VrainHistoryError("invalid_sample")
            stamp, depth = item.get("time_point"), item.get("depth")
            # Only known measurement fields are retained. Other content may contain PII/secrets.
            if not isinstance(stamp, str) or len(stamp) > 40:
                stamp = None
            if not isinstance(depth, (str, int, float, type(None))) or isinstance(depth, bool):
                depth = None
            if isinstance(depth, float) and not math.isfinite(depth):
                depth = None
            if isinstance(depth, str):
                # Retain numeric strings only, never arbitrary text from upstream.
                try:
                    Decimal(depth)
                except InvalidOperation:
                    depth = None
                if depth is not None and len(depth) > 40:
                    depth = None
            samples.append({"time_point": stamp, "depth": depth})
        result.append({"station_id": row["station_id"], "value": samples})
    return {"Data": result}


def fetch_history(start, end):
    url = getattr(settings, "VRAIN_HISTORY_BASE_URL", "https://kttv-open.vrain.vn/v1/stations/stats")
    parsed = urlparse(url)
    allowed = parsed.scheme == "https" and parsed.hostname == "kttv-open.vrain.vn" and parsed.path == "/v1/stations/stats"
    local = getattr(settings, "VRAIN_HISTORY_ALLOW_LOCAL_TEST", False) and parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
    if not (allowed or local) or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise VrainHistoryError("invalid_provider_url")
    try:
        key = _get_api_key()
    except Exception:
        raise VrainHistoryError("missing_credentials") from None
    for attempt in range(3):
        try:
            response = requests.get(url, params={"start_time": start.astimezone(VN).strftime("%Y-%m-%d %H:%M:%S"), "end_time": end.astimezone(VN).strftime("%Y-%m-%d %H:%M:%S")}, headers={"x-api-key": key}, timeout=(5, getattr(settings, "VRAIN_HISTORY_HTTP_TIMEOUT", 20)), allow_redirects=False)
        except requests.RequestException:
            if attempt == 2:
                raise VrainHistoryError("connection_failed") from None
        else:
            if response.status_code == 200:
                try:
                    return sanitize(response.json())
                except (ValueError, TypeError):
                    raise VrainHistoryError("invalid_payload") from None
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise VrainHistoryError(f"http_{response.status_code}")
            retry = response.headers.get("Retry-After")
            if retry is not None:
                try:
                    delay = float(retry)
                    if not math.isfinite(delay) or not 0 <= delay <= 30:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise VrainHistoryError("retry_deferred") from None
                time.sleep(delay)
                continue
        time.sleep(2 ** attempt + random.uniform(0, .5))
