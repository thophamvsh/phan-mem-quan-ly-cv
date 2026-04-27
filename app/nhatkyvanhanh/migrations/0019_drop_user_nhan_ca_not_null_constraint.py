from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("nhatkyvanhanh", "0018_allow_so_giao_nhan_ca_user_nhan_ca_null"),
    ]

    operations = [
        migrations.RunSQL(sql=migrations.RunSQL.noop, reverse_sql=migrations.RunSQL.noop),
    ]
