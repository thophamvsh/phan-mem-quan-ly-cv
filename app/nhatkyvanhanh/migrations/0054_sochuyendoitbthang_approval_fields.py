from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('nhatkyvanhanh', '0053_sochuyendoithietbituan_approval_and_locking'),
    ]

    operations = [
        migrations.AddField(
            model_name='sochuyendoitbthang',
            name='trang_thai',
            field=models.CharField(
                choices=[('cho_duyet', 'Chờ duyệt'), ('da_duyet', 'Đã duyệt')],
                default='cho_duyet',
                max_length=20,
                verbose_name='Trạng thái',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoitbthang',
            name='nguoi_duyet',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='so_chuyen_doi_tb_thang_da_duyet',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Người duyệt',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoitbthang',
            name='duyet_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Thời gian duyệt',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoitbthang',
            name='ghi_chu_duyet',
            field=models.TextField(
                blank=True,
                verbose_name='Ghi chú duyệt',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoitbthang',
            name='chu_ky_nguoi_tao',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='signatures/so_chuyen_doi_thang/nguoi_tao/',
                verbose_name='Chữ ký người tạo',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoitbthang',
            name='chu_ky_nguoi_duyet',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='signatures/so_chuyen_doi_thang/nguoi_duyet/',
                verbose_name='Chữ ký người duyệt',
            ),
        ),
    ]
