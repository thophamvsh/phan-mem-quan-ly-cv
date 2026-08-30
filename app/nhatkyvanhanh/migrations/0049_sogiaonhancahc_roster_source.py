from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("nhatkyvanhanh", "0048_sogiaonhancavh_admin_shift_source")]

    operations = [
        migrations.AddField(
            model_name="sogiaonhancahc", name="lich_truc_nguon",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="so_giao_nhan_ca_hc", to="quanlycatruc.lichtrucca", verbose_name="Lịch trực nguồn"),
        ),
        migrations.AddField(
            model_name="sogiaonhancahc", name="ngay_truc_ca_nguon",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="so_giao_nhan_ca_hc", to="quanlycatruc.ngaytrucca", verbose_name="Ngày trực ca nguồn"),
        ),
        migrations.AddField(model_name="sogiaonhancahc", name="phien_ban_lich_nguon", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="sogiaonhancahc", name="dong_bo_bien_che_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="sogiaonhancahc", name="nguoi_tao_thuoc_bien_che", field=models.BooleanField(blank=True, null=True)),
    ]
