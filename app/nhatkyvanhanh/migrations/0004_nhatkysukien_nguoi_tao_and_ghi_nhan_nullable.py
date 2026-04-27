from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def gan_nguoi_tao_tu_ben_ghi_nhan(apps, schema_editor):
    NhatKySuKien = apps.get_model("nhatkyvanhanh", "NhatKySuKien")
    for su_kien in NhatKySuKien.objects.filter(nguoi_tao__isnull=True):
        su_kien.nguoi_tao_id = su_kien.ben_ghi_nhan_su_kien_id
        su_kien.save(update_fields=["nguoi_tao"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("nhatkyvanhanh", "0003_alter_nhatkysukien_trang_thai"),
    ]

    operations = [
        migrations.AddField(
            model_name="nhatkysukien",
            name="nguoi_tao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="nhat_ky_su_kien_da_tao",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="nhatkysukien",
            name="ben_ghi_nhan_su_kien",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="nhat_ky_su_kien_da_ghi_nhan",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            gan_nguoi_tao_tu_ben_ghi_nhan,
            migrations.RunPython.noop,
        ),
    ]
