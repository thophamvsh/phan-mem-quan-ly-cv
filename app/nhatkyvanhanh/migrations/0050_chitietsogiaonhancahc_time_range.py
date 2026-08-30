from django.db import migrations, models


def copy_legacy_time(apps, schema_editor):
    Detail = apps.get_model("nhatkyvanhanh", "ChiTietSoGiaoNhanCaHC")
    Detail.objects.filter(thoi_gian_bat_dau__isnull=True).update(
        thoi_gian_bat_dau=models.F("thoi_gian")
    )


class Migration(migrations.Migration):
    dependencies = [("nhatkyvanhanh", "0049_sogiaonhancahc_roster_source")]

    operations = [
        migrations.AddField(
            model_name="chitietsogiaonhancahc",
            name="thoi_gian_bat_dau",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chitietsogiaonhancahc",
            name="thoi_gian_ket_thuc",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(copy_legacy_time, migrations.RunPython.noop),
    ]
