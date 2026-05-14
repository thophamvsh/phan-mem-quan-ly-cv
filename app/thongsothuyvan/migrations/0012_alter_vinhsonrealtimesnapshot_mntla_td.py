from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("thongsothuyvan", "0011_tramdomuavrain"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vinhsonrealtimesnapshot",
            name="mntla_td",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
