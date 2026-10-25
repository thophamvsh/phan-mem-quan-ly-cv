"""Run against local Postman simulation. Isolated in-memory DB; no production writes."""
import os
from datetime import datetime,timedelta
os.environ["DJANGO_SETTINGS_MODULE"]="app.settings"
import django
from django.conf import settings
settings.DATABASES={"default":{"ENGINE":"django.db.backends.sqlite3","NAME":":memory:"}}
settings.CACHES={"default":{"BACKEND":"django.core.cache.backends.locmem.LocMemCache"}}
settings.VRAIN_API_KEY="synthetic-only"
settings.VRAIN_HISTORY_ENABLED=True
settings.VRAIN_INTERVAL_CONTRACT_VERIFIED=False
settings.VRAIN_HISTORY_ALLOW_LOCAL_TEST=True
settings.VRAIN_HISTORY_HTTP_TIMEOUT=1
settings.VRAIN_HISTORY_BASE_URL="http://127.0.0.1:4920/vrain/v1/stations/stats"
django.setup()
from django.db import connection
from thongsothuyvan.vrain_history_models import VrainStation,VrainSyncRun,VrainSourceSample,VrainRainfallRevision,VrainRainfallInterval,VrainSyncLease,VrainBackfillJob
from thongsothuyvan.vrain_history_services import sync_history
from thongsothuyvan.vrain_history_provider import VN
with connection.schema_editor() as editor:
    for model in [VrainStation,VrainSyncRun,VrainSourceSample,VrainRainfallRevision,VrainRainfallInterval,VrainSyncLease,VrainBackfillJob]:
        editor.create_model(model)
VrainStation.objects.create(source_station_code="036604",name="Synthetic",plant="songhinh")
start=datetime(2026,1,1,tzinfo=VN)
for _ in range(2):
    result=sync_history(start,start+timedelta(minutes=10))
    assert result["status"]=="captured_unverified",result
assert VrainSourceSample.objects.count()==2
assert VrainRainfallRevision.objects.count()==2
assert VrainSyncRun.objects.count()==2
assert not VrainRainfallInterval.objects.exists()
print("PASS: real HTTP -> audit/evidence -> samples -> idempotent revisions; no unverified intervals")
start=datetime(2000,1,3,tzinfo=VN)
result=sync_history(start,start+timedelta(minutes=10))
assert result["error_code"]=="http_401",result
assert VrainSourceSample.objects.count()==2
assert VrainSyncRun.objects.latest("pk").status=="error"
print("PASS: real 401 retained existing samples and recorded safe failure")
