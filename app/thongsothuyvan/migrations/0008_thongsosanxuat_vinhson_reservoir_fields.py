from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("thongsothuyvan", "0007_thongsosanxuat_mucnuoc_gioihan_tuan_ho_a_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="thongsosanxuat",
            name="mucnuoc_thuongluu_ho_b",
            field=models.FloatField(blank=True, null=True, verbose_name="Mực nước thượng lưu hồ B (m)"),
        ),
        migrations.AddField(
            model_name="thongsosanxuat",
            name="mucnuoc_thuongluu_ho_c",
            field=models.FloatField(blank=True, null=True, verbose_name="Mực nước thượng lưu hồ C (m)"),
        ),
        migrations.AddField(
            model_name="thongsosanxuat",
            name="luuluong_ve_ho_b",
            field=models.FloatField(blank=True, null=True, verbose_name="Lưu lượng nước về hồ B (m3/s)"),
        ),
        migrations.AddField(
            model_name="thongsosanxuat",
            name="luuluong_ve_ho_c",
            field=models.FloatField(blank=True, null=True, verbose_name="Lưu lượng nước về hồ C (m3/s)"),
        ),
    ]
