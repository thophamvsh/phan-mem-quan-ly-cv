from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("quanlyvanhanh", "0025_auto_20260611_1511"),
    ]

    operations = [
        UnaccentExtension(),
    ]
