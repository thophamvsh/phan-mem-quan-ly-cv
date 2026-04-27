from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("nhatkyvanhanh", "0006_nhatkysukien_lich_su_xu_ly_tiep_tuc"),
    ]

    operations = [
        migrations.AddField(
            model_name="nhatkysukien",
            name="chu_ky_nguoi_xac_nhan_lan_cuoi",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="operations/nhat_ky_su_kien/chu_ky/xac_nhan_lan_cuoi/",
            ),
        ),
        migrations.AddField(
            model_name="nhatkysukien",
            name="nguoi_xac_nhan_lan_cuoi",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="nhat_ky_su_kien_da_xac_nhan_lan_cuoi",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
