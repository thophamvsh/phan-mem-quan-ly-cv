"""Real HTTP transport check against the local synthetic simulation; no DB or real key."""
from datetime import datetime, timedelta
from django.conf import settings
settings.configure(VRAIN_API_KEY="synthetic-only", VRAIN_HISTORY_BASE_URL="http://127.0.0.1:4920/vrain/v1/stations/stats", VRAIN_HISTORY_ALLOW_LOCAL_TEST=True,VRAIN_HISTORY_HTTP_TIMEOUT=1)
from thongsothuyvan.vrain_history_provider import fetch_history,VrainHistoryError,VN
start=datetime(2026,1,1,0,0,tzinfo=VN)
result=fetch_history(start,start+timedelta(minutes=10))
assert result["Data"][0]["value"][0]["depth"]==0
print("PASS: real HTTP success, numeric zero and observed source schema")
for day,code in [(1,"http_500"),(2,"http_429"),(3,"http_401"),(4,"connection_failed")]:
    start=datetime(2000,1,day,tzinfo=VN)
    try:
        fetch_history(start,start+timedelta(minutes=10))
    except VrainHistoryError as error:
        assert str(error)==code,str(error)
        print("PASS: real HTTP",code)
    else:
        raise AssertionError("Expected failure")
settings.VRAIN_HISTORY_BASE_URL="http://127.0.0.1:1/v1/stations/stats"
try:
    fetch_history(start,start+timedelta(minutes=10))
except VrainHistoryError as error:
    assert str(error)=="connection_failed"
    print("PASS: refused connection")
else:
    raise AssertionError("Expected refused connection")
