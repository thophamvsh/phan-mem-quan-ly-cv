from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0012_assignment_plan_schedule")]

    operations = [
        migrations.AddField(
            model_name="ngaytrucca",
            name="che_do_phan_cong_hc",
            field=models.CharField(
                choices=[
                    ("theo_phuong_an", "Theo phương án chung"),
                    ("tuy_chinh", "Tùy chỉnh theo ngày"),
                    ("khong_bo_tri", "Không bố trí nhân sự"),
                ],
                default="theo_phuong_an", max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="PhanCongNhanSuHCNgay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("vai_tro", models.CharField(choices=[("truong_ca", "Trưởng ca"), ("truc_chinh", "Trực chính"), ("truc_phu", "Trực phụ"), ("ky_thuat_vien", "Kỹ thuật viên"), ("nhan_vien", "Nhân viên")], default="nhan_vien", max_length=20)),
                ("thu_tu", models.PositiveSmallIntegerField(default=1)),
                ("ngay_truc", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="phan_cong_hc", to="quanlycatruc.ngaytrucca")),
                ("nhan_su", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="phan_cong_hc_theo_ngay", to="quanlycatruc.nhansu")),
            ],
            options={"verbose_name": "Phân công KT-HC theo ngày", "verbose_name_plural": "Phân công KT-HC theo ngày", "ordering": ["thu_tu", "nhan_su__ho_ten"]},
        ),
        migrations.AddConstraint(
            model_name="phancongnhansuhcngay",
            constraint=models.UniqueConstraint(fields=("ngay_truc", "nhan_su"), name="uq_phanconghc_ngay_nhansu"),
        ),
    ]
