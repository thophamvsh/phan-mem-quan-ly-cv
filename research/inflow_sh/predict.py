"""Experimental, dependency-free SH daily inference; no DB/API writes."""
import argparse,json,sys,time
from pathlib import Path
from datetime import datetime,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"app"))
from thongsothuyvan.inflow_forecasting import features_at,experimental_prediction,VN


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--source",type=Path,required=True);parser.add_argument("--model",type=Path,required=True);parser.add_argument("--issue-time",required=True);parser.add_argument("--lag-days",type=int,choices=[1,2],default=1)
    parser.add_argument("--allow-unqualified-ridge",action="store_true",help="Research only; bypass baseline fallback for unqualified Ridge")
    args=parser.parse_args();source=json.loads(args.source.read_text(encoding="utf-8"));model=json.loads(args.model.read_text(encoding="utf-8"));issue=datetime.fromisoformat(args.issue_time)
    if issue.tzinfo is None:raise ValueError("issue-time must include timezone")
    if args.lag_days!=model.get("availability_lag_days"):raise ValueError("Availability lag does not match model")
    if issue<datetime.fromisoformat(model["valid_from_issue_time"]):raise ValueError("Model was fitted with labels unavailable before this issue time")
    row=features_at(source,issue,args.lag_days)
    start=time.perf_counter();result=experimental_prediction(model,row,args.allow_unqualified_ridge)
    result.update(issue_time=issue.isoformat(),target_day=str(issue.astimezone(VN).date()+timedelta(days=1)),last_observation_day=row["last_observation_day"] if row else None,inference_ms=(time.perf_counter()-start)*1000,model_checksum=model["checksum"],warning="Retrospective availability assumption; not approved for operations.")
    print(json.dumps(result))


if __name__=="__main__":main()
