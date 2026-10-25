"""Parallel VRAIN ingestion. Source evidence is separate from verified intervals."""
from django.db import models
from django.db.models import Q, F


class VrainStation(models.Model):
    provider = models.CharField(max_length=20, default="vrain")
    source_station_code = models.CharField(max_length=30)
    name = models.CharField(max_length=120)
    plant = models.CharField(max_length=20)
    enabled = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["provider", "source_station_code"], name="vrain_station_provider_code")]

    def __str__(self):
        return f"{self.source_station_code} - {self.name}"


class VrainSyncRun(models.Model):
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=30, default="running")
    error_code = models.CharField(max_length=60, blank=True)
    counts = models.JSONField(default=dict)
    # Allowlisted source fields only; no request URL, headers or API key.
    evidence = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64, blank=True)
    parser_version = models.CharField(max_length=30, default="vrain-evidence-v1")
    contract_verified = models.BooleanField(default=False)


class VrainSourceSample(models.Model):
    station = models.ForeignKey(VrainStation, on_delete=models.PROTECT, related_name="samples")
    source_timestamp = models.DateTimeField()
    first_received_at = models.DateTimeField()
    last_received_at = models.DateTimeField()
    fingerprint = models.CharField(max_length=64)
    data = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["station", "source_timestamp"], name="vrain_sample_station_time")]
        indexes = [models.Index(fields=["station", "-source_timestamp"], name="vrain_sample_time")]


class VrainRainfallRevision(models.Model):
    sample = models.ForeignKey(VrainSourceSample, on_delete=models.PROTECT, related_name="revisions")
    run = models.ForeignKey(VrainSyncRun, on_delete=models.PROTECT)
    received_at = models.DateTimeField()
    data = models.JSONField()
    fingerprint = models.CharField(max_length=64)

    class Meta:
        indexes = [models.Index(fields=["sample", "-received_at"], name="vrain_revision_received")]


class VrainRainfallInterval(models.Model):
    station = models.ForeignKey(VrainStation, on_delete=models.PROTECT, related_name="intervals")
    interval_start = models.DateTimeField()
    interval_end = models.DateTimeField()
    rainfall_mm = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    status = models.CharField(max_length=20)
    quality_flags = models.JSONField(default=list)
    revision = models.ForeignKey(VrainRainfallRevision, null=True, on_delete=models.PROTECT)
    parser_version = models.CharField(max_length=30, default="vrain-interval-v1")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["station", "interval_start", "interval_end"], name="vrain_unique_interval"),
            models.CheckConstraint(condition=Q(interval_end__gt=F("interval_start")), name="vrain_positive_interval"),
            models.CheckConstraint(condition=Q(rainfall_mm__isnull=True) | Q(rainfall_mm__gte=0), name="vrain_nonnegative_rain"),
        ]
        indexes = [models.Index(fields=["station", "interval_end"], name="vrain_interval_station_end"), models.Index(fields=["interval_end"], name="vrain_interval_end")]


class VrainSyncLease(models.Model):
    name = models.CharField(max_length=30, primary_key=True)
    token = models.CharField(max_length=36)
    expires_at = models.DateTimeField()


class VrainBackfillJob(models.Model):
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    cursor = models.DateTimeField()
    status = models.CharField(max_length=20, default="pending")
    last_run = models.ForeignKey(VrainSyncRun, null=True, on_delete=models.PROTECT)
