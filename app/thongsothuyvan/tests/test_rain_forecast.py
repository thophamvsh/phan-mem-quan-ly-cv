from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from thongsothuyvan.rain_forecast_models import RainForecastFetch, RainForecastLocation, RainForecastLock, RainForecastRevision
from thongsothuyvan.rain_forecast_provider import ForecastError, normalize_forecast, fetch_forecast, _get_response
from thongsothuyvan.rain_forecast_services import VN, chatbot_forecast, location_forecast, refresh_forecasts
from thongsothuyvan.rain_forecast_views import RainForecastAPIView


def payload():
    today = timezone.now().astimezone(VN).date()
    dates = [(today + timedelta(days=i)).isoformat() for i in range(7)]
    return {"utc_offset_seconds": 25200, "daily_units": {"precipitation_sum": "mm"},
            "latitude": 12.92684, "longitude": 108.946392,
            "daily": {"time": dates, "precipitation_sum": [0, 1, 2, 3, 4, 5, 6],
                      "precipitation_probability_max": [0, 50, 60, 70, 80, 90, 100]},
            "hourly": {"time": [dates[0] + "T01:00"], "precipitation": [0]}}


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class ForecastProviderTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_null_zero_partial_and_hour_interval(self):
        value = payload()
        value["daily"]["precipitation_sum"] = [0, None, -1, float("nan")]
        result = normalize_forecast(value, True)
        self.assertEqual(result["daily"][0]["precipitation"], 0)
        self.assertEqual([r["precipitation"] for r in result["daily"]][1:], [None] * 6)
        self.assertTrue(result["hourly"][0]["valid_start"].endswith("T00:00:00+07:00"))

    def test_bad_unit_dates_timezone_and_hour_lengths(self):
        for change in [
            lambda p: p.update(utc_offset_seconds=0),
            lambda p: p["daily_units"].update(precipitation_sum="inch"),
            lambda p: p["daily"].update(time=["invalid"]),
            lambda p: p["hourly"].update(precipitation=[]),
        ]:
            value = payload()
            change(value)
            with self.assertRaises(ForecastError):
                normalize_forecast(value, True)

    @patch("thongsothuyvan.rain_forecast_provider.time.sleep")
    @patch("thongsothuyvan.rain_forecast_provider.requests.get")
    def test_bounded_retry_and_retry_after(self, get, sleep):
        get.side_effect = [Mock(status_code=429, headers={"Retry-After": "2"}), Mock(status_code=200)]
        self.assertEqual(_get_response("http://test", {}).status_code, 200)
        sleep.assert_called_once_with(2)
        get.reset_mock()
        get.side_effect = None
        get.return_value = Mock(status_code=429, headers={"Retry-After": "120"})
        self.assertEqual(_get_response("http://test", {}).status_code, 429)
        get.assert_called_once()
        get.reset_mock()
        get.return_value = Mock(status_code=401)
        self.assertEqual(_get_response("http://test", {}).status_code, 401)
        get.assert_called_once()

    @override_settings(OPEN_METEO_BASE_URL="https://evil.example/v1/forecast")
    def test_untrusted_host_never_called(self):
        with patch("thongsothuyvan.rain_forecast_provider.requests.get") as get:
            with self.assertRaises(ForecastError):
                fetch_forecast(1, 2)
            get.assert_not_called()

    @override_settings(RAIN_FORECAST_ENABLED=False)
    def test_chatbot_cache_and_missing_water_rain(self):
        from ai_tools.water_tools.weather_service import get_rainfall_forecast
        value = payload()
        value["daily"]["precipitation_sum"][1] = None
        with patch("thongsothuyvan.rain_forecast_services.fetch_forecast", return_value=normalize_forecast(value)) as fetch:
            result = get_rainfall_forecast(1, 2)
            get_rainfall_forecast(1, 2)
            fetch.assert_called_once()
            self.assertEqual(result[value["daily"]["time"][0]], 0)
            self.assertNotIn(value["daily"]["time"][1], result)


@override_settings(RAIN_FORECAST_ENABLED=True)
class ForecastDatabaseTests(TestCase):
    def setUp(self):
        RainForecastLocation.objects.update(enabled=False)
        self.location = RainForecastLocation.objects.create(code="test_sh", plant="songhinh", name="Test SH", latitude=12.92684, longitude=108.946392)
        self.normalized = normalize_forecast(payload(), True)

    def refresh(self):
        with patch("thongsothuyvan.rain_forecast_services.fetch_forecast", return_value=self.normalized):
            return refresh_forecasts()

    def test_revision_reuse_change_and_stale_on_failure(self):
        self.assertEqual(self.refresh()["status"], "success")
        self.refresh()
        self.assertEqual(RainForecastRevision.objects.count(), 1)
        self.assertEqual(RainForecastFetch.objects.count(), 2)
        self.assertEqual(location_forecast(self.location)["status"], "fresh")
        self.normalized["daily"][0]["precipitation"] = 10
        self.refresh()
        self.assertEqual(RainForecastRevision.objects.count(), 2)
        with patch("thongsothuyvan.rain_forecast_services.fetch_forecast", side_effect=ForecastError("connection_failed")):
            self.assertEqual(refresh_forecasts()["status"], "partial")
        result = location_forecast(self.location)
        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["daily"][0]["precipitation_mm"], 10)
        with self.assertRaises(ForecastError):
            chatbot_forecast(float(self.location.latitude), float(self.location.longitude))

    def test_disabled_and_locked_do_not_fetch(self):
        with override_settings(RAIN_FORECAST_ENABLED=False), patch("thongsothuyvan.rain_forecast_services.fetch_forecast") as fetch:
            self.assertEqual(refresh_forecasts()["status"], "disabled")
            fetch.assert_not_called()
        RainForecastLock.objects.create(name=self.location.code, token="other", expires_at=timezone.now() + timedelta(minutes=5))
        with patch("thongsothuyvan.rain_forecast_services.fetch_forecast") as fetch:
            self.assertEqual(refresh_forecasts()["locations"][self.location.code], "locked")
            fetch.assert_not_called()

    def test_chatbot_uses_same_revision_no_network_and_coordinate_edit_invalidates(self):
        self.refresh()
        with patch("thongsothuyvan.rain_forecast_services.fetch_forecast") as fetch:
            rows = chatbot_forecast(12.92684, 108.946392)
            self.assertEqual(rows[0]["precipitation"], location_forecast(self.location)["daily"][0]["precipitation_mm"])
            fetch.assert_not_called()
        self.location.latitude = 13
        self.location.save()
        self.assertEqual(location_forecast(self.location)["status"], "unavailable")

    def test_api_auth_scope_and_disabled(self):
        factory = APIRequestFactory()
        view = RainForecastAPIView.as_view()
        self.assertIn(view(factory.get("/?plant=songhinh")).status_code, [401, 403])
        user = SimpleNamespace(is_authenticated=True, is_superuser=False,
                               profile=SimpleNamespace(can_view_realtime_hydrology=True, is_all_factories=False,
                                                       nha_may=SimpleNamespace(ma_nha_may="SH")))
        for plant, expected in [("invalid", 400), ("vinhson", 403), ("songhinh", 200)]:
            req = factory.get("/", {"plant": plant})
            force_authenticate(req, user=user)
            with patch("thongsothuyvan.rain_forecast_services.fetch_forecast") as fetch:
                response = view(req)
                self.assertEqual(response.status_code, expected)
                fetch.assert_not_called()
        req = factory.get("/?plant=songhinh")
        force_authenticate(req, user=user)
        with override_settings(RAIN_FORECAST_ENABLED=False):
            self.assertEqual(view(req).data["locations"], [])

    def test_midnight_dates_and_stale_age(self):
        self.refresh()
        tomorrow = timezone.now() + timedelta(days=1)
        result = location_forecast(self.location, tomorrow)
        self.assertEqual(result["status"], "stale")
        self.assertIsNone(result["daily"][-1]["precipitation_mm"])

    def test_lost_lease_cannot_publish_or_release_new_owner(self):
        def lose_lease(*args, **kwargs):
            RainForecastLock.objects.filter(name=self.location.code).update(
                token="replacement", expires_at=timezone.now() + timedelta(minutes=5))
            return self.normalized
        with patch("thongsothuyvan.rain_forecast_services.fetch_forecast", side_effect=lose_lease):
            result = refresh_forecasts()
        self.assertEqual(result["locations"][self.location.code], "lease_expired")
        self.assertFalse(RainForecastRevision.objects.exists())
        lease = RainForecastLock.objects.get(name=self.location.code)
        self.assertEqual(lease.token, "replacement")
        self.assertGreater(lease.expires_at, timezone.now())

    def test_revision_write_failure_retains_previous_forecast(self):
        self.refresh()
        self.normalized["daily"][0]["precipitation"] = 99
        with patch("thongsothuyvan.rain_forecast_services.fetch_forecast", return_value=self.normalized), patch(
            "thongsothuyvan.rain_forecast_services.RainForecastRevision.objects.create", side_effect=RuntimeError("secret must not escape")
        ):
            result = refresh_forecasts()
        self.assertEqual(result["locations"][self.location.code], "internal_error")
        self.assertEqual(RainForecastRevision.objects.count(), 1)
        self.assertEqual(location_forecast(self.location)["daily"][0]["precipitation_mm"], 0)
        self.assertEqual(location_forecast(self.location)["status"], "stale")
        self.assertEqual(RainForecastFetch.objects.latest("pk").error_code, "internal_error")

    def test_api_filters_other_plant_and_denies_missing_permission(self):
        self.refresh()
        RainForecastLocation.objects.create(code="test_vs", plant="vinhson", name="VS", latitude=14, longitude=108)
        user = SimpleNamespace(is_authenticated=True, is_superuser=False,
            profile=SimpleNamespace(can_view_realtime_hydrology=True, is_all_factories=False,
                                    nha_may=SimpleNamespace(ma_nha_may="SH")))
        request = APIRequestFactory().get("/?plant=songhinh")
        force_authenticate(request, user=user)
        response = RainForecastAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["code"] for item in response.data["locations"]], [self.location.code])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        user.profile.can_view_realtime_hydrology = False
        self.assertEqual(RainForecastAPIView.as_view()(request).status_code, 403)
