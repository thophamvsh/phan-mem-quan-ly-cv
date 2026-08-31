import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tochuc", "0002_preserve_nha_may_permissions"),
        (
            "quanlycatruc",
            "0018_alter_donvitochuc_nha_may_alter_kiptruc_nha_may_and_more",
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="DonViToChuc",
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
                        ("ma_don_vi", models.CharField(max_length=50, unique=True)),
                        ("ten_don_vi", models.CharField(max_length=200)),
                        (
                            "loai_don_vi",
                            models.CharField(
                                choices=[
                                    ("cong_ty", "Công ty"),
                                    ("cum_nha_may", "Cụm nhà máy"),
                                    ("nha_may", "Nhà máy"),
                                    ("van_phong", "Văn phòng"),
                                    ("khac", "Khác"),
                                ],
                                default="nha_may",
                                max_length=20,
                            ),
                        ),
                        ("thu_tu", models.PositiveSmallIntegerField(default=1)),
                        ("dang_hoat_dong", models.BooleanField(default=True)),
                        (
                            "don_vi_cha",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="don_vi_con",
                                to="tochuc.donvitochuc",
                            ),
                        ),
                        (
                            "nha_may",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="don_vi_to_chuc",
                                to="tochuc.nhamay",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Đơn vị tổ chức",
                        "verbose_name_plural": "Các đơn vị tổ chức",
                        "db_table": "quanlycatruc_donvitochuc",
                        "ordering": ["thu_tu", "ten_don_vi"],
                    },
                ),
                migrations.CreateModel(
                    name="BoPhan",
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
                        ("ma_bo_phan", models.CharField(max_length=50)),
                        ("ten_bo_phan", models.CharField(max_length=150)),
                        (
                            "loai_bo_phan",
                            models.CharField(
                                choices=[
                                    ("van_hanh", "Vận hành"),
                                    ("ky_thuat", "Kỹ thuật"),
                                    ("hanh_chinh", "Hành chính"),
                                    ("bao_ve", "Bảo vệ"),
                                    ("bao_tri", "Bảo trì"),
                                    ("an_toan", "An toàn"),
                                    ("khac", "Khác"),
                                ],
                                default="khac",
                                max_length=20,
                            ),
                        ),
                        ("thu_tu", models.PositiveSmallIntegerField(default=1)),
                        ("dang_hoat_dong", models.BooleanField(default=True)),
                        (
                            "don_vi",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="bo_phan",
                                to="tochuc.donvitochuc",
                            ),
                        ),
                    ],
                    options={
                        "verbose_name": "Bộ phận",
                        "verbose_name_plural": "Các bộ phận",
                        "db_table": "quanlycatruc_bophan",
                        "ordering": ["don_vi", "thu_tu", "ten_bo_phan"],
                        "constraints": [
                            models.UniqueConstraint(
                                fields=("don_vi", "ma_bo_phan"),
                                name="uq_bophan_donvi_ma",
                            )
                        ],
                    },
                ),
            ],
        ),
    ]
