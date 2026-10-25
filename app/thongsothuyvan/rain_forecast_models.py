from django.db import models


class RainForecastLocation(models.Model):
    code = models.CharField(max_length=40, unique=True)
    plant = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    station_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    enabled = models.BooleanField(default=True)
    note = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class RainForecastRevision(models.Model):
    location = models.ForeignKey(RainForecastLocation, on_delete=models.PROTECT, related_name="revisions")
    received_at = models.DateTimeField()
    source_issued_at = models.DateTimeField(null=True, blank=True)
    provider = models.CharField(max_length=30, default="open-meteo")
    fingerprint = models.CharField(max_length=64)
    # Immutable normalized hourly/daily arrays plus coordinates/model/parser metadata.
    # One atomic document prevents mixing days from different forecasts.
    data = models.JSONField()

    class Meta:
        indexes = [models.Index(fields=["location", "-received_at"], name="rain_rev_location_time")]


class RainForecastFetch(models.Model):
    location = models.ForeignKey(RainForecastLocation, on_delete=models.PROTECT, related_name="fetches")
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, default="running")
    error_code = models.CharField(max_length=80, blank=True)
    revision = models.ForeignKey(RainForecastRevision, null=True, on_delete=models.PROTECT)

    class Meta:
        indexes = [models.Index(fields=["location", "-started_at"], name="rain_fetch_location_time")]


class RainForecastLock(models.Model):
    """Database lease, independent of locmem cache and worker process."""
    name = models.CharField(max_length=40, primary_key=True)
    token = models.CharField(max_length=36)
    expires_at = models.DateTimeField()
