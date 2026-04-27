from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nhatkyvanhanh", "0002_alter_nhatkysukien_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="nhatkysukien",
            name="trang_thai",
            field=models.CharField(
                choices=[
                    ("chua_xu_ly_xong", "Chua xu ly xong"),
                    ("dang_xu_ly", "Dang xu ly"),
                    ("xu_ly_xong", "Xu ly xong"),
                ],
                default="chua_xu_ly_xong",
                max_length=32,
            ),
        ),
    ]
