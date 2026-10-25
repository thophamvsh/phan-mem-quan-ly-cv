from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from thongsothuyvan.vrain_history_models import VrainBackfillJob
from thongsothuyvan.vrain_history_provider import VrainHistoryError
from thongsothuyvan.vrain_history_services import sync_history, advance_backfill, aligned


class Command(BaseCommand):
    help = "Capture VRAIN evidence; intervals require verified source semantics. No legacy tables are written."

    def add_arguments(self, parser):
        parser.add_argument("--start", help="Timezone-aware ISO timestamp on a 10-minute boundary")
        parser.add_argument("--end", help="Timezone-aware ISO timestamp on a 10-minute boundary")
        parser.add_argument("--backfill", action="store_true", help="Create a bounded resumable job, at most 7 days")
        parser.add_argument("--resume", type=int, help="Resume one hour of a job by ID")

    def handle(self, *args, **options):
        if options["resume"]:
            if options["start"] or options["end"] or options["backfill"]:
                raise CommandError("--resume cannot be combined with other options")
            try:
                result = advance_backfill(VrainBackfillJob.objects.get(pk=options["resume"]))
            except VrainBackfillJob.DoesNotExist:
                raise CommandError("Backfill job not found") from None
        else:
            if bool(options["start"]) != bool(options["end"]):
                raise CommandError("Supply both --start and --end")
            try:
                start = parse_datetime(options["start"]) if options["start"] else None
                end = parse_datetime(options["end"]) if options["end"] else None
                if options["start"] and (start is None or end is None):
                    raise ValueError()
            except ValueError:
                raise CommandError("Invalid ISO timestamp") from None
            if options["backfill"]:
                if not start or not end or not aligned(start) or not aligned(end) or not start < end or end-start > timedelta(days=7) or end > timezone.now():
                    raise CommandError("Backfill requires aligned aware start/end in the past, at most 7 days")
                job = VrainBackfillJob.objects.create(window_start=start, window_end=end, cursor=start)
                self.stdout.write(f"Created job {job.pk}; run --resume {job.pk} for one bounded window")
                return
            try:
                result = sync_history(start, end, manual=True)
            except VrainHistoryError as error:
                raise CommandError(str(error)) from None
        self.stdout.write(str(result))
        if result["status"] in {"error", "no_data", "locked", "partial"}:
            raise CommandError("Capture incomplete; inspect VrainSyncRun")
