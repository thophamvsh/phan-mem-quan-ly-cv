from django.db import migrations


def migrate_existing_roster_staff(apps, schema_editor):
    DonViToChuc = apps.get_model("quanlycatruc", "DonViToChuc")
    BoPhan = apps.get_model("quanlycatruc", "BoPhan")
    NhanSu = apps.get_model("quanlycatruc", "NhanSu")
    ThanhVienKipTruc = apps.get_model("quanlycatruc", "ThanhVienKipTruc")
    BangNhaMay = apps.get_model("khovattu", "Bang_nha_may")

    units = {}
    departments = {}
    for plant in BangNhaMay.objects.all():
        unit, _ = DonViToChuc.objects.get_or_create(
            ma_don_vi=f"NM-{plant.pk}",
            defaults={
                "ten_don_vi": plant.ten_nha_may,
                "loai_don_vi": "nha_may",
                "nha_may_id": plant.pk,
            },
        )
        department, _ = BoPhan.objects.get_or_create(
            don_vi=unit,
            ma_bo_phan="VH",
            defaults={"ten_bo_phan": "Vận hành", "loai_bo_phan": "van_hanh"},
        )
        units[plant.pk] = unit
        departments[plant.pk] = department

    for membership in ThanhVienKipTruc.objects.select_related("kip_truc", "user"):
        if not membership.user_id or membership.nhan_su_id:
            continue
        plant_id = membership.kip_truc.nha_may_id
        user = membership.user
        full_name = " ".join(filter(None, [user.first_name, user.last_name])).strip() or user.username
        personnel, _ = NhanSu.objects.get_or_create(
            user_id=user.pk,
            defaults={
                "ho_ten": full_name,
                "don_vi": units[plant_id],
                "bo_phan": departments[plant_id],
                "tu_ngay": membership.tu_ngay,
            },
        )
        membership.nhan_su_id = personnel.pk
        membership.save(update_fields=["nhan_su"])


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0002_alter_thanhvienkiptruc_user_donvitochuc_bophan_and_more")]

    operations = [migrations.RunPython(migrate_existing_roster_staff, migrations.RunPython.noop)]
