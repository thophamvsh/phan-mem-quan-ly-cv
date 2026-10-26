import json
from collections import Counter,defaultdict
from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand,CommandError
from django.db import connection,transaction
from django.db.models import Count,Min,Max
from django.utils import timezone
from thongsothuyvan.inflow_audit import distribution,candidate_events,compare_daily,finite

VN=ZoneInfo("Asia/Ho_Chi_Minh")


def group_days(rows,time_field,value_field):
    grouped=defaultdict(list)
    for row in rows:
        stamp=row[time_field]
        day=stamp.astimezone(VN).date() if hasattr(stamp,"hour") else stamp
        grouped[day].append(row[value_field])
    # Ambiguous duplicates are excluded, not silently averaged or overwritten.
    return {day:values[0] for day,values in grouped.items() if len(values)==1},[str(day) for day,values in sorted(grouped.items()) if len(values)>1]


class Command(BaseCommand):
    help="Read-only SH audit: daily Qve distribution, threshold-event candidates, source comparison and station aliases."
    requires_migrations_checks=True

    def add_arguments(self,parser):
        parser.add_argument("--threshold",type=float,default=300)
        parser.add_argument("--bridge-days",type=int,default=1)

    def handle(self,*args,**options):
        import math
        if not math.isfinite(options["threshold"]) or options["threshold"]<=0 or not 0<=options["bridge_days"]<=7:
            raise CommandError("Threshold must be finite/positive; bridge-days must be 0..7")
        if connection.vendor not in {"postgresql","sqlite"}:
            raise CommandError("Read-only audit supports PostgreSQL or SQLite only")
        sqlite_previous=None
        if connection.vendor=="sqlite":
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA query_only")
                sqlite_previous=cursor.fetchone()[0]
                cursor.execute("PRAGMA query_only=ON")
        try:
            with transaction.atomic():
                if connection.vendor=="postgresql":
                    with connection.cursor() as cursor:
                        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                report=self.collect(options)
        finally:
            if sqlite_previous is not None:
                with connection.cursor() as cursor:
                    cursor.execute(f"PRAGMA query_only={int(sqlite_previous)}")
        self.stdout.write(json.dumps(report,default=str,ensure_ascii=True,indent=2,allow_nan=False))

    def collect(self,options):
        from thongsothuyvan.models import ThongSoThuyVanThucTe,ThongsoSanxuat,TramDoMuaVrain,SongHinhRealtimeSnapshot
        from thongsothuyvan.vrain_history_models import VrainStation,VrainSourceSample
        hydro_rows=list(ThongSoThuyVanThucTe.objects.filter(nha_may="songhinh").order_by("ngay").values("ngay","qve"))
        production_rows=list(ThongsoSanxuat.objects.filter(nha_may="songhinh").order_by("thoi_gian").values("thoi_gian","cot_i"))
        hydro,hydro_duplicates=group_days(hydro_rows,"ngay","qve")
        production,production_duplicates=group_days(production_rows,"thoi_gian","cot_i")
        rain_fields=["Dap_Tran","Thon_10_Xa_Ea_M_Doal","Xa_Ea_M_doan","Xa_Ea_Trang","Cu_Kroa","UBND_xa_Song_Hinh"]
        rain=list(TramDoMuaVrain.objects.order_by("Thoi_gian").values("Thoi_gian","sync_status",*rain_fields))
        rain_dates=Counter(row["Thoi_gian"].astimezone(VN).date() for row in rain)
        events=candidate_events(hydro,options["threshold"],options["bridge_days"])
        overlap=sorted({day for day,value in hydro.items() if finite(value) is not None}&set(rain_dates))
        snapshots=SongHinhRealtimeSnapshot.objects.aggregate(rows=Count("id"),first=Min("time_stamp"),last=Max("time_stamp"),qve_nonnull=Count("qve_tinh_toan"))
        aliases=[]
        for code in ["957833","036606","036605"]:
            station=VrainStation.objects.filter(provider="vrain",source_station_code=code).first()
            stats=VrainSourceSample.objects.filter(station=station).aggregate(samples=Count("id"),first=Min("source_timestamp"),last=Max("source_timestamp")) if station else {}
            aliases.append({"code":code,"present_in_catalog":bool(station),"enabled":station.enabled if station else None,"name":station.name if station else None,**stats})
        years={str(y):{"days_above_threshold":sum(e["days_above_threshold"] for e in candidate_events({d:v for d,v in hydro.items() if d.year==y},options["threshold"],options["bridge_days"])),"events_starting_in_year":sum(e["start"].year==y for e in events)} for y in sorted(set(d.year for d in hydro))}
        return {"generated_at":timezone.now(),"plant":"songhinh","database_vendor":connection.vendor,"read_only":True,
                "interpretation":"Retrospective audit only. Daily means, units, time boundaries, source provenance and operational availability are unverified; candidate events are not verified floods.",
                "daily_hydrology":{"first":min(hydro,default=None),"last":max(hydro,default=None),"distribution":distribution(hydro.values()),"duplicate_days_excluded":hydro_duplicates},
                "daily_production":{"first":min(production,default=None),"last":max(production,default=None),"distribution":distribution(production.values()),"duplicate_days_excluded":production_duplicates},
                "source_comparison":compare_daily(hydro,production),
                "candidate_events":{"threshold_exclusive":options["threshold"],"bridge_days":options["bridge_days"],"missing_days_break_events":True,"count":len(events),"by_year":years,"events":events},
                "rain_daily":{"rows":len(rain),"unique_dates":len(rain_dates),"duplicate_days":sum(n>1 for n in rain_dates.values()),"sync_status_counts":dict(Counter(r["sync_status"] for r in rain)),"common_qve_dates":len(overlap),"first_common":overlap[0] if overlap else None,"last_common":overlap[-1] if overlap else None,"fields":{field:distribution(r[field] for r in rain) for field in rain_fields}},
                "snapshots":snapshots,"station_alias_review":{"stations":aliases,"warning":"Presence/absence does not establish alias equivalence. Legacy daily Xa_Ea_M_doan cannot identify which source code contributed to historical totals. Never merge 036605 with 036606."}}
