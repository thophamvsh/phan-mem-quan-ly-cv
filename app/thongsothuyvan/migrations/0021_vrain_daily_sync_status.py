from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("thongsothuyvan", "0020_quarterly_production_target"),
    ]

    operations = [
        migrations.AddField(
            model_name="tramdomuavrain",
            name="sync_status",
            field=models.CharField(
                choices=[
                    ("unknown", "Chưa xác định"),
                    ("provisional", "Tạm tính"),
                    ("finalized", "Đã chốt"),
                ],
                default="unknown",
                max_length=12,
                verbose_name="Trạng thái đồng bộ",
            ),
        ),
        migrations.AddField(
            model_name="tramdomuavrain",
            name="synced_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name="Đồng bộ lúc",
            ),
        ),
    ]
