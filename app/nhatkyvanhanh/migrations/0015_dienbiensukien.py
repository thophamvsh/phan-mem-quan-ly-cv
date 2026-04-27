from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("nhatkyvanhanh", "0014_khacphucsukien_nguoi_tao"),
    ]

    operations = [
        migrations.CreateModel(
            name="DienBienSuKien",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("thoi_gian_dien_bien", models.DateTimeField(default=django.utils.timezone.now)),
                ("noi_dung", models.TextField()),
                (
                    "nguoi_tao",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dien_bien_su_kien_da_tao",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "su_kien",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dien_bien_su_kiens",
                        to="nhatkyvanhanh.sukien",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dien bien su kien",
                "verbose_name_plural": "Dien bien su kien",
                "ordering": ["thoi_gian_dien_bien", "created_at"],
            },
        ),
    ]
