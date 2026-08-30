from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("nhatkyvanhanh", "0046_sogiaonhancavh_loai_thoi_gian_truc_and_more"),
        ("quanlycatruc", "0017_schedule_custom_cycles"),
    ]

    operations = [
        migrations.AddField(
            model_name="sogiaonhancavh",
            name="lich_truc_nguon",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="so_giao_nhan_ca_vh", to="quanlycatruc.lichtrucca", verbose_name="Lịch trực nguồn"),
        ),
        migrations.AddField(
            model_name="sogiaonhancavh",
            name="ngay_truc_ca_nguon",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="so_giao_nhan_ca_vh", to="quanlycatruc.ngaytrucca", verbose_name="Ngày trực ca nguồn"),
        ),
        migrations.AddField(
            model_name="sogiaonhancavh",
            name="phien_ban_lich_nguon",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sogiaonhancavh",
            name="dong_bo_bien_che_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
