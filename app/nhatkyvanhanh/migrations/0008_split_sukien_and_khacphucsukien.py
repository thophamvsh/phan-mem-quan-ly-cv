from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def forward_copy_data(apps, schema_editor):
    OldNhatKySuKien = apps.get_model("nhatkyvanhanh", "NhatKySuKien")
    SuKien = apps.get_model("nhatkyvanhanh", "SuKien")
    KhacPhucSuKien = apps.get_model("nhatkyvanhanh", "KhacPhucSuKien")

    for old in OldNhatKySuKien.objects.all():
        su_kien = SuKien.objects.create(
            id=old.id,
            created_at=old.created_at,
            updated_at=old.updated_at,
            thoi_gian_xay_ra=old.thoi_gian_xay_ra,
            ten_he_thong_thiet_bi=old.ten_he_thong_thiet_bi,
            hien_tuong_dien_bien=old.hien_tuong_dien_bien,
            phan_tich_nguyen_nhan=old.phan_tich_nguyen_nhan,
            qua_trinh_kiem_tra=old.qua_trinh_kiem_tra,
            de_xuat_khac_phuc=old.de_xuat_khac_phuc,
            bao_cho=old.bao_cho,
            hinh_anh_truoc_su_co=old.hinh_anh_truoc_su_co,
            chu_ky_ben_ghi_nhan_su_kien=old.chu_ky_ben_ghi_nhan_su_kien,
            trang_thai=old.trang_thai,
            nguoi_tao_id=old.nguoi_tao_id,
            ben_ghi_nhan_su_kien_id=old.ben_ghi_nhan_su_kien_id,
        )

        has_khac_phuc_data = any(
            [
                old.qua_trinh_xu_ly,
                old.thoi_gian_xu_ly,
                old.ket_qua_kiem_tra_nguyen_nhan,
                old.noi_dung_xu_ly_khac_phuc,
                old.de_xuat_lien_quan,
                old.ket_qua_sau_xu_ly,
                old.lich_su_xu_ly_tiep_tuc,
                old.hinh_anh_sau_xu_ly,
                old.chu_ky_ben_xu_ly_su_kien_thiet_bi,
                old.chu_ky_nguoi_xac_nhan_xu_ly,
                old.chu_ky_nguoi_xac_nhan_lan_cuoi,
                old.ben_xu_ly_su_kien_thiet_bi_id,
                old.nguoi_xac_nhan_xu_ly_id,
                old.nguoi_xac_nhan_lan_cuoi_id,
            ]
        )

        if has_khac_phuc_data:
            KhacPhucSuKien.objects.create(
                created_at=old.created_at,
                updated_at=old.updated_at,
                su_kien=su_kien,
                qua_trinh_xu_ly=old.qua_trinh_xu_ly,
                thoi_gian_xu_ly=old.thoi_gian_xu_ly,
                ket_qua_kiem_tra_nguyen_nhan=old.ket_qua_kiem_tra_nguyen_nhan,
                noi_dung_xu_ly_khac_phuc=old.noi_dung_xu_ly_khac_phuc,
                de_xuat_lien_quan=old.de_xuat_lien_quan,
                ket_qua_sau_xu_ly=old.ket_qua_sau_xu_ly,
                lich_su_xu_ly_tiep_tuc=old.lich_su_xu_ly_tiep_tuc,
                hinh_anh_sau_xu_ly=old.hinh_anh_sau_xu_ly,
                chu_ky_ben_xu_ly_su_kien_thiet_bi=old.chu_ky_ben_xu_ly_su_kien_thiet_bi,
                chu_ky_nguoi_xac_nhan_xu_ly=old.chu_ky_nguoi_xac_nhan_xu_ly,
                chu_ky_nguoi_xac_nhan_lan_cuoi=old.chu_ky_nguoi_xac_nhan_lan_cuoi,
                ben_xu_ly_su_kien_thiet_bi_id=old.ben_xu_ly_su_kien_thiet_bi_id,
                nguoi_xac_nhan_xu_ly_id=old.nguoi_xac_nhan_xu_ly_id,
                nguoi_xac_nhan_lan_cuoi_id=old.nguoi_xac_nhan_lan_cuoi_id,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("nhatkyvanhanh", "0007_nhatkysukien_xac_nhan_lan_cuoi"),
    ]

    operations = [
        migrations.CreateModel(
            name="SuKien",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("thoi_gian_xay_ra", models.DateTimeField()),
                ("ten_he_thong_thiet_bi", models.CharField(max_length=255)),
                ("hien_tuong_dien_bien", models.TextField()),
                ("phan_tich_nguyen_nhan", models.TextField(blank=True)),
                ("qua_trinh_kiem_tra", models.TextField(blank=True)),
                ("de_xuat_khac_phuc", models.TextField(blank=True)),
                ("bao_cho", models.CharField(blank=True, max_length=255)),
                ("hinh_anh_truoc_su_co", models.ImageField(blank=True, null=True, upload_to="operations/nhat_ky_su_kien/truoc_su_co/")),
                ("chu_ky_ben_ghi_nhan_su_kien", models.ImageField(blank=True, null=True, upload_to="operations/nhat_ky_su_kien/chu_ky/ghi_nhan/")),
                ("trang_thai", models.CharField(choices=[("chua_xu_ly_xong", "Chua xu ly xong"), ("dang_xu_ly", "Dang xu ly"), ("xu_ly_xong", "Xu ly xong")], default="chua_xu_ly_xong", max_length=32)),
                ("ben_ghi_nhan_su_kien", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="su_kien_da_ghi_nhan", to=settings.AUTH_USER_MODEL)),
                ("nguoi_tao", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="su_kien_da_tao", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Su kien",
                "verbose_name_plural": "Su kien",
                "ordering": ["-thoi_gian_xay_ra", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="KhacPhucSuKien",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("qua_trinh_xu_ly", models.TextField(blank=True)),
                ("thoi_gian_xu_ly", models.DateTimeField(blank=True, null=True)),
                ("ket_qua_kiem_tra_nguyen_nhan", models.TextField(blank=True)),
                ("noi_dung_xu_ly_khac_phuc", models.TextField(blank=True)),
                ("de_xuat_lien_quan", models.TextField(blank=True)),
                ("ket_qua_sau_xu_ly", models.TextField(blank=True)),
                ("lich_su_xu_ly_tiep_tuc", models.TextField(blank=True)),
                ("hinh_anh_sau_xu_ly", models.ImageField(blank=True, null=True, upload_to="operations/nhat_ky_su_kien/sau_xu_ly/")),
                ("chu_ky_ben_xu_ly_su_kien_thiet_bi", models.ImageField(blank=True, null=True, upload_to="operations/nhat_ky_su_kien/chu_ky/xu_ly/")),
                ("chu_ky_nguoi_xac_nhan_xu_ly", models.ImageField(blank=True, null=True, upload_to="operations/nhat_ky_su_kien/chu_ky/xac_nhan/")),
                ("chu_ky_nguoi_xac_nhan_lan_cuoi", models.ImageField(blank=True, null=True, upload_to="operations/nhat_ky_su_kien/chu_ky/xac_nhan_lan_cuoi/")),
                ("ben_xu_ly_su_kien_thiet_bi", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="khac_phuc_su_kien_da_xu_ly", to=settings.AUTH_USER_MODEL)),
                ("nguoi_xac_nhan_lan_cuoi", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="khac_phuc_su_kien_da_xac_nhan_lan_cuoi", to=settings.AUTH_USER_MODEL)),
                ("nguoi_xac_nhan_xu_ly", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="khac_phuc_su_kien_da_xac_nhan_xu_ly", to=settings.AUTH_USER_MODEL)),
                ("su_kien", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="khac_phuc_su_kiens", to="nhatkyvanhanh.sukien")),
            ],
            options={
                "verbose_name": "Khac phuc su kien",
                "verbose_name_plural": "Khac phuc su kien",
                "ordering": ["-thoi_gian_xu_ly", "-created_at"],
            },
        ),
        migrations.RunPython(forward_copy_data, migrations.RunPython.noop),
        migrations.DeleteModel(
            name="NhatKySuKien",
        ),
    ]
