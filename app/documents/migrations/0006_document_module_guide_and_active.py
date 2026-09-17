from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0005_moduleguide"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="document",
            name="module_guide",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rag_document",
                to="documents.moduleguide",
            ),
        ),
    ]
