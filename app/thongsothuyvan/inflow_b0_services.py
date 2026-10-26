import hashlib,json,math
from datetime import datetime,time,timedelta
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db import transaction
from django.db.models import F,OuterRef,Subquery
from django.utils import timezone
from .models import ThongSoThuyVanThucTe
from .inflow_b0_models import InflowB0Forecast,InflowB0Run,InflowB0Evaluation

VN=ZoneInfo("Asia/Ho_Chi_Minh")
VERSION="b0-persistence-v1"


def finite_nonnegative(value):
    if value is None or isinstance(value,bool):return None
    try:
        number=float(value)
        return number if math.isfinite(number) and number>=0 else None
    except (ValueError,TypeError,OverflowError):return None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def finish(run,status,*,error_code="",forecast=None,details=None):
    run.status=status;run.error_code=error_code;run.finished_at=timezone.now()
    run.forecast=forecast;run.details=details or {}
    run.save(update_fields=["status","error_code","finished_at","forecast","details"])
    return {"status":status,"run_id":run.pk,**({"forecast_id":forecast.pk} if forecast else {}),**run.details,**({"error_code":error_code} if error_code else {})}


def publish_b0(*,manual=False,dry_run=False):
    if not manual and not getattr(settings,"INFLOW_B0_SH_ENABLED",False):return {"status":"disabled"}
    started=timezone.now()
    run=None if dry_run else InflowB0Run.objects.create(action="publish",trigger="manual" if manual else "scheduled",started_at=started)
    try:
        with transaction.atomic():
            now=timezone.now();today=now.astimezone(VN).date()
            existing=InflowB0Forecast.objects.filter(plant="songhinh",issue_date=today,model_version=VERSION).first()
            if existing:
                result={"status":"already_exists","forecast_id":existing.pk,"issued_at":existing.issued_at.isoformat(),"target_day":str(existing.target_day),"predicted_qve":existing.predicted_qve}
                return result if dry_run else finish(run,"already_exists",forecast=existing,details={k:v for k,v in result.items() if k not in {"status","forecast_id"}})
            candidates=ThongSoThuyVanThucTe.objects.filter(nha_may="songhinh",ngay__lt=today,created_at__lte=now,updated_at__lte=now).order_by("-ngay","-pk")
            if not dry_run:candidates=candidates.select_for_update()
            # Inspect recent dates only; never silently use an old valid row indefinitely.
            age_limit=getattr(settings,"INFLOW_B0_SH_MAX_SOURCE_AGE_DAYS",2)
            source=next((row for row in candidates.filter(ngay__gte=today-timedelta(days=age_limit)) if finite_nonnegative(row.qve) is not None),None)
            if source is None:
                reason="missing_invalid_or_stale_approved_qve"
                return {"status":"unavailable","reason":reason} if dry_run else finish(run,"unavailable",details={"reason":reason})
            # Recheck actual wall clock after waiting for the source lock.
            issued=timezone.now();issue_date=issued.astimezone(VN).date()
            if issue_date!=today:
                return {"status":"unavailable","reason":"date_changed_retry"} if dry_run else finish(run,"unavailable",details={"reason":"date_changed_retry"})
            target=today+timedelta(days=1)
            snapshot={"table":"ThongSoThuyVanThucTe","field":"qve","id":source.pk,"ngay":str(source.ngay),"qve":finite_nonnegative(source.qve),"created_at":source.created_at.isoformat(),"updated_at":source.updated_at.isoformat(),"captured_at":issued.isoformat(),"approval_basis":"operator_designated_approved_hydrology_source; separate approval timestamp not recorded"}
            flags=["experimental_baseline","not_for_automatic_operation"]
            if (today-source.ngay).days>1:flags.append("older_than_previous_day")
            scheduled=datetime.combine(today,time(7,30),VN)
            if issued>scheduled+timedelta(minutes=15):flags.append("late_manual_or_delayed_publication")
            values={"issued_at":issued,"scheduled_for":scheduled,"target_day":target,"target_start":datetime.combine(target,time.min,VN),"target_end":datetime.combine(target+timedelta(days=1),time.min,VN),"predicted_qve":snapshot["qve"],"source_day":source.ngay,"source_record_id":source.pk,"source_snapshot":snapshot,"source_fingerprint":fingerprint(snapshot),"quality_flags":flags}
            if dry_run:return {"status":"dry_run","target_day":str(target),"predicted_qve":snapshot["qve"],"source_day":str(source.ngay),"quality_flags":flags}
            forecast,created=InflowB0Forecast.objects.get_or_create(plant="songhinh",issue_date=today,model_version=VERSION,defaults=values)
            return finish(run,"published" if created else "already_exists",forecast=forecast,details={"target_day":str(forecast.target_day),"predicted_qve":forecast.predicted_qve,"source_day":str(forecast.source_day)})
    except Exception:
        if run:return finish(run,"error",error_code="internal_error")
        raise


def reconcile_b0(*,manual=False,target_day=None,limit=500):
    if not manual and not getattr(settings,"INFLOW_B0_SH_ENABLED",False):return {"status":"disabled"}
    if not 1<=limit<=5000:raise ValueError("limit must be 1..5000")
    now=timezone.now()
    if target_day is not None and target_day>=now.astimezone(VN).date():raise ValueError("target day has not ended")
    run=InflowB0Run.objects.create(action="reconcile",trigger="manual" if manual else "scheduled",started_at=now)
    counts={"checked":0,"new_revisions":0,"verified":0,"missing_actual":0,"invalid_actual":0}
    try:
        forecasts=InflowB0Forecast.objects.filter(plant="songhinh",target_end__lte=now).order_by(F("last_checked_at").asc(nulls_first=True),"pk")
        if target_day is not None:forecasts=forecasts.filter(target_day=target_day)
        ids=list(forecasts.values_list("pk",flat=True)[:limit])
        for pk in ids:
            with transaction.atomic():
                forecast=InflowB0Forecast.objects.select_for_update().get(pk=pk)
                checked=timezone.now()
                actual=ThongSoThuyVanThucTe.objects.select_for_update().filter(nha_may="songhinh",ngay=forecast.target_day,created_at__lte=checked,updated_at__lte=checked).first()
                value=finite_nonnegative(actual.qve) if actual else None
                status="missing_actual" if actual is None else "invalid_actual" if value is None else "verified"
                raw_value=float(actual.qve) if actual is not None and actual.qve is not None and math.isfinite(actual.qve) else None
                snapshot={"raw_qve":raw_value,"table":"ThongSoThuyVanThucTe","field":"qve","id":actual.pk if actual else None,"ngay":str(forecast.target_day),"qve":value,"created_at":actual.created_at.isoformat() if actual else None,"updated_at":actual.updated_at.isoformat() if actual else None,"invalid_value":value is None and actual is not None}
                # Only value/status/identity changes create an evaluation revision.
                mark=fingerprint({"status":status,"source_record_id":snapshot["id"],"day":snapshot["ngay"],"qve":value,"raw_qve":raw_value})
                latest=forecast.evaluations.order_by("-revision").first()
                if latest is None or latest.fingerprint!=mark:
                    error=forecast.predicted_qve-value if value is not None else None
                    InflowB0Evaluation.objects.create(forecast=forecast,revision=latest.revision+1 if latest else 1,checked_at=checked,status=status,source_record_id=actual.pk if actual else None,actual_qve=value,signed_error=error,absolute_error=abs(error) if error is not None else None,squared_error=error**2 if error is not None else None,volume_error_m3=error*86400 if error is not None else None,actual_snapshot=snapshot,fingerprint=mark)
                    counts["new_revisions"]+=1
                forecast.last_checked_at=checked;forecast.save(update_fields=["last_checked_at"])
                counts["checked"]+=1;counts[status]+=1
        return finish(run,"completed",details=counts)
    except Exception:
        return finish(run,"error",error_code="internal_error",details=counts)


def b0_report():
    # Score the latest revision only; never count corrections as extra forecasts.
    latest=InflowB0Evaluation.objects.filter(forecast_id=OuterRef("forecast_id")).order_by("-revision").values("pk")[:1]
    evaluations=list(InflowB0Evaluation.objects.filter(forecast__plant="songhinh",pk=Subquery(latest)).select_related("forecast"))
    valid=[e for e in evaluations if e.status=="verified"]
    n=len(valid)
    mean=sum(e.actual_qve for e in valid)/n if n else None
    denom=sum((e.actual_qve-mean)**2 for e in valid) if n else 0
    return {"mode":"prospective_shadow_baseline_not_operational_guidance","model_version":VERSION,"forecasts":InflowB0Forecast.objects.filter(plant="songhinh").count(),"scored":n,"missing_actual":sum(e.status=="missing_actual" for e in evaluations),"invalid_actual":sum(e.status=="invalid_actual" for e in evaluations),"unevaluated":InflowB0Forecast.objects.filter(plant="songhinh",evaluations__isnull=True).count(),
            "mae":sum(e.absolute_error for e in valid)/n if n else None,"rmse":math.sqrt(sum(e.squared_error for e in valid)/n) if n else None,"bias":sum(e.signed_error for e in valid)/n if n else None,"nse":1-sum(e.squared_error for e in valid)/denom if denom else None,
            "automatic_enabled":getattr(settings,"INFLOW_B0_SH_ENABLED",False),
            "results":_report_rows(evaluations)}


def _report_rows(evaluations):
    latest={item.forecast_id:item for item in evaluations}
    result=[];now=timezone.now()
    for forecast in InflowB0Forecast.objects.filter(plant="songhinh").order_by("target_day","pk"):
        evaluation=latest.get(forecast.pk)
        result.append({"forecast_id":forecast.pk,"target_day":str(forecast.target_day),"issued_at":forecast.issued_at.isoformat(),"prediction":forecast.predicted_qve,"source_day":str(forecast.source_day),"actual":evaluation.actual_qve if evaluation else None,"status":evaluation.status if evaluation else "target_not_ended" if forecast.target_end>now else "awaiting_reconciliation","evaluation_revision":evaluation.revision if evaluation else None})
    return result
