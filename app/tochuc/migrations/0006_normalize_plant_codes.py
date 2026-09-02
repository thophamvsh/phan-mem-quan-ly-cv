import unicodedata

from django.db import migrations


PLANT_CODES = {
    "song hinh": "SH",
    "vinh son": "VS",
    "thuong kon tum": "TKT",
}


def normalize(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return " ".join(
        "".join(char for char in normalized if not unicodedata.combining(char))
        .lower()
        .replace("đ", "d")
        .split()
    )


def normalize_plant_codes(apps, schema_editor):
    NhaMay = apps.get_model("tochuc", "NhaMay")
    DonViToChuc = apps.get_model("tochuc", "DonViToChuc")
    updates = []
    for plant in NhaMay.objects.all():
        normalized_name = normalize(plant.ten_nha_may)
        target_code = next(
            (code for name, code in PLANT_CODES.items() if name in normalized_name),
            None,
        )
        if target_code and plant.ma_nha_may.upper() != target_code:
            updates.append((plant, target_code))

    targets = [code for _, code in updates]
    if len(targets) != len(set(targets)):
        raise RuntimeError("Có nhiều nhà máy cùng ánh xạ tới một mã chuẩn.")

    updating_ids = {plant.pk for plant, _ in updates}
    conflicts = NhaMay.objects.filter(ma_nha_may__in=targets).exclude(
        pk__in=updating_ids
    )
    if conflicts.exists():
        raise RuntimeError("Mã nhà máy chuẩn đã được sử dụng bởi bản ghi khác.")

    for plant, _ in updates:
        plant.ma_nha_may = f"TMP-{plant.pk}"
        plant.save(update_fields=["ma_nha_may"])
    for plant, target_code in updates:
        plant.ma_nha_may = target_code
        plant.save(update_fields=["ma_nha_may"])

    plants_by_code = {
        plant.ma_nha_may.upper(): plant
        for plant in NhaMay.objects.filter(ma_nha_may__in=PLANT_CODES.values())
    }
    for unit in DonViToChuc.objects.all():
        normalized_name = normalize(unit.ten_don_vi)
        target_code = next(
            (code for name, code in PLANT_CODES.items() if name in normalized_name),
            None,
        )
        target_plant = plants_by_code.get(target_code)
        if target_plant and unit.nha_may_id != target_plant.pk:
            unit.nha_may_id = target_plant.pk
            unit.save(update_fields=["nha_may"])


class Migration(migrations.Migration):
    dependencies = [("tochuc", "0005_transfer_legacy_organization_permissions")]

    operations = [
        migrations.RunPython(normalize_plant_codes, migrations.RunPython.noop),
    ]
