import uuid

import django.db.models.deletion
from django.db import migrations, models


def _normalize(value):
    return str(value or "").strip().casefold()


def _resolve_plant_id(device, plants):
    device_plant = _normalize(getattr(device, "nha_may", ""))
    full_code = _normalize(getattr(device, "ma_day_du", ""))
    for plant in plants:
        code = _normalize(plant.ma_nha_may)
        name = _normalize(plant.ten_nha_may)
        if code and (device_plant == code or full_code.startswith(f"{code}.")):
            return plant.pk
        if name and (device_plant == name or name in device_plant):
            return plant.pk
    return None


def backfill_monthly_switch_identity(apps, schema_editor):
    Template = apps.get_model("nhatkyvanhanh", "MauChuyenDoiTBThang")
    Log = apps.get_model("nhatkyvanhanh", "SoChuyenDoiTBThang")
    Detail = apps.get_model("nhatkyvanhanh", "ChiTietChuyenDoiTBThang")
    Plant = apps.get_model("tochuc", "NhaMay")
    plants = list(Plant.objects.all())

    template_map = {}
    for template in Template.objects.select_related("thiet_bi").iterator(chunk_size=500):
        plant_id = template.nha_may_id or _resolve_plant_id(template.thiet_bi, plants)
        if not plant_id:
            raise RuntimeError(f"Không xác định được nhà máy cho mẫu tháng {template.pk}")
        identity = uuid.uuid4()
        phase = (template.pha or "").strip().upper()
        display_code = (template.thiet_bi.ma_day_du or template.thiet_bi.ma or "").strip().upper()
        display_name = (template.thiet_bi.ten or "").strip()
        key = ("LINKED", plant_id, template.thiet_bi_id, phase)
        if key in template_map:
            raise RuntimeError(f"Trùng khóa logic mẫu tháng khi backfill: {key}")
        template_map[key] = identity
        Template.objects.filter(pk=template.pk).update(
            nha_may_id=plant_id,
            ma_dinh_danh=identity,
            ma_hien_thi=display_code,
            ten_hien_thi=display_name,
            pha=phase,
            loai_tinh_toan="counter",
        )

    for log in Log.objects.filter(nha_may_id__isnull=True).iterator(chunk_size=500):
        first_detail = Detail.objects.select_related("thiet_bi").filter(so_id=log.pk).first()
        plant_id = _resolve_plant_id(first_detail.thiet_bi, plants) if first_detail else None
        if not plant_id:
            raise RuntimeError(f"Không xác định được nhà máy cho sổ tháng {log.pk}")
        Log.objects.filter(pk=log.pk).update(nha_may_id=plant_id)

    orphan_map = {}
    yearly_baselines = {}
    details = Detail.objects.select_related("so", "thiet_bi").order_by(
        "so__nam", "so__thang", "created_at"
    )
    for detail in details.iterator(chunk_size=500):
        plant_id = detail.so.nha_may_id
        phase = (detail.pha or "").strip().upper()
        display_code = (detail.thiet_bi.ma_day_du or detail.thiet_bi.ma or "").strip().upper()
        display_name = (detail.thiet_bi.ten or "").strip()
        key = ("LINKED", plant_id, detail.thiet_bi_id, phase)
        identity = template_map.get(key)
        if identity is None:
            identity = orphan_map.setdefault(key, uuid.uuid4())
        beginning = detail.dau_thang or 0
        ending = detail.cuoi_thang or 0
        baseline_key = (identity, detail.so.nam)
        yearly_baseline = yearly_baselines.setdefault(baseline_key, beginning)
        Detail.objects.filter(pk=detail.pk).update(
            ma_dinh_danh=identity,
            ma_hien_thi=display_code,
            ten_hien_thi=display_name,
            pha=phase,
            loai_tinh_toan="counter",
            dau_nam=yearly_baseline,
            luy_ke_nam=ending - yearly_baseline,
        )


class Migration(migrations.Migration):
    # Commit the data backfill before altering PostgreSQL constraints. Keeping
    # all operations in one transaction leaves FK trigger events pending.
    atomic = False

    dependencies = [("nhatkyvanhanh", "0065_dynamic_weekly_switch_areas")]

    operations = [
        migrations.AddField(
            model_name="mauchuyendoitbthang",
            name="ma_dinh_danh",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="mauchuyendoitbthang",
            name="ma_hien_thi",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="mauchuyendoitbthang",
            name="ten_hien_thi",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="mauchuyendoitbthang",
            name="pha",
            field=models.CharField(blank=True, choices=[("", "Không phân pha"), ("A", "Pha A"), ("B", "Pha B"), ("C", "Pha C")], default="", max_length=10),
        ),
        migrations.AddField(
            model_name="mauchuyendoitbthang",
            name="loai_tinh_toan",
            field=models.CharField(choices=[("counter", "Bộ đếm tăng dần"), ("fuel", "Nhiên liệu tiêu hao")], default="counter", max_length=20),
        ),
        migrations.AddField(
            model_name="chitietchuyendoitbthang",
            name="ma_dinh_danh",
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="chitietchuyendoitbthang",
            name="ma_hien_thi",
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="chitietchuyendoitbthang",
            name="ten_hien_thi",
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="chitietchuyendoitbthang",
            name="pha",
            field=models.CharField(blank=True, choices=[("", "Không phân pha"), ("A", "Pha A"), ("B", "Pha B"), ("C", "Pha C")], default="", max_length=10),
        ),
        migrations.AddField(
            model_name="chitietchuyendoitbthang",
            name="loai_tinh_toan",
            field=models.CharField(choices=[("counter", "Bộ đếm tăng dần"), ("fuel", "Nhiên liệu tiêu hao")], default="counter", max_length=20),
        ),
        migrations.AddField(model_name="chitietchuyendoitbthang", name="dau_nam", field=models.DecimalField(decimal_places=3, default=0, max_digits=18)),
        migrations.AddField(model_name="chitietchuyendoitbthang", name="nhap_trong_thang", field=models.DecimalField(decimal_places=3, default=0, max_digits=18)),
        migrations.AddField(model_name="chitietchuyendoitbthang", name="luy_ke_nam", field=models.DecimalField(decimal_places=3, default=0, editable=False, max_digits=18)),
        migrations.AddField(model_name="chitietchuyendoitbthang", name="luy_ke_truoc_so_hoa", field=models.DecimalField(decimal_places=3, default=0, max_digits=18)),
        migrations.AlterField(model_name="chitietchuyendoitbthang", name="dau_thang", field=models.DecimalField(decimal_places=3, default=0, max_digits=18)),
        migrations.AlterField(model_name="chitietchuyendoitbthang", name="cuoi_thang", field=models.DecimalField(decimal_places=3, default=0, max_digits=18)),
        migrations.AlterField(model_name="chitietchuyendoitbthang", name="thuc_hien", field=models.DecimalField(decimal_places=3, default=0, editable=False, max_digits=18)),
        migrations.RunPython(backfill_monthly_switch_identity, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name="mauchuyendoitbthang", name="uq_mau_chuyen_doi_tb_thang_nha_may_thiet_bi"),
        migrations.RemoveConstraint(model_name="chitietchuyendoitbthang", name="uq_chi_tiet_chuyen_doi_tb_thang_so_thiet_bi"),
        migrations.AlterField(model_name="mauchuyendoitbthang", name="ma_dinh_danh", field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
        migrations.AlterField(model_name="mauchuyendoitbthang", name="ma_hien_thi", field=models.CharField(max_length=100)),
        migrations.AlterField(model_name="mauchuyendoitbthang", name="ten_hien_thi", field=models.CharField(max_length=255)),
        migrations.AlterField(model_name="mauchuyendoitbthang", name="nha_may", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mau_chuyen_doi_tb_thang", to="tochuc.nhamay", verbose_name="Nhà máy")),
        migrations.AlterField(model_name="mauchuyendoitbthang", name="thiet_bi", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mau_chuyen_doi_tb_thang", to="quanlyvanhanh.thietbi")),
        migrations.AlterField(model_name="sochuyendoitbthang", name="nha_may", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="so_chuyen_doi_tb_thang", to="tochuc.nhamay", verbose_name="Nhà máy")),
        migrations.AlterField(model_name="chitietchuyendoitbthang", name="ma_dinh_danh", field=models.UUIDField(db_index=True, editable=False)),
        migrations.AlterField(model_name="chitietchuyendoitbthang", name="ma_hien_thi", field=models.CharField(max_length=100)),
        migrations.AlterField(model_name="chitietchuyendoitbthang", name="ten_hien_thi", field=models.CharField(max_length=255)),
        migrations.AlterField(model_name="chitietchuyendoitbthang", name="thiet_bi", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="chi_tiet_chuyen_doi_tb_thang", to="quanlyvanhanh.thietbi")),
        migrations.AddConstraint(model_name="mauchuyendoitbthang", constraint=models.UniqueConstraint(condition=models.Q(("thiet_bi__isnull", False)), fields=("nha_may", "thiet_bi", "pha"), name="uq_mau_thang_linked_device_phase")),
        migrations.AddConstraint(model_name="mauchuyendoitbthang", constraint=models.UniqueConstraint(condition=models.Q(("thiet_bi__isnull", True)), fields=("nha_may", "ma_hien_thi", "pha"), name="uq_mau_thang_manual_device_phase")),
        migrations.AddConstraint(model_name="chitietchuyendoitbthang", constraint=models.UniqueConstraint(condition=models.Q(("thiet_bi__isnull", False)), fields=("so", "thiet_bi", "pha"), name="uq_chi_tiet_thang_linked_device_phase")),
        migrations.AddConstraint(model_name="chitietchuyendoitbthang", constraint=models.UniqueConstraint(condition=models.Q(("thiet_bi__isnull", True)), fields=("so", "ma_hien_thi", "pha"), name="uq_chi_tiet_thang_manual_device_phase")),
        migrations.AddConstraint(model_name="chitietchuyendoitbthang", constraint=models.UniqueConstraint(fields=("so", "ma_dinh_danh"), name="uq_chi_tiet_thang_so_ma_dinh_danh")),
    ]
