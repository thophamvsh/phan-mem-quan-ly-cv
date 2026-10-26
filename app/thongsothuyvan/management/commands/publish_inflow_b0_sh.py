import json
from django.core.management.base import BaseCommand,CommandError
from thongsothuyvan.inflow_b0_services import publish_b0


class Command(BaseCommand):
    help="Publish one prospective experimental B0 for SH tomorrow. Manual invocation overrides the scheduler flag; never backdates."

    def add_arguments(self,parser):
        parser.add_argument("--dry-run",action="store_true",help="Preview current input without writing forecast or run")

    def handle(self,*args,**options):
        result=publish_b0(manual=True,dry_run=options["dry_run"])
        self.stdout.write(json.dumps(result,ensure_ascii=True))
        if result["status"] in {"unavailable","error"}:raise CommandError("B0 not published; inspect input freshness or InflowB0Run")
