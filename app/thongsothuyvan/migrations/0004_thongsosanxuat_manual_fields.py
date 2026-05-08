from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("thongsothuyvan", "0003_alter_thongsosanxuat_cot_c"),
    ]

    operations = [
        migrations.AddField(
            model_name="thongsosanxuat",
            name="sanluong_kh_thang",
            field=models.FloatField(
                blank=True,
                null=True,
                verbose_name="Sản lượng kế hoạch tháng",
            ),
        ),
        migrations.AddField(
            model_name="thongsosanxuat",
            name="mucnuoc_gioihan_tuan",
            field=models.FloatField(
                blank=True,
                null=True,
                verbose_name="Mực nước giới hạn tuần",
            ),
        ),
    ]
