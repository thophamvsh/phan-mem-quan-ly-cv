from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("thongsothuyvan", "0021_vrain_daily_sync_status")]
    operations = [
        migrations.AddField(model_name=model, name=name, field=field)
        for model in ("songhinhrealtimesnapshot", "vinhsonrealtimesnapshot")
        for name, field in (
            ("qve_tinh_toan", models.FloatField(null=True, blank=True)),
            ("qve_calculation", models.JSONField(default=dict, blank=True)),
        )
    ]
