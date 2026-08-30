from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0009_phuonganphancongca_chitietphuonganphancongca_and_more")]

    operations = [
        migrations.AddField(model_name="lichtrucca", name="loai_lich", field=models.CharField(choices=[("thang", "Lịch tháng"), ("chuyen_de", "Lịch chuyên đề")], default="thang", max_length=20)),
        migrations.AddField(model_name="lichtrucca", name="ten_lich", field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name="lichtrucca", name="tu_ngay", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="lichtrucca", name="den_ngay", field=models.DateField(blank=True, null=True)),
        migrations.AddField(model_name="lichtrucca", name="lich_thang_goc", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="lich_chuyen_de", to="quanlycatruc.lichtrucca")),
        migrations.AddField(model_name="ngaytrucca", name="ngay_am", field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="ngaytrucca", name="thang_am", field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="ngaytrucca", name="nam_am", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="ngaytrucca", name="la_thang_nhuan", field=models.BooleanField(default=False)),
    ]
