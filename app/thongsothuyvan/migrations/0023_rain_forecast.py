import django.db.models.deletion
from django.db import migrations, models


def seed(apps, schema_editor):
    Location = apps.get_model("thongsothuyvan", "RainForecastLocation")
    rows = [
        ("songhinh", "songhinh", "Sông Hinh — Đập Tràn", "036604", "12.926840", "108.946392", "Dự báo tại trạm Đập Tràn, không phải mưa bình quân lưu vực."),
        ("vinhson_a", "vinhson", "Hồ A", "036616", "14.365095", "108.694488", "Trạm cửa nhận nước hồ A."),
        ("vinhson_b", "vinhson", "Trạm Hồ B", "036617", "14.358556", "108.568786", "VRAIN ghi địa chỉ UBND xã Sơn Lang; chưa xác nhận đây là tọa độ đập hồ B."),
        ("vinhson_c", "vinhson", "Hồ C", "036618", "14.424164", "108.444031", "Trạm đập hồ C."),
    ]
    for code, plant, name, station, lat, lon, note in rows:
        Location.objects.using(schema_editor.connection.alias).get_or_create(code=code, defaults={
            "plant": plant, "name": name, "station_code": station,
            "latitude": lat, "longitude": lon, "note": note,
        })


class Migration(migrations.Migration):
    dependencies = [("thongsothuyvan", "0022_realtime_calculated_inflow")]
    operations = [
        migrations.CreateModel(name="RainForecastLocation", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("code", models.CharField(max_length=40, unique=True)),
            ("plant", models.CharField(max_length=30)),
            ("name", models.CharField(max_length=120)),
            ("station_code", models.CharField(blank=True, max_length=20)),
            ("latitude", models.DecimalField(max_digits=9, decimal_places=6)),
            ("longitude", models.DecimalField(max_digits=9, decimal_places=6)),
            ("enabled", models.BooleanField(default=True)),
            ("note", models.CharField(blank=True, max_length=255)),
        ]),
        migrations.CreateModel(name="RainForecastLock", fields=[
            ("name", models.CharField(max_length=40, primary_key=True, serialize=False)),
            ("token", models.CharField(max_length=36)), ("expires_at", models.DateTimeField()),
        ]),
        migrations.CreateModel(name="RainForecastRevision", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("received_at", models.DateTimeField()),
            ("source_issued_at", models.DateTimeField(null=True, blank=True)),
            ("provider", models.CharField(max_length=30, default="open-meteo")),
            ("fingerprint", models.CharField(max_length=64)), ("data", models.JSONField()),
            ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="revisions", to="thongsothuyvan.rainforecastlocation")),
        ]),
        migrations.CreateModel(name="RainForecastFetch", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("started_at", models.DateTimeField()), ("finished_at", models.DateTimeField(null=True)),
            ("status", models.CharField(max_length=20, default="running")),
            ("error_code", models.CharField(max_length=80, blank=True)),
            ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="fetches", to="thongsothuyvan.rainforecastlocation")),
            ("revision", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to="thongsothuyvan.rainforecastrevision")),
        ]),
        migrations.AddIndex(model_name="rainforecastrevision", index=models.Index(fields=["location", "-received_at"], name="rain_rev_location_time")),
        migrations.AddIndex(model_name="rainforecastfetch", index=models.Index(fields=["location", "-started_at"], name="rain_fetch_location_time")),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
