from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('nhatkyvanhanh', '0052_bangphancongnhiemvuhc_chitietnhiemvuthutrongtuan_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sochuyendoithietbituan',
            name='trang_thai',
            field=models.CharField(
                choices=[('cho_duyet', 'Chờ duyệt'), ('da_duyet', 'Đã duyệt')],
                default='cho_duyet',
                max_length=20,
                verbose_name='Trạng thái',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoithietbituan',
            name='nguoi_duyet',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='so_chuyen_doi_tuan_da_duyet',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Người duyệt / Trưởng ca / Quản đốc',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoithietbituan',
            name='duyet_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Thời điểm duyệt',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoithietbituan',
            name='ghi_chu_duyet',
            field=models.TextField(
                blank=True,
                verbose_name='Ý kiến phê duyệt',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoithietbituan',
            name='chu_ky_nguoi_tao',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='operations/so_chuyen_doi_tuan/chu_ky/nguoi_tao/',
                verbose_name='Chữ ký người lập sổ',
            ),
        ),
        migrations.AddField(
            model_name='sochuyendoithietbituan',
            name='chu_ky_nguoi_duyet',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='operations/so_chuyen_doi_tuan/chu_ky/nguoi_duyet/',
                verbose_name='Chữ ký người duyệt',
            ),
        ),
    ]
