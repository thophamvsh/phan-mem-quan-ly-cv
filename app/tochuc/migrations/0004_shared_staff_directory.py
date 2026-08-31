import datetime

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("tochuc", "0003_shared_organization_directory"),
        ("quanlycatruc", "0019_move_organization_directory_state"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="NhanSu",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("updated_at", models.DateTimeField(auto_now=True)),
                        (
                            "ma_nhan_vien",
                            models.CharField(
                                blank=True,
                                max_length=50,
                                null=True,
                                unique=True,
                            ),
                        ),
                        ("ho_ten", models.CharField(max_length=150)),
                        ("chuc_danh", models.CharField(blank=True, max_length=120)),
                        ("dien_thoai", models.CharField(blank=True, max_length=30)),
                        ("tu_ngay", models.DateField(default=datetime.date.today)),
                        ("den_ngay", models.DateField(blank=True, null=True)),
                        ("dang_lam_viec", models.BooleanField(default=True)),
                        (
                            "bo_phan",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="nhan_su",
                                to="tochuc.bophan",
                            ),
                        ),
                        (
                            "don_vi",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="nhan_su",
                                to="tochuc.donvitochuc",
                            ),
                        ),
                        (
                            "user",
                            models.OneToOneField(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="nhan_su_ca_truc",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Nhân sự",
                        "verbose_name_plural": "Danh mục nhân sự",
                        "db_table": "quanlycatruc_nhansu",
                        "ordering": ["don_vi", "bo_phan", "ho_ten"],
                        "indexes": [
                            models.Index(
                                fields=["don_vi", "bo_phan", "dang_lam_viec"],
                                name="quanlycatru_don_vi__2e1cc8_idx",
                            )
                        ],
                    },
                ),
            ],
        ),
    ]
