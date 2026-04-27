from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_nguoi_tao(apps, schema_editor):
    KhacPhucSuKien = apps.get_model("nhatkyvanhanh", "KhacPhucSuKien")

    for khac_phuc in KhacPhucSuKien.objects.select_related("su_kien").filter(nguoi_tao__isnull=True):
        su_kien = khac_phuc.su_kien
        nguoi_tao_id = (
            khac_phuc.ben_xu_ly_su_kien_thiet_bi_id
            or su_kien.nguoi_tao_id
            or su_kien.ben_ghi_nhan_su_kien_id
        )
        if nguoi_tao_id:
            khac_phuc.nguoi_tao_id = nguoi_tao_id
            khac_phuc.save(update_fields=["nguoi_tao"])


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("nhatkyvanhanh", "0013_backfill_factory_scope_again"),
    ]

    operations = [
        migrations.AddField(
            model_name="khacphucsukien",
            name="nguoi_tao",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="khac_phuc_su_kien_da_tao",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_nguoi_tao, migrations.RunPython.noop),
    ]
