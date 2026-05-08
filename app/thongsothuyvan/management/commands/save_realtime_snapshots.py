from django.core.management.base import BaseCommand

from thongsothuyvan.models import RealtimeUpdateState
from thongsothuyvan.realtime_services import save_all_realtime_snapshots


class Command(BaseCommand):
    help = "Luu snapshot realtime Song Hinh va Vinh Son neu che do tu dong dang bat."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bo qua trang thai auto_update_enabled va luu ngay.",
        )

    def handle(self, *args, **options):
        state = RealtimeUpdateState.get_solo()
        if not state.auto_update_enabled and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "Tu dong cap nhat realtime dang tat. Dung --force neu muon luu thu cong."
                )
            )
            return

        state, results = save_all_realtime_snapshots(is_manual=options["force"])
        for result in results:
            if result.saved:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{result.plant}: da luu snapshot #{result.snapshot_id}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"{result.plant}: {result.error}")
                )

        if state.last_error:
            raise SystemExit(1)
