from django.db import migrations, models
import django.db.models.deletion
import datetime


def create_default_groups(apps, schema_editor):
    Plant = apps.get_model("khovattu", "Bang_nha_may")
    Unit = apps.get_model("quanlycatruc", "DonViToChuc")
    Department = apps.get_model("quanlycatruc", "BoPhan")
    Group = apps.get_model("quanlycatruc", "NhomLichTruc")
    Scope = apps.get_model("quanlycatruc", "PhamViNhanSuCaTruc")
    Personnel = apps.get_model("quanlycatruc", "NhanSu")
    Membership = apps.get_model("quanlycatruc", "ThanhVienKipTruc")
    Team = apps.get_model("quanlycatruc", "KipTruc")
    Template = apps.get_model("quanlycatruc", "MauChuKyCaTruc")
    Schedule = apps.get_model("quanlycatruc", "LichTrucCa")
    Plan = apps.get_model("quanlycatruc", "PhuongAnPhanCongCa")

    for plant in Plant.objects.all():
        department = Department.objects.filter(don_vi__nha_may_id=plant.id, loai_bo_phan="van_hanh").first()
        if department:
            unit = department.don_vi
        else:
            unit = Unit.objects.filter(nha_may_id=plant.id).first()
            if not unit:
                unit = Unit.objects.create(ma_don_vi=f"NM-{plant.id}", ten_don_vi=plant.ten_nha_may, loai_don_vi="nha_may", nha_may_id=plant.id)
            department = Department.objects.filter(don_vi=unit).first()
            if not department:
                department = Department.objects.create(don_vi=unit, ma_bo_phan="VH", ten_bo_phan="Vận hành", loai_bo_phan="van_hanh")
        group = Group.objects.create(
            nha_may_id=plant.id, don_vi=unit, bo_phan=department,
            ma_nhom="MAC_DINH", ten_nhom="Lịch trực vận hành", dia_diem=plant.ten_nha_may,
        )
        Team.objects.filter(nha_may_id=plant.id).update(nhom_lich=group)
        Template.objects.filter(nha_may_id=plant.id).update(nhom_lich=group)
        Schedule.objects.filter(nha_may_id=plant.id).update(nhom_lich=group)
        Plan.objects.filter(nha_may_id=plant.id).update(nhom_lich=group)
        personnel_ids = set(Personnel.objects.filter(bo_phan=department, dang_lam_viec=True).values_list("id", flat=True))
        personnel_ids.update(Membership.objects.filter(kip_truc__nhom_lich=group, nhan_su_id__isnull=False).values_list("nhan_su_id", flat=True))
        Scope.objects.bulk_create([Scope(nhom_lich=group, nhan_su_id=personnel_id) for personnel_id in personnel_ids], ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0010_schedule_custom_range_and_lunar_date")]
    operations = [
        migrations.CreateModel(
            name="NhomLichTruc",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("ma_nhom", models.CharField(max_length=50)), ("ten_nhom", models.CharField(max_length=150)),
                ("dia_diem", models.CharField(blank=True, max_length=200)), ("thu_tu", models.PositiveSmallIntegerField(default=1)),
                ("dang_hoat_dong", models.BooleanField(default=True)),
                ("bo_phan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="nhom_lich_truc", to="quanlycatruc.bophan")),
                ("don_vi", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="nhom_lich_truc", to="quanlycatruc.donvitochuc")),
                ("nha_may", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="nhom_lich_truc", to="khovattu.bang_nha_may")),
            ], options={"ordering": ["nha_may", "thu_tu", "ten_nhom"], "verbose_name": "Nhóm lịch trực", "verbose_name_plural": "Các nhóm lịch trực"},
        ),
        migrations.AddConstraint(model_name="nhomlichtruc", constraint=models.UniqueConstraint(fields=("nha_may", "ma_nhom"), name="uq_nhomlich_nhamay_ma")),
        migrations.CreateModel(
            name="PhamViNhanSuCaTruc",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("tu_ngay", models.DateField(default=datetime.date.today)), ("den_ngay", models.DateField(blank=True, null=True)), ("dang_hoat_dong", models.BooleanField(default=True)),
                ("nhan_su", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pham_vi_ca_truc", to="quanlycatruc.nhansu")),
                ("nhom_lich", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="pham_vi_nhan_su", to="quanlycatruc.nhomlichtruc")),
            ], options={"ordering": ["nhom_lich", "nhan_su__ho_ten"], "verbose_name": "Phạm vi nhân sự ca trực", "verbose_name_plural": "Phạm vi nhân sự ca trực"},
        ),
        migrations.AddConstraint(model_name="phamvinhansucatruc", constraint=models.UniqueConstraint(fields=("nhom_lich", "nhan_su"), name="uq_phamvi_nhom_nhansu")),
        migrations.AddField(model_name="kiptruc", name="nhom_lich", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="kip_truc", to="quanlycatruc.nhomlichtruc")),
        migrations.AddField(model_name="mauchukycatruc", name="nhom_lich", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mau_chu_ky", to="quanlycatruc.nhomlichtruc")),
        migrations.AddField(model_name="lichtrucca", name="nhom_lich", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="lich_truc", to="quanlycatruc.nhomlichtruc")),
        migrations.AddField(model_name="phuonganphancongca", name="nhom_lich", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="phuong_an_phan_cong", to="quanlycatruc.nhomlichtruc")),
        migrations.AlterField(model_name="kiptruc", name="ma_kip", field=models.CharField(max_length=20)),
        migrations.RemoveConstraint(model_name="kiptruc", name="uq_catruc_nhamay_makip"),
        migrations.RemoveConstraint(model_name="kiptruc", name="ck_catruc_loai_ma_hop_le"),
        migrations.RemoveConstraint(model_name="mauchukycatruc", name="uq_mauchuky_nhamay_phienban"),
        migrations.RemoveConstraint(model_name="lichtrucca", name="uq_lichtruc_thang_phienban"),
        migrations.RemoveConstraint(model_name="phuonganphancongca", name="uq_phuongan_phancong_ky_phienban"),
        migrations.RunPython(create_default_groups, migrations.RunPython.noop),
        migrations.AddConstraint(model_name="kiptruc", constraint=models.UniqueConstraint(fields=("nhom_lich", "ma_kip"), name="uq_catruc_nhomlich_makip")),
        migrations.AddConstraint(model_name="mauchukycatruc", constraint=models.UniqueConstraint(fields=("nhom_lich", "phien_ban"), name="uq_mauchuky_nhom_phienban")),
        migrations.AddConstraint(model_name="lichtrucca", constraint=models.UniqueConstraint(fields=("nhom_lich", "nam", "thang", "phien_ban"), name="uq_lichtruc_nhom_thang_phienban")),
        migrations.AddConstraint(model_name="phuonganphancongca", constraint=models.UniqueConstraint(fields=("nhom_lich", "nam", "thang", "phien_ban"), name="uq_phuongan_nhom_ky_phienban")),
    ]
