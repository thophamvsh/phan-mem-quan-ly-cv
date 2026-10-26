import json
from datetime import date
from django.core.management.base import BaseCommand,CommandError
from thongsothuyvan.inflow_b0_services import reconcile_b0


class Command(BaseCommand):
    help="Compare ended SH B0 targets with actual hydrology; preserve all correction revisions."

    def add_arguments(self,parser):
        parser.add_argument("--target-date",help="Optional ended target day YYYY-MM-DD")
        parser.add_argument("--limit",type=int,default=500)

    def handle(self,*args,**options):
        try:
            target=date.fromisoformat(options["target_date"]) if options["target_date"] else None
            result=reconcile_b0(manual=True,target_day=target,limit=options["limit"])
        except ValueError as error:raise CommandError(str(error)) from None
        self.stdout.write(json.dumps(result,ensure_ascii=True))
        if result["status"]=="error":raise CommandError("B0 comparison incomplete; inspect InflowB0Run")
