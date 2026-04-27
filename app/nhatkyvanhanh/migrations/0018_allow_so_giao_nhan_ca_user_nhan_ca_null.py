from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("nhatkyvanhanh", "0017_sogiaonhancavh_nguoi_tao_chitietsogiaonhancavh"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="sogiaonhancavh",
            name="user_nhan_ca",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="so_giao_nhan_ca_vh_da_nhan",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
