from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("thongsothuyvan", "0002_thongsogiophat_thongsosanxuat"),
    ]

    operations = [
        migrations.AlterField(
            model_name="thongsosanxuat",
            name="cot_c",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                verbose_name="Hồ chứa",
            ),
        ),
    ]
