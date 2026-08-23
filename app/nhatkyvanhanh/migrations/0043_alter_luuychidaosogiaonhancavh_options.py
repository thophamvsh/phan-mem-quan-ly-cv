from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("nhatkyvanhanh", "0042_event_multiple_images"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="luuychidaosogiaonhancavh",
            options={
                "ordering": ["thoi_gian", "created_at"],
                "verbose_name": "Lưu ý chỉ đạo sổ giao nhận ca vận hành",
                "verbose_name_plural": "Lưu ý chỉ đạo sổ giao nhận ca vận hành",
            },
        ),
    ]
