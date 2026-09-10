import re
import unicodedata

from django.db import migrations, models


def normalize_name(value):
    value = unicodedata.normalize("NFC", value or "")
    return re.sub(r"\s+", " ", value).strip().casefold()


def backfill_shift_staff_identity(apps, schema_editor):
    ShiftStaff = apps.get_model("nhatkyvanhanh", "NhanSuSoGiaoNhanCaVH")
    Staff = apps.get_model("tochuc", "NhanSu")

    staff_by_plant_and_name = {}
    for staff in Staff.objects.select_related("don_vi").all().iterator():
        key = (staff.don_vi.nha_may_id, normalize_name(staff.ho_ten))
        staff_by_plant_and_name.setdefault(key, []).append(staff)

    linked_pairs = set()
    linked_rows = ShiftStaff.objects.exclude(nhan_su_id=None).order_by(
        "created_at",
        "pk",
    )
    for row in linked_rows.iterator():
        pair = (row.so_giao_nhan_ca_id, row.nhan_su_id)
        if pair in linked_pairs:
            # Giữ snapshot nhưng bỏ liên kết trùng trước khi tạo constraint.
            ShiftStaff.objects.filter(pk=row.pk).update(nhan_su_id=None)
            continue
        linked_pairs.add(pair)

    legacy_rows = (
        ShiftStaff.objects.filter(nhan_su_id=None)
        .select_related("so_giao_nhan_ca")
        .order_by("created_at", "pk")
    )
    for row in legacy_rows.iterator():
        key = (
            row.so_giao_nhan_ca.nha_may_id,
            normalize_name(row.ten_nhan_su),
        )
        matches = staff_by_plant_and_name.get(key, [])
        if len(matches) != 1:
            # Không đoán khi không tìm thấy hoặc có nhiều nhân sự trùng tên.
            continue

        staff = matches[0]
        pair = (row.so_giao_nhan_ca_id, staff.pk)
        if pair in linked_pairs:
            continue

        ShiftStaff.objects.filter(pk=row.pk).update(
            nhan_su_id=staff.pk,
            ten_nhan_su=staff.ho_ten,
            ma_nhan_vien=staff.ma_nhan_vien or "",
        )
        linked_pairs.add(pair)


class Migration(migrations.Migration):

    # PostgreSQL cần hoàn tất các trigger FK do bước backfill tạo ra trước khi
    # dựng unique index có điều kiện trong operation kế tiếp.
    atomic = False

    dependencies = [
        ("nhatkyvanhanh", "0061_nhansusogiaonhancavh_ma_nhan_vien_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_shift_staff_identity,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="nhansusogiaonhancavh",
            constraint=models.UniqueConstraint(
                fields=("so_giao_nhan_ca", "nhan_su"),
                condition=models.Q(nhan_su__isnull=False),
                name="uq_sogiaonhancavh_nhan_su_lien_ket",
            ),
        ),
    ]
