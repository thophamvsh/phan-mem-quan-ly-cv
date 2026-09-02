from django.db import migrations


def backfill_employee_codes(apps, schema_editor):
    NhanSu = apps.get_model("tochuc", "NhanSu")
    for person in NhanSu.objects.filter(ma_nhan_vien__isnull=True).iterator():
        person.ma_nhan_vien = f"NS-{person.pk:08d}"
        person.save(update_fields=["ma_nhan_vien"])
    for person in NhanSu.objects.filter(ma_nhan_vien="").iterator():
        person.ma_nhan_vien = f"NS-{person.pk:08d}"
        person.save(update_fields=["ma_nhan_vien"])


class Migration(migrations.Migration):
    dependencies = [("tochuc", "0006_normalize_plant_codes")]

    operations = [
        migrations.RunPython(backfill_employee_codes, migrations.RunPython.noop),
    ]
