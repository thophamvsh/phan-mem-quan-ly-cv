from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0011_shift_schedule_groups")]
    operations = [
        migrations.AddField(
            model_name="phuonganphancongca",
            name="lich_truc",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="phuong_an_phan_cong",
                to="quanlycatruc.lichtrucca",
            ),
        ),
    ]
