import uuid

from django.db import migrations


def assign_unique_batch_to_legacy_rows(apps, schema_editor):
    Adjustment = apps.get_model("quanlycatruc", "DieuChinhNhanSuCaTruc")
    for adjustment_id in Adjustment.objects.values_list("id", flat=True).iterator():
        Adjustment.objects.filter(pk=adjustment_id).update(ma_phieu=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0006_dieuchinhnhansucatruc_ma_phieu")]

    operations = [migrations.RunPython(assign_unique_batch_to_legacy_rows, migrations.RunPython.noop)]
