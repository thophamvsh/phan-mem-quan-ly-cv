from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0016_schedule_cycle_anchor")]

    operations = [
        migrations.AddField(
            model_name="lichtrucca", name="chu_ky_hanh_chinh_tuy_chon",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lichtrucca", name="chu_ky_van_hanh_tuy_chon",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
