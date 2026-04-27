from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nhatkyvanhanh", "0005_nhatkysukien_xac_nhan_xu_ly"),
    ]

    operations = [
        migrations.AddField(
            model_name="nhatkysukien",
            name="lich_su_xu_ly_tiep_tuc",
            field=models.TextField(blank=True),
        ),
    ]
