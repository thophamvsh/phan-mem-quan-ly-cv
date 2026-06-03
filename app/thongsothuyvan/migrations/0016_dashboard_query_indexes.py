from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("thongsothuyvan", "0015_thongsothuyvancaidat"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="thongsosanxuat",
            index=models.Index(
                fields=["nha_may", "-thoi_gian"],
                name="tsx_plant_time_desc_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="thongsogiophat",
            index=models.Index(
                fields=["nha_may", "ngay"],
                name="tgp_plant_day_idx",
            ),
        ),
    ]
