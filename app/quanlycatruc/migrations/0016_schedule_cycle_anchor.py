from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0015_adjustment_leave_types")]

    operations = [
        migrations.AddField(
            model_name="lichtrucca",
            name="che_do_sinh_chu_ky",
            field=models.CharField(
                choices=[
                    ("tiep_noi", "Nối tiếp lịch tháng trước"),
                    ("moc_tuy_chon", "Chọn mốc chu kỳ"),
                ],
                default="tiep_noi",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="lichtrucca", name="ngay_moc_chu_ky",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lichtrucca", name="vi_tri_moc_hanh_chinh",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lichtrucca", name="vi_tri_moc_van_hanh",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
