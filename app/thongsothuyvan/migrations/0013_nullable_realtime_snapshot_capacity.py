from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("thongsothuyvan", "0012_alter_vinhsonrealtimesnapshot_mntla_td"),
    ]

    operations = [
        migrations.AlterField(
            model_name="songhinhrealtimesnapshot",
            name="dung_tich_ho",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="songhinhrealtimesnapshot",
            name="dung_tich_phong_lu",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="vinhsonrealtimesnapshot",
            name="dung_tich_ho_a",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="vinhsonrealtimesnapshot",
            name="dung_tich_ho_b",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="vinhsonrealtimesnapshot",
            name="dung_tich_ho_c",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
