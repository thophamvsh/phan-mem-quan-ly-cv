from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("thongsothuyvan", "0019_auto_20260718_1625"),
    ]

    operations = [
        migrations.AddField(
            model_name="thongsothuyvancaidat",
            name="quy",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="thongsothuyvancaidat",
            name="sanluong_kehoach_quy",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="thongsothuyvancaidat",
            name="loai",
            field=models.CharField(
                choices=[
                    ("annual", "Ke hoach nam"),
                    ("monthly", "Ke hoach thang"),
                    ("quarterly", "Kế hoạch quý"),
                    ("weekly", "MNGH tuan"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="thongsothuyvancaidat",
            unique_together={
                ("nha_may", "nam", "loai", "thang", "quy", "tuan")
            },
        ),
    ]
