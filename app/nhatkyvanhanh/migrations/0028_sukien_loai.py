from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nhatkyvanhanh", "0027_sukien_chu_ky_nguoi_chi_dao_sukien_nguoi_chi_dao"),
    ]

    operations = [
        migrations.AddField(
            model_name="sukien",
            name="loai",
            field=models.CharField(
                choices=[
                    ("khiem_khuyet", "Khiem khuyet"),
                    ("su_co", "Su co"),
                ],
                default="su_co",
                max_length=32,
            ),
        ),
    ]
