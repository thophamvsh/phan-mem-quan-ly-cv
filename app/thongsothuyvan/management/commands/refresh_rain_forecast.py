from django.core.management.base import BaseCommand, CommandError
from thongsothuyvan.rain_forecast_services import refresh_forecasts


class Command(BaseCommand):
    help = "Fetch configured forecast points (requires RAIN_FORECAST_ENABLED)."

    def handle(self, *args, **options):
        result = refresh_forecasts()
        self.stdout.write(str(result))
        if result["status"] == "partial":
            raise CommandError("Some forecast locations failed; inspect RainForecastFetch")
