import unicodedata

from django.db import migrations


UNIT_CODES = {
    "SH": ("song hinh", "SH-NM"),
    "VS": ("vinh son", "VS-NM"),
    "TKT": ("thuong kon tum", "TKT-NM"),
}


def normalize(value):
    normalized = unicodedata.normalize("NFKD", value or "")
    return " ".join(
        "".join(char for char in normalized if not unicodedata.combining(char))
        .lower()
        .replace("đ", "d")
        .split()
    )


def normalize_root_unit_codes(apps, schema_editor):
    NhaMay = apps.get_model("tochuc", "NhaMay")
    DonViToChuc = apps.get_model("tochuc", "DonViToChuc")
    updates = []

    for plant_code, (name_fragment, target_code) in UNIT_CODES.items():
        plant = NhaMay.objects.filter(ma_nha_may__iexact=plant_code).first()
        if not plant:
            continue
        candidates = [
            unit
            for unit in DonViToChuc.objects.filter(
                nha_may_id=plant.pk,
                don_vi_cha__isnull=True,
            )
            if name_fragment in normalize(unit.ten_don_vi)
        ]
        preferred = [
            unit for unit in candidates if unit.loai_don_vi == "nha_may"
        ]
        if len(preferred) == 1:
            candidates = preferred
        if not candidates:
            continue
        if len(candidates) > 1:
            raise RuntimeError(
                f"Không xác định duy nhất đơn vị gốc của nhà máy {plant_code}."
            )
        unit = candidates[0]
        if unit.ma_don_vi != target_code:
            updates.append((unit, target_code))

    targets = [target for _, target in updates]
    updating_ids = {unit.pk for unit, _ in updates}
    conflicts = DonViToChuc.objects.filter(ma_don_vi__in=targets).exclude(
        pk__in=updating_ids
    )
    if conflicts.exists() or len(targets) != len(set(targets)):
        raise RuntimeError("Mã đơn vị chuẩn đã được sử dụng bởi đơn vị khác.")

    for unit, _ in updates:
        unit.ma_don_vi = f"TMP-UNIT-{unit.pk}"
        unit.save(update_fields=["ma_don_vi"])
    for unit, target_code in updates:
        unit.ma_don_vi = target_code
        unit.save(update_fields=["ma_don_vi"])


class Migration(migrations.Migration):
    dependencies = [("tochuc", "0007_backfill_employee_codes")]

    operations = [
        migrations.RunPython(
            normalize_root_unit_codes,
            migrations.RunPython.noop,
        ),
    ]
