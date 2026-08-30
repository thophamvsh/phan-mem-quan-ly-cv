from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0014_alter_phuonganphancongca_lich_truc_and_more")]

    operations = [
        migrations.AlterField(
            model_name="dieuchinhnhansucatruc",
            name="loai_dieu_chinh",
            field=models.CharField(
                choices=[
                    ("doi_ca", "Đổi ca"), ("truc_thay", "Trực thay"),
                    ("nghi_phep", "Nghỉ phép"), ("nghi_bu", "Nghỉ bù"),
                    ("dieu_dong", "Điều động"),
                ], max_length=20,
            ),
        ),
    ]
