from django.db import migrations


def clear_premature_signatures(apps, schema_editor):
    SogiaonhancaVH = apps.get_model("nhatkyvanhanh", "SogiaonhancaVH")
    SogiaonhancaVH.objects.filter(nhan_ca_ky_at__isnull=True).update(
        chu_ky_user_giao_ca="",
        chu_ky_user_nhan_ca="",
    )
    SogiaonhancaVH.objects.filter(user_nhan_ca__isnull=True).update(
        chu_ky_user_giao_ca="",
        chu_ky_user_nhan_ca="",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("nhatkyvanhanh", "0020_alter_sogiaonhancavh_options_and_more"),
    ]

    operations = [
        migrations.RunPython(clear_premature_signatures, migrations.RunPython.noop),
    ]
