"""Offline SH hindcast benchmark. Never uses test to select a model."""
import argparse,csv,hashlib,json,os,platform,sys,time
from pathlib import Path
from datetime import datetime,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"app"))
import numpy as np
import sklearn
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from thongsothuyvan.inflow_forecasting import build_dataset,prepare_sources,digest,predict_artifact,features_at,FEATURE_VERSION
from thongsothuyvan.inflow_audit import candidate_events

ALPHAS=(.1,1.,10.,100.,1000.)


def metrics(actual,predicted):
    y,p=np.asarray(actual,float),np.asarray(predicted,float)
    if not len(y):return {"n":0}
    error=p-y;variance=np.sum((y-np.mean(y))**2)
    high=y>300
    return {"n":len(y),"mae":float(np.mean(abs(error))),"rmse":float(np.sqrt(np.mean(error**2))),
            "nse":float(1-np.sum(error**2)/variance) if variance>0 else None,
            "bias":float(np.mean(error)),"high_days":int(high.sum()),
            "high_day_mae":float(np.mean(abs(error[high]))) if high.any() else None,
            "high_day_mean_underforecast":float(np.mean(np.maximum(-error[high],0))) if high.any() else None}


def columns(rows,group):
    keys=sorted(rows[0]["features"])
    base=[name for name in keys if name.startswith(("qve_","season_"))]
    if group in {"qcm","rain","rain_no_alias"}:base+=[name for name in keys if name.startswith("qcm_")]
    if group in {"rain","rain_no_alias"}:base+=[name for name in keys if name.startswith("rain_") and (group!="rain_no_alias" or "Xa_Ea_M_doan" not in name)]
    return base


def matrix(rows,names):
    return np.array([[row["features"][name] if row["features"][name] is not None else np.nan for name in names] for row in rows],float)


def fit(rows,names,alpha):
    x=matrix(rows,names)
    medians=np.array([np.median(col[np.isfinite(col)]) if np.isfinite(col).any() else 0 for col in x.T])
    filled=np.where(np.isfinite(x),x,medians)
    scaler=StandardScaler().fit(filled)
    ridge=Ridge(alpha=alpha).fit(scaler.transform(filled),np.array([r["target_qve"] for r in rows]))
    artifact={"schema_version":"sh-ridge-json-v1","feature_version":FEATURE_VERSION,"features":names,
              "alpha":alpha,"impute":medians.tolist(),"center":scaler.mean_.tolist(),"scale":scaler.scale_.tolist(),
              "coefficients":ridge.coef_.tolist(),"intercept":float(ridge.intercept_),"nonnegative_output":True,
              "mode":"experimental_hindcast_not_approved_for_operations"}
    artifact["checksum"]=digest(artifact)
    return artifact,ridge,scaler


def predict(model,rows):
    return [predict_artifact(model,r["features"]) for r in rows]


def before_fit(rows,first_issue):
    return [r for r in rows if datetime.fromisoformat(r["target_assumed_known_at"])<=first_issue]


def select(train,validation):
    records=[]
    for group in ["qve","qcm","rain","rain_no_alias"]:
        names=columns(train,group)
        for alpha in ALPHAS:
            artifact,_,_=fit(train,names,alpha)
            score=metrics([r["target_qve"] for r in validation],predict(artifact,validation))
            records.append({"group":group,"alpha":alpha,"validation":score})
    records.sort(key=lambda r:(r["validation"]["mae"],len(columns(train,r["group"])),r["alpha"]))
    return records[0],records


def baselines(rows):
    y=[r["target_qve"] for r in rows]
    return {"B0_persistence":metrics(y,[r["baseline_persistence"] for r in rows]),"B1_mean3":metrics(y,[r["baseline_mean3"] for r in rows])}


def event_checks(rows,snapshot):
    # Nested, retrospective LOFEO within development data only. Not operational CV.
    hydro,_,_,_=prepare_sources(snapshot)
    observed={day:row.get("qve") for day,row in hydro.items() if day.year<=2025}
    events=candidate_events(observed,300,1)
    folds=[]
    for event in events:
        lower=event["start"]-timedelta(days=9);upper=event["end"]+timedelta(days=9)
        held=[r for r in rows if event["start"]<=datetime.fromisoformat(r["target_start"]).date()<=event["end"]]
        pool=[r for r in rows if not lower<=datetime.fromisoformat(r["target_start"]).date()<=upper]
        if not held or len(pool)<240:continue
        cut=int(len(pool)*.8)
        inner_validation=pool[cut:]
        inner_train=before_fit(pool[:cut],datetime.fromisoformat(inner_validation[0]["issue_time"]))
        selected,_=select(inner_train,inner_validation)
        artifact,_,_=fit(pool,columns(pool,selected["group"]),selected["alpha"])
        baseline=baselines(inner_validation)
        baseline_name=min(baseline,key=lambda name:baseline[name]["mae"])
        key="baseline_persistence" if baseline_name=="B0_persistence" else "baseline_mean3"
        folds.append({"event":{k:str(v) for k,v in event.items()},"purge_days":9,"train_rows":len(pool),"held_rows":len(held),
                      "selection":selected,"baseline_selected_on_inner_validation":baseline_name,
                      "baseline":metrics([r["target_qve"] for r in held],[r[key] for r in held]),
                      "ridge":metrics([r["target_qve"] for r in held],predict(artifact,held))})
    return {"kind":"nested_retrospective_LOFEO_not_operational_skill","threshold":300,"bridge_days":1,"folds":folds}


def parity_check(model,rows,ridge,scaler):
    x=matrix(rows,model["features"])
    filled=np.where(np.isfinite(x),x,np.array(model["impute"]))
    expected=np.maximum(0,ridge.predict(scaler.transform(filled)))
    actual=np.array(predict(model,rows))
    delta=float(np.max(abs(expected-actual)))
    if not np.allclose(expected,actual,rtol=1e-10,atol=1e-8):raise AssertionError("Portable Ridge prediction parity failed")
    return delta


def save_csv(path,rows):
    names=sorted(rows[0]["features"])
    meta=["issue_time","target_day","target_start","target_end","target_assumed_known_at","target_qve","target_source_id","last_observation_day","assumed_cutoff_day","baseline_persistence","baseline_mean3"]
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=meta+names+["source_ids"]);writer.writeheader()
        for r in rows:writer.writerow({**{key:r[key] for key in meta},**r["features"],"source_ids":json.dumps(r["source_ids"],sort_keys=True)})


def dump(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--source",required=True,type=Path);parser.add_argument("--output",required=True,type=Path);parser.add_argument("--lag-days",type=int,choices=[1,2],default=1);parser.add_argument("--event-checks",action="store_true")
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter();source=json.loads(args.source.read_text(encoding="utf-8"))
    rows,meta=build_dataset(source,args.lag_days)
    train=[r for r in rows if r["target_day"]<"2025-01-01"]
    validation=[r for r in rows if "2025-01-01"<=r["target_day"]<"2026-01-01"]
    test=[r for r in rows if r["target_day"]>="2026-01-01"]
    if min(map(len,[train,validation,test]))<30:raise ValueError("Insufficient chronological split")
    first_test_issue=datetime.fromisoformat(test[0]["issue_time"])
    validation=before_fit(validation,first_test_issue)
    train=before_fit(train,datetime.fromisoformat(validation[0]["issue_time"]))
    selected,search=select(train,validation)
    validation_baselines=baselines(validation)
    best_baseline=min(validation_baselines,key=lambda name:validation_baselines[name]["mae"])
    development=before_fit([r for r in rows if r["target_day"]<"2026-01-01"],first_test_issue)
    model,ridge,scaler=fit(development,columns(development,selected["group"]),selected["alpha"])
    model.update({"availability_lag_days":args.lag_days,"plant":"songhinh","target":"daily_mean_qve_m3s_next_calendar_day",
                  "valid_from_issue_time":first_test_issue.isoformat(),"training_source_sha256":hashlib.sha256(args.source.read_bytes()).hexdigest()})
    model["checksum"]=digest({k:v for k,v in model.items() if k!="checksum"})
    parity=parity_check(model,rows,ridge,scaler)
    test_scores=baselines(test);test_scores["Ridge_selected_on_2025"]=metrics([r["target_qve"] for r in test],predict(model,test))
    improvement=1-test_scores["Ridge_selected_on_2025"]["mae"]/test_scores[best_baseline]["mae"]
    holdout_has_high_days=any(r["target_qve"]>300 for r in test)
    # Technical validity is separate from operational acceptance.
    report={"evaluation_kind":"retrospective_hindcast_with_assumed_availability","selection_uses":"train 2023-2024; validation 2025 only; purge labels unavailable before next fold issue",
            "selected":selected,"validation_search":search,"validation_baselines":validation_baselines,"best_baseline_selected_on_validation":best_baseline,
            "test_2026":test_scores,"test_mae_improvement_vs_preselected_baseline":improvement,
            "portable_artifact_max_abs_difference":parity,"split_counts":{"train":len(train),"validation":len(validation),"final_fit_development":len(development),"test":len(test)},
            "technical_checks":{"causal_features":True,"training_labels_available_under_assumption":True,"test_not_used_for_selection":True,"portable_prediction_parity":True},
            "qualification":{"test_mae_improved_10pct":improvement>=.1,"test_contains_high_qve_days":holdout_has_high_days,
                             "historical_approval_times_verified":False,"rain_zero_missing_semantics_verified":False,"orangepi_benchmarked":False,"production_ready":False},
            "limitations":["No archived NWP used; unobserved new storms cannot be learned from future rain.","Daily rain unknown status and station alias unresolved; rain features are experimental.","Missing Qcm is imputed from train only; Qcm daily definition/availability not fully confirmed.","2026 holdout is partial year and may not test flood extremes.","Do not tune on this test after inspecting results; any new iterations require a fresh final test."],
            "elapsed_seconds":time.perf_counter()-started}
    if args.event_checks:report["events_development"]=event_checks(development,source)
    report["elapsed_seconds"]=time.perf_counter()-started
    save_csv(args.output/"dataset.csv",rows)
    manifest={**meta,"source_sha256":hashlib.sha256(args.source.read_bytes()).hexdigest(),"dataset_sha256":hashlib.sha256((args.output/"dataset.csv").read_bytes()).hexdigest(),"rows":len(rows),"lag_days":args.lag_days,
              "selected_features":model["features"],"target_source":source["qve_source"],"qcm_source":source["qcm_source"],"data_exported_at":source["exported_at"],
              "software":{"python":platform.python_version(),"numpy":np.__version__,"scikit_learn":sklearn.__version__},"protocol":"fixed chronological split; 20 Ridge candidates selected only on 2025; nonnegative predictions"}
    model["fallback_baseline"]=best_baseline
    model["qualification"]=report["qualification"]
    model["checksum"]=digest({k:v for k,v in model.items() if k!="checksum"})
    dump(args.output/"manifest.json",manifest);dump(args.output/"model.json",model);dump(args.output/"report.json",report)
    predictions=[{"issue_time":r["issue_time"],"target_day":r["target_day"],"actual_qve":r["target_qve"],"B0":r["baseline_persistence"],"B1":r["baseline_mean3"],"Ridge":p} for r,p in zip(test,predict(model,test))]
    with (args.output/"test_predictions.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(predictions[0]));writer.writeheader();writer.writerows(predictions)
    # No deployment artifact is promoted automatically, even if MAE passes.
    print(json.dumps({"selected":selected,"counts":report["split_counts"],"test":test_scores,"mae_improvement":improvement,"qualification":report["qualification"],"output":str(args.output)},indent=2))


if __name__=="__main__":main()
