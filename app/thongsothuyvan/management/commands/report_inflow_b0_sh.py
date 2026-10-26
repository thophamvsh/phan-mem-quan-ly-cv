import json
from django.core.management.base import BaseCommand
from thongsothuyvan.inflow_b0_services import b0_report


class Command(BaseCommand):
    help="Read B0 shadow results, scoring the latest actual revision once per forecast."

    def handle(self,*args,**options):
        self.stdout.write(json.dumps(b0_report(),ensure_ascii=True,indent=2,allow_nan=False))
