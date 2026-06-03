from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("original_file", models.FileField(upload_to="ai_documents/%Y/%m/")),
                ("markdown_text", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("uploaded", "Uploaded"), ("processing", "Processing"), ("ready", "Ready"), ("failed", "Failed")], default="uploaded", max_length=20)),
                ("document_type", models.CharField(blank=True, default="", max_length=80)),
                ("factory", models.CharField(choices=[("general", "Chung"), ("songhinh", "Song Hinh"), ("vinhson", "Vinh Son"), ("thuongkontum", "Thuong Kon Tum")], default="general", max_length=40)),
                ("visibility", models.CharField(default="internal", max_length=30)),
                ("version", models.PositiveIntegerField(default=1)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ai_documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-updated_at", "-id"),
            },
        ),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField()),
                ("heading_path", models.CharField(blank=True, max_length=500)),
                ("content", models.TextField()),
                ("token_count", models.PositiveIntegerField(default=0)),
                ("page_from", models.PositiveIntegerField(blank=True, null=True)),
                ("page_to", models.PositiveIntegerField(blank=True, null=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("embedding", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("document", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="chunks", to="documents.document")),
            ],
            options={
                "ordering": ("document_id", "chunk_index"),
                "unique_together": {("document", "chunk_index")},
            },
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["status", "factory"], name="documents_d_status_7db45b_idx"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["document_type", "factory"], name="documents_d_documen_9ef95c_idx"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["created_at"], name="documents_d_created_3b0a51_idx"),
        ),
        migrations.AddIndex(
            model_name="documentchunk",
            index=models.Index(fields=["document", "chunk_index"], name="documents_d_documen_8ea6ce_idx"),
        ),
        migrations.AddIndex(
            model_name="documentchunk",
            index=models.Index(fields=["token_count"], name="documents_d_token_c_166a1e_idx"),
        ),
    ]
