"""Shared Open-Meteo adapter. No database access and no fabricated observations."""
import math
import random
import time
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import requests
from django.conf import settings

DAILY_FIELDS = (
    "precipitation_sum", "precipitation_probability_max", "weather_code",
    "temperature_2m_max", "temperature_2m_min",
)


class ForecastError(RuntimeError):
    """Safe error code; never include a request URL/key in its message."""


def _get_response(url, params):
    # At most three attempts. A large Retry-After is deferred to a later run.
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=(5, 15), allow_redirects=False)
        except requests.RequestException:
            if attempt == 2:
                raise
        else:
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                return response
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    delay = float(retry_after)
                except (ValueError, TypeError):
                    return response  # HTTP-date or unrecognized value: don't retry early.
                if not math.isfinite(delay) or delay < 0 or delay > 30:
                    return response
                time.sleep(delay)
                continue
        time.sleep(2 ** attempt + random.uniform(0, 0.5))


def number(value, minimum=None, maximum=None):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    if not math.isfinite(value) or (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        return None
    return value


def normalize_forecast(payload, require_hourly=False):
    if not isinstance(payload, dict):
        raise ForecastError("invalid_payload")
    if payload.get("utc_offset_seconds", 25200) != 25200:
        raise ForecastError("invalid_timezone")
    daily = payload.get("daily") or {}
    times = daily.get("time")
    if not isinstance(times, list) or not times or len(times) > 7:
        raise ForecastError("invalid_daily_times")
    units = payload.get("daily_units") or {}
    if units.get("precipitation_sum", "mm") != "mm":
        raise ForecastError("invalid_unit")
    fields = {
        "precipitation": ("precipitation_sum", 0, None),
        "precipitation_probability": ("precipitation_probability_max", 0, 100),
        "weather_code": ("weather_code", 0, 99),
        "temperature_max": ("temperature_2m_max", None, None),
        "temperature_min": ("temperature_2m_min", None, None),
    }
    rows = []
    previous = None
    for i, day in enumerate(times):
        try:
            parsed = date.fromisoformat(day)
        except (TypeError, ValueError):
            raise ForecastError("invalid_daily_date") from None
        if previous is not None and parsed != previous + timedelta(days=1):
            raise ForecastError("non_contiguous_days")
        previous = parsed
        row = {"date": day}
        for target, (source, low, high) in fields.items():
            values = daily.get(source) or []
            if not isinstance(values, list):
                raise ForecastError("invalid_daily_array")
            row[target] = number(values[i], low, high) if i < len(values) else None
        row["quality_flags"] = ["missing_precipitation"] if row["precipitation"] is None else []
        rows.append(row)
    hourly = payload.get("hourly") or {}
    hours = hourly.get("time") or []
    rain = hourly.get("precipitation") or []
    if not isinstance(hours, list) or not isinstance(rain, list) or len(hours) != len(rain) or len(hours) > 168:
        raise ForecastError("invalid_hourly_array")
    if (payload.get("hourly_units") or {}).get("precipitation", "mm") != "mm":
        raise ForecastError("invalid_unit")
    hour_rows = []
    previous = None
    for stamp, value in zip(hours, rain):
        try:
            end = datetime.fromisoformat(stamp)
            if end.tzinfo is not None or end.minute or end.second:
                raise ValueError()
        except (ValueError, TypeError):
            raise ForecastError("invalid_hourly_time") from None
        if previous is not None and end != previous + timedelta(hours=1):
            raise ForecastError("non_contiguous_hours")
        previous = end
        # Open-Meteo precipitation is accumulated over the preceding hour.
        hour_rows.append({
            "valid_start": (end - timedelta(hours=1)).isoformat() + "+07:00",
            "valid_end": end.isoformat() + "+07:00",
            "precipitation": number(value, 0),
        })
    if require_hourly and not hour_rows:
        raise ForecastError("missing_hourly")
    return {"daily": rows, "hourly": hour_rows, "grid_latitude": number(payload.get("latitude")),
            "grid_longitude": number(payload.get("longitude")), "timezone": "Asia/Ho_Chi_Minh",
            "model": "best_match", "parser_version": "open-meteo-v1", "source_issued_at": None}


def fetch_forecast(latitude, longitude, *, hourly=True):
    lat, lon = number(latitude, -90, 90), number(longitude, -180, 180)
    if lat is None or lon is None:
        raise ForecastError("invalid_coordinates")
    url = getattr(settings, "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")
    parsed = urlparse(url)
    allowed = parsed.scheme == "https" and parsed.hostname in {"api.open-meteo.com", "customer-api.open-meteo.com"}
    local_test = getattr(settings, "RAIN_FORECAST_ALLOW_LOCAL_TEST", False) and parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
    if not (allowed or local_test) or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ForecastError("invalid_provider_url")
    params = {"latitude": lat, "longitude": lon, "daily": ",".join(DAILY_FIELDS),
              "forecast_days": 7, "timezone": "Asia/Ho_Chi_Minh"}
    if hourly:
        params["hourly"] = "precipitation"
    key = getattr(settings, "OPEN_METEO_API_KEY", "")
    if key:
        params["apikey"] = key
    try:
        response = _get_response(url, params)
        response.raise_for_status()
        if response.status_code != 200:
            raise ForecastError("unexpected_status")
        return normalize_forecast(response.json(), require_hourly=hourly)
    except requests.HTTPError as error:
        code = error.response.status_code if error.response is not None else 0
        raise ForecastError(f"http_{code}") from None
    except requests.RequestException:
        raise ForecastError("connection_failed") from None
    except (ValueError, TypeError, AttributeError):
        raise ForecastError("invalid_payload") from None
