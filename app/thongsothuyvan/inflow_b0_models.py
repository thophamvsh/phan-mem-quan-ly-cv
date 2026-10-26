"""Prospective SH baseline shadow forecasts. No operational control actions."""
from django.db import models
from django.db.models import Q,F


class InflowB0Forecast(models.Model):
    plant=models.CharField(max_length=20,default="songhinh")
    model_version=models.CharField(max_length=40,default="b0-persistence-v1")
    issue_date=models.DateField()
    issued_at=models.DateTimeField()
    scheduled_for=models.DateTimeField()
    target_day=models.DateField()
    target_start=models.DateTimeField()
    target_end=models.DateTimeField()
    predicted_qve=models.FloatField()
    source_day=models.DateField()
    source_record_id=models.BigIntegerField()
    source_snapshot=models.JSONField()
    source_fingerprint=models.CharField(max_length=64)
    quality_flags=models.JSONField(default=list)
    # Only reconciliation bookkeeping changes; forecast contents are never overwritten.
    last_checked_at=models.DateTimeField(null=True,blank=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["plant","issue_date","model_version"],name="sh_b0_unique_issue"),
                     models.CheckConstraint(condition=Q(predicted_qve__gte=0),name="sh_b0_nonnegative"),
                     models.CheckConstraint(condition=Q(issued_at__lt=F("target_start")),name="sh_b0_before_target"),
                     models.CheckConstraint(condition=Q(target_end__gt=F("target_start")),name="sh_b0_target_positive")]
        indexes=[models.Index(fields=["plant","target_day"],name="sh_b0_target_day")]
        ordering=["-issued_at"]


class InflowB0Run(models.Model):
    action=models.CharField(max_length=20)
    trigger=models.CharField(max_length=20)
    started_at=models.DateTimeField()
    finished_at=models.DateTimeField(null=True)
    status=models.CharField(max_length=30,default="running")
    error_code=models.CharField(max_length=60,blank=True)
    forecast=models.ForeignKey(InflowB0Forecast,null=True,blank=True,on_delete=models.PROTECT,related_name="runs")
    details=models.JSONField(default=dict)
    class Meta:
        ordering=["-started_at"]


class InflowB0Evaluation(models.Model):
    forecast=models.ForeignKey(InflowB0Forecast,on_delete=models.PROTECT,related_name="evaluations")
    revision=models.PositiveIntegerField()
    checked_at=models.DateTimeField()
    status=models.CharField(max_length=30)
    source_record_id=models.BigIntegerField(null=True)
    actual_qve=models.FloatField(null=True)
    signed_error=models.FloatField(null=True)  # prediction minus actual, m3/s
    absolute_error=models.FloatField(null=True)
    squared_error=models.FloatField(null=True)
    volume_error_m3=models.FloatField(null=True)
    actual_snapshot=models.JSONField(default=dict)
    fingerprint=models.CharField(max_length=64)

    class Meta:
        constraints=[models.UniqueConstraint(fields=["forecast","revision"],name="sh_b0_unique_eval_rev")]
        ordering=["-revision"]
