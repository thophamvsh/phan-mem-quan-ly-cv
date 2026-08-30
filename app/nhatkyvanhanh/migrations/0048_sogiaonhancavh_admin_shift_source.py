from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("nhatkyvanhanh", "0047_sogiaonhancavh_roster_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="sogiaonhancavh",
            name="so_giao_nhan_ca_hc_nguon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="so_giao_nhan_ca_vh_dong_bo",
                to="nhatkyvanhanh.sogiaonhancahc",
                verbose_name="Sổ giao nhận ca hành chính nguồn",
            ),
        ),
        migrations.AddField(
            model_name="sogiaonhancavh",
            name="dong_bo_truc_ktvh_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
