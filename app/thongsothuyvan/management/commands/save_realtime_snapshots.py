from django.core.management.base import BaseCommand

from thongsothuyvan.realtime_services import save_all_realtime_snapshots


class Command(BaseCommand):
    help = "Luu snapshot realtime Song Hinh va Vinh Son."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Danh dau day la lan luu thu cong.",
        )

    def handle(self, *args, **options):
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
