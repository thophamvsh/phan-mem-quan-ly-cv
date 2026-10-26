"""Export a consistent, read-only snapshot for offline SH experiments."""
import json
from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand,CommandError
from django.db import connection,transaction
from django.utils import timezone


class Command(BaseCommand):
    help="Export SH approved-target candidates, production Qcm and daily rain; no writes or external calls."

    def add_arguments(self,parser):
        parser.add_argument("--output",required=True,help="New JSON file; refuses overwrite")

    def handle(self,*args,**options):
        from pathlib import Path
        from thongsothuyvan.models import ThongSoThuyVanThucTe,ThongsoSanxuat,TramDoMuaVrain
        from thongsothuyvan.inflow_forecasting import RAIN_FIELDS
        if connection.vendor!="postgresql":
            raise CommandError("This snapshot exporter requires PostgreSQL read-only transaction")
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            data={"schema_version":"sh-source-v1","exported_at":timezone.now().isoformat(),"plant":"songhinh","timezone":"Asia/Ho_Chi_Minh","read_only":True,
                  "qve_source":"ThongSoThuyVanThucTe.qve","qcm_source":"ThongsoSanxuat.cot_j",
                  "hydrology":list(ThongSoThuyVanThucTe.objects.filter(nha_may="songhinh").order_by("ngay","pk").values("id","ngay","qve","muc_nuoc_ho","created_at","updated_at")),
                  "production":list(ThongsoSanxuat.objects.filter(nha_may="songhinh").order_by("thoi_gian","pk").values("id","thoi_gian","cot_j")),
                  "rain":list(TramDoMuaVrain.objects.order_by("Thoi_gian","pk").values("id","Thoi_gian","sync_status",*RAIN_FIELDS))}
        # Output outside DB transaction; JSON contains measurements, never credentials.
        path=Path(options["output"])
        with path.open("x",encoding="utf-8") as handle:
            json.dump(data,handle,default=str,ensure_ascii=True,sort_keys=True,allow_nan=False)
        self.stdout.write(f"Exported hydrology={len(data['hydrology'])}, production={len(data['production'])}, rain={len(data['rain'])}")
