from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ai_tools", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditAiQuery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query", models.TextField()),
                ("answer", models.TextField(blank=True)),
                ("module_code", models.CharField(blank=True, db_index=True, max_length=50)),
                ("document_ids", models.JSONField(blank=True, default=list)),
                ("guide_ids", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audited_ai_queries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Nhật ký truy vấn AI tài liệu",
                "verbose_name_plural": "Nhật ký truy vấn AI tài liệu",
                "ordering": ("-created_at", "-id"),
            },
        ),
    ]
