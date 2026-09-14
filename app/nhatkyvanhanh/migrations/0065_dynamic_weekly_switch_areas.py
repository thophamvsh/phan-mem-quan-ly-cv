import uuid

import django.db.models.deletion
from django.db import migrations, models


DEFAULT_AREAS = (
    ("H1", "Tổ máy H1", 1),
    ("H2", "Tổ máy H2", 2),
    ("TU_DUNG", "Tự dùng", 3),
)


def backfill_areas(apps, schema_editor):
    Area = apps.get_model("nhatkyvanhanh", "KhuVucChuyenDoiThietBi")
    Template = apps.get_model("nhatkyvanhanh", "MauChuyenDoiThietBi")
    Detail = apps.get_model("nhatkyvanhanh", "ChiTietChuyenDoiThietBi")
    Plant = apps.get_model("tochuc", "NhaMay")

    for plant in Plant.objects.all().iterator():
        area_map = {}
        for code, name, order in DEFAULT_AREAS:
            area, _ = Area.objects.get_or_create(
                nha_may_id=plant.pk,
                ma_khu_vuc=code,
                defaults={"ten_khu_vuc": name, "thu_tu": order, "dang_su_dung": True},
            )
            area_map[code] = area

        for template in Template.objects.filter(nha_may_id=plant.pk).iterator():
            normalized = (template.to_may or "").strip().upper()
            area = area_map.get(normalized)
            if area is None:
                area, _ = Area.objects.get_or_create(
                    nha_may_id=plant.pk,
                    ma_khu_vuc=normalized or "KHAC",
                    defaults={
                        "ten_khu_vuc": template.to_may or "Khu vực khác",
                        "thu_tu": 99,
                        "dang_su_dung": True,
                    },
                )
            Template.objects.filter(pk=template.pk).update(
                khu_vuc_id=area.pk,
                to_may=area.ma_khu_vuc,
            )

    for detail in Detail.objects.select_related("lan_chuyen_doi__so").iterator():
        plant_id = detail.lan_chuyen_doi.so.nha_may_id
        if not plant_id:
            continue
        normalized = (detail.to_may or "").strip().upper()
        area = Area.objects.filter(nha_may_id=plant_id, ma_khu_vuc=normalized).first()
        if area:
            Detail.objects.filter(pk=detail.pk).update(
                khu_vuc_id=area.pk,
                to_may=area.ma_khu_vuc,
                ten_khu_vuc_snapshot=area.ten_khu_vuc,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("nhatkyvanhanh", "0064_seed_14_default_shift_command_templates"),
        ("tochuc", "0008_normalize_root_unit_codes"),
    ]

    operations = [
        migrations.CreateModel(
            name="KhuVucChuyenDoiThietBi",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ma_khu_vuc", models.CharField(max_length=50, verbose_name="Mã khu vực")),
                ("ten_khu_vuc", models.CharField(max_length=255, verbose_name="Tên khu vực")),
                ("thu_tu", models.PositiveIntegerField(default=0, verbose_name="Thứ tự hiển thị")),
                ("dang_su_dung", models.BooleanField(default=True, verbose_name="Đang sử dụng")),
                ("nha_may", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="khu_vuc_chuyen_doi_thiet_bi", to="tochuc.nhamay", verbose_name="Nhà máy")),
            ],
            options={
                "verbose_name": "Khu vực chuyển đổi thiết bị",
                "verbose_name_plural": "Khu vực chuyển đổi thiết bị",
                "ordering": ["nha_may", "thu_tu", "ten_khu_vuc"],
            },
        ),
        migrations.AddConstraint(
            model_name="khuvucchuyendoithietbi",
            constraint=models.UniqueConstraint(fields=("nha_may", "ma_khu_vuc"), name="uq_khu_vuc_chuyen_doi_nha_may_ma"),
        ),
        migrations.AddField(
            model_name="mauchuyendoithietbi",
            name="khu_vuc",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mau_thiet_bi", to="nhatkyvanhanh.khuvucchuyendoithietbi", verbose_name="Tổ máy / Khu vực"),
        ),
        migrations.AddField(
            model_name="chitietchuyendoithietbi",
            name="khu_vuc",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="chi_tiet_lich_su", to="nhatkyvanhanh.khuvucchuyendoithietbi", verbose_name="Tổ máy / Khu vực"),
        ),
        migrations.AddField(
            model_name="chitietchuyendoithietbi",
            name="ten_khu_vuc_snapshot",
            field=models.CharField(blank=True, max_length=255, verbose_name="Tên khu vực tại thời điểm tạo sổ"),
        ),
        migrations.AlterField(
            model_name="mauchuyendoithietbi",
            name="to_may",
            field=models.CharField(max_length=50, verbose_name="Mã tổ máy / Khu vực"),
        ),
        migrations.AlterField(
            model_name="chitietchuyendoithietbi",
            name="to_may",
            field=models.CharField(max_length=50, verbose_name="Mã tổ máy / Khu vực"),
        ),
        migrations.RunPython(backfill_areas, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="mauchuyendoithietbi",
            name="uq_mau_chuyen_doi_thiet_bi_nha_may_to_may_tb",
        ),
        migrations.AddConstraint(
            model_name="mauchuyendoithietbi",
            constraint=models.UniqueConstraint(fields=("nha_may", "khu_vuc", "thiet_bi"), name="uq_mau_chuyen_doi_thiet_bi_nha_may_khu_vuc_tb"),
        ),
    ]
