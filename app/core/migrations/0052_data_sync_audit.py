import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0051_useractivitylog_nha_may_and_more"),
        ("tochuc", "0008_normalize_root_unit_codes"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataSyncAudit",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source", models.CharField(choices=[("EXCEL", "Excel"), ("GOOGLE_SHEET", "Google Sheet"), ("API", "API"), ("SCHEDULE", "Tác vụ tự động")], max_length=24)),
                ("data_type", models.CharField(max_length=64, verbose_name="Loại dữ liệu")),
                ("status", models.CharField(choices=[("SUCCESS", "Thành công"), ("PARTIAL", "Thành công một phần"), ("FAILED", "Thất bại")], max_length=16)),
                ("filename", models.CharField(blank=True, max_length=255, verbose_name="Tên file")),
                ("checksum_sha256", models.CharField(blank=True, editable=False, max_length=64)),
                ("date_from", models.DateField(blank=True, null=True, verbose_name="Từ ngày dữ liệu")),
                ("date_to", models.DateField(blank=True, null=True, verbose_name="Đến ngày dữ liệu")),
                ("processed_count", models.PositiveIntegerField(default=0)),
                ("created_count", models.PositiveIntegerField(default=0)),
                ("updated_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("error_summary", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="data_sync_audits", to=settings.AUTH_USER_MODEL, verbose_name="Người thực hiện")),
                ("nha_may", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="data_sync_audits", to="tochuc.nhamay", verbose_name="Nhà máy")),
            ],
            options={
                "verbose_name": "Phiên đồng bộ dữ liệu",
                "verbose_name_plural": "Các phiên đồng bộ dữ liệu",
                "ordering": ["-started_at"],
                "indexes": [
                    models.Index(fields=["nha_may", "started_at"], name="syncaudit_plant_time_idx"),
                    models.Index(fields=["status", "started_at"], name="syncaudit_status_time_idx"),
                    models.Index(fields=["data_type", "started_at"], name="syncaudit_type_time_idx"),
                ],
            },
        ),
    ]
