from django.db import migrations, models


def backfill_chuc_danh_nguoi_tao(apps, schema_editor):
    DienBienSuKien = apps.get_model("nhatkyvanhanh", "DienBienSuKien")
    UserProfile = apps.get_model("core", "UserProfile")

    chuc_danh_by_user_id = {
        profile.user_id: profile.chuc_danh or ""
        for profile in UserProfile.objects.exclude(user_id__isnull=True)
    }

    for dien_bien in DienBienSuKien.objects.filter(chuc_danh_nguoi_tao=""):
        chuc_danh = chuc_danh_by_user_id.get(dien_bien.nguoi_tao_id, "")
        if chuc_danh:
            dien_bien.chuc_danh_nguoi_tao = chuc_danh
            dien_bien.save(update_fields=["chuc_danh_nguoi_tao"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_auto_20251004_0318"),
        ("nhatkyvanhanh", "0015_dienbiensukien"),
    ]

    operations = [
        migrations.AddField(
            model_name="dienbiensukien",
            name="chuc_danh_nguoi_tao",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(backfill_chuc_danh_nguoi_tao, migrations.RunPython.noop),
    ]
