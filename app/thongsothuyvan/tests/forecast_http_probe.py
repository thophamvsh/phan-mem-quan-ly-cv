"""Run with python -m thongsothuyvan.tests.forecast_http_probe against local simulation.

No Django database, real credentials or production environment are read.
"""
import sys
from django.conf import settings

settings.configure(OPEN_METEO_BASE_URL="http://127.0.0.1:4910/weather/v1/forecast",
                   OPEN_METEO_API_KEY="", RAIN_FORECAST_ALLOW_LOCAL_TEST=True)
from thongsothuyvan.rain_forecast_provider import fetch_forecast, ForecastError

data = fetch_forecast(12.92684, 108.946392)
assert len(data["daily"]) == 7 and len(data["hourly"]) == 168
assert data["daily"][0]["precipitation"] == 0
assert data["daily"][2]["precipitation"] is None
print("PASS real HTTP: normalized 7 days / 168 hours / zero and missing")
for lat, code in [(0, "http_500"), (1, "http_429"), (2, "http_401"), (3, "connection_failed")]:
    try:
        fetch_forecast(lat, 108)
    except ForecastError as error:
        assert str(error) == code, str(error)
        print("PASS real HTTP:", code)
    else:
        sys.exit("Expected upstream failure")
settings.OPEN_METEO_BASE_URL = "http://127.0.0.1:1/v1/forecast"
try:
    fetch_forecast(12, 108)
except ForecastError as error:
    assert str(error) == "connection_failed"
    print("PASS real HTTP: refused connection")
else:
    sys.exit("Expected refused connection")
