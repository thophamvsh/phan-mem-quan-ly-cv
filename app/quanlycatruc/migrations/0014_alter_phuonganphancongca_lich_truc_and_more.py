from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0013_daily_admin_staffing")]

    operations = [
        migrations.AlterField(
            model_name="phuonganphancongca",
            name="lich_truc",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="phuong_an_phan_cong",
                to="quanlycatruc.lichtrucca",
            ),
        ),
        migrations.AlterField(
            model_name="lichtrucca",
            name="lich_thang_goc",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lich_chuyen_de",
                to="quanlycatruc.lichtrucca",
            ),
        ),
    ]
