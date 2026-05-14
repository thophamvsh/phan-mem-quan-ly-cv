from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("thongsothuyvan", "0013_nullable_realtime_snapshot_capacity"),
    ]

    operations = [
        migrations.AddField(
            model_name="realtimeupdatestate",
            name="last_hourly_slot",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
