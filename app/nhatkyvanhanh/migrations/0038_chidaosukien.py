from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


def migrate_legacy_chi_dao(apps, schema_editor):
    SuKien = apps.get_model("nhatkyvanhanh", "SuKien")
    ChiDaoSuKien = apps.get_model("nhatkyvanhanh", "ChiDaoSuKien")

    for su_kien in SuKien.objects.exclude(chi_dao=""):
        if ChiDaoSuKien.objects.filter(su_kien_id=su_kien.id).exists():
            continue
        ChiDaoSuKien.objects.create(
            su_kien_id=su_kien.id,
            noi_dung=su_kien.chi_dao,
            nguoi_chi_dao_id=su_kien.nguoi_chi_dao_id,
            chu_ky_nguoi_chi_dao=su_kien.chu_ky_nguoi_chi_dao,
            created_at=su_kien.updated_at,
            updated_at=su_kien.updated_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("nhatkyvanhanh", "0037_alter_chitietchuyendoitbthang_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ChiDaoSuKien",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("noi_dung", models.TextField()),
                ("chuc_danh_nguoi_chi_dao", models.CharField(blank=True, max_length=100)),
                (
                    "chu_ky_nguoi_chi_dao",
                    models.ImageField(
                        blank=True,
                        null=True,
                        upload_to="operations/nhat_ky_su_kien/chu_ky/chi_dao/",
                    ),
                ),
                (
                    "nguoi_chi_dao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="chi_dao_su_kien_da_tao",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "su_kien",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chi_dao_su_kiens",
                        to="nhatkyvanhanh.sukien",
                    ),
                ),
            ],
            options={
                "verbose_name": "Chỉ đạo sự kiện",
                "verbose_name_plural": "Chỉ đạo sự kiện",
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.RunPython(migrate_legacy_chi_dao, migrations.RunPython.noop),
    ]
