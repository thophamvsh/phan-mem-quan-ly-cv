from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("nhatkyvanhanh", "0004_nhatkysukien_nguoi_tao_and_ghi_nhan_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="nhatkysukien",
            name="chu_ky_nguoi_xac_nhan_xu_ly",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="operations/nhat_ky_su_kien/chu_ky/xac_nhan/",
            ),
        ),
        migrations.AddField(
            model_name="nhatkysukien",
            name="nguoi_xac_nhan_xu_ly",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="nhat_ky_su_kien_da_xac_nhan_xu_ly",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
