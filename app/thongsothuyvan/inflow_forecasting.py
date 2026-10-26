"""Causal daily SH feature builder and dependency-light Ridge inference.

Historical availability is an explicit hindcast assumption, NOT a reconstruction
of actual approvals. Daily Qve target uses approved hydrology, never production Qve.
"""
import hashlib
import json
import math
from collections import defaultdict
from datetime import date,datetime,time,timedelta
from zoneinfo import ZoneInfo

VN=ZoneInfo("Asia/Ho_Chi_Minh")
RAIN_FIELDS=("Dap_Tran","Thon_10_Xa_Ea_M_Doal","Xa_Ea_M_doan","Xa_Ea_Trang","Cu_Kroa","UBND_xa_Song_Hinh")
FEATURE_VERSION="sh-daily-causal-v1"


def number(value):
    if value is None or isinstance(value,bool):
        return None
    try:
        result=float(value)
        return result if math.isfinite(result) and result>=0 else None
    except (TypeError,ValueError,OverflowError):
        return None


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def source_day(value):
    if isinstance(value,date) and not isinstance(value,datetime):
        return value
    value=str(value)
    if "T" not in value and " " not in value:
        return date.fromisoformat(value)
    stamp=datetime.fromisoformat(value.replace("Z","+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Timestamp without timezone")
    return stamp.astimezone(VN).date()


def calendar_index(rows,key):
    grouped=defaultdict(list)
    for row in rows:
        grouped[source_day(row[key])].append(row)
    return {day:items[0] for day,items in grouped.items() if len(items)==1},[str(day) for day,items in sorted(grouped.items()) if len(items)>1]


def prepare_sources(snapshot):
    if snapshot.get("schema_version")!="sh-source-v1" or snapshot.get("plant")!="songhinh":
        raise ValueError("Unsupported source schema or plant")
    hydro,hd=calendar_index(snapshot["hydrology"],"ngay")
    production,pd=calendar_index(snapshot["production"],"thoi_gian")
    rain,rd=calendar_index(snapshot["rain"],"Thoi_gian")
    return hydro,production,rain,{"hydrology":hd,"production":pd,"rain":rd}


def features_at(snapshot,issue_time,availability_lag_days=1,prepared=None):
    if issue_time.tzinfo is None or availability_lag_days not in {1,2}:
        raise ValueError("Aware issue time and availability lag 1 or 2 days required")
    # Assumed published at 07:00 on observation day + lag. Before 07:00,
    # another day is unavailable. Online callers must supply actually available data.
    local=issue_time.astimezone(VN)
    cutoff=local.date()-timedelta(days=availability_lag_days+(local.time()<time(7)))
    hydro,production,rain,_=prepared or prepare_sources(snapshot)
    candidates=[day for day in hydro if day<=cutoff and number(hydro[day].get("qve")) is not None]
    if not candidates:
        return None
    latest=max(candidates)
    age=(cutoff-latest).days
    if age>2:
        return None
    values={"qve_latest":number(hydro[latest].get("qve")),"qve_age_days":age,
            "season_sin":math.sin(2*math.pi*local.timetuple().tm_yday/365.25),
            "season_cos":math.cos(2*math.pi*local.timetuple().tm_yday/365.25)}
    used={"hydrology":[],"production":[],"rain":[]}
    for lag in [0,1,2,6]:
        day=cutoff-timedelta(days=lag)
        values[f"qve_lag_{lag}"]=number(hydro.get(day,{}).get("qve"))
        if day in hydro:used["hydrology"].append(hydro[day]["id"])
    used["hydrology"].append(hydro[latest]["id"])
    qlast=[number(hydro.get(cutoff-timedelta(days=i),{}).get("qve")) for i in range(3)]
    values["qve_mean3"]=sum(qlast)/3 if all(v is not None for v in qlast) else None
    values["qve_trend"]=qlast[0]-qlast[1] if all(v is not None for v in qlast[:2]) else None
    qcm=[]
    for i in range(3):
        day=cutoff-timedelta(days=i)
        row=production.get(day,{})
        value=number(row.get("cot_j"));qcm.append(value)
        values[f"qcm_lag_{i}"]=value
        if row:used["production"].append(row["id"])
    values["qcm_mean3"]=sum(qcm)/3 if all(v is not None for v in qcm) else None
    unknown=0
    for station in RAIN_FIELDS:
        window=[number(rain.get(cutoff-timedelta(days=i),{}).get(station)) for i in range(7)]
        values[f"rain_{station}_last"]=window[0]
        for size in [3,7]:
            valid=[v for v in window[:size] if v is not None]
            values[f"rain_{station}_sum{size}"]=sum(valid) if len(valid)==size else None
            values[f"rain_{station}_coverage{size}"]=len(valid)/size
    for i in range(7):
        row=rain.get(cutoff-timedelta(days=i))
        if row:
            used["rain"].append(row["id"])
            unknown+=row.get("sync_status") not in {"finalized"}
    values["rain_unverified_days7"]=unknown
    for name,value in list(values.items()):
        values[name+"_missing"]=int(value is None)
    return {"features":values,"last_observation_day":str(latest),"assumed_cutoff_day":str(cutoff),
            "source_ids":{key:sorted(set(ids)) for key,ids in used.items()},
            "baseline_persistence":values["qve_latest"],
            "baseline_mean3":values["qve_mean3"] if values["qve_mean3"] is not None else values["qve_latest"]}


def build_dataset(snapshot,availability_lag_days=1):
    prepared=prepare_sources(snapshot)
    hydro,_,_,duplicates=prepared
    rows=[];excluded={"invalid_target":0,"stale_or_missing_qve_history":0}
    for target in sorted(hydro):
        y=number(hydro[target].get("qve"))
        if y is None:
            excluded["invalid_target"]+=1;continue
        issue_day=target-timedelta(days=1)
        issue=datetime.combine(issue_day,time(7,30),VN)
        result=features_at(snapshot,issue,availability_lag_days,prepared)
        if result is None:
            excluded["stale_or_missing_qve_history"]+=1;continue
        rows.append({"issue_time":issue.isoformat(),"target_day":str(target),
                     "target_start":datetime.combine(target,time.min,VN).isoformat(),
                     "target_end":datetime.combine(target+timedelta(days=1),time.min,VN).isoformat(),
                     "target_assumed_known_at":datetime.combine(target+timedelta(days=availability_lag_days),time(7),VN).isoformat(),
                     "target_qve":y,"target_source_id":hydro[target]["id"],**result})
    return rows,{"duplicate_days_excluded":duplicates,"excluded_rows":excluded,
                 "availability_assumption":f"Observation day + {availability_lag_days} day(s), published at 07:00 Vietnam. Historical approval receipt times not reconstructed.",
                 "evaluation_kind":"retrospective_hindcast","feature_version":FEATURE_VERSION}


def predict_artifact(artifact,feature_row):
    if artifact.get("schema_version")!="sh-ridge-json-v1" or artifact.get("feature_version")!=FEATURE_VERSION:
        raise ValueError("Unsupported model artifact")
    payload={key:value for key,value in artifact.items() if key!="checksum"}
    if artifact.get("checksum")!=digest(payload):
        raise ValueError("Model checksum mismatch")
    schema=artifact["features"]
    if len(set(schema))!=len(schema):raise ValueError("Duplicate model features")
    n=len(schema)
    for key in ["impute","center","scale","coefficients"]:
        if len(artifact[key])!=n:raise ValueError("Model vector length mismatch")
    value=artifact["intercept"]
    for i,name in enumerate(schema):
        if name not in feature_row:raise ValueError("Feature schema mismatch")
        observed=feature_row[name]
        if observed is None:observed=artifact["impute"][i]
        if not math.isfinite(observed) or not math.isfinite(artifact["scale"][i]) or artifact["scale"][i]<=0:
            raise ValueError("Invalid model input or scale")
        value+=(observed-artifact["center"][i])/artifact["scale"][i]*artifact["coefficients"][i]
    if not math.isfinite(value):raise ValueError("Non-finite prediction")
    # Explicit policy: daily target is nonnegative; apply identically offline/online.
    return max(0.,value)


def experimental_prediction(model,row,allow_unqualified_ridge=False):
    """Never silently present a rejected candidate as the accepted model."""
    if row is None:
        return {"status":"unavailable","reason":"missing_or_stale_qve_history","qve_m3s":None}
    # Verify model even if falling back, so corrupt artifacts cannot select policy.
    payload={key:value for key,value in model.items() if key!="checksum"}
    if model.get("checksum")!=digest(payload):raise ValueError("Model checksum mismatch")
    if allow_unqualified_ridge:
        return {"status":"experimental_unqualified_ridge","model":"Ridge","qve_m3s":predict_artifact(model,row["features"])}
    fallback=model.get("fallback_baseline")
    key={"B0_persistence":"baseline_persistence","B1_mean3":"baseline_mean3"}.get(fallback)
    if key is None:raise ValueError("Missing preselected baseline policy")
    return {"status":"experimental_baseline_only","model":fallback,"qve_m3s":row[key],"reason":"Ridge candidate is not operationally qualified"}
