from django.db import migrations


def recalculate_counter_baselines(apps, schema_editor):
    Detail = apps.get_model("nhatkyvanhanh", "ChiTietChuyenDoiTBThang")
    baselines = {}
    queryset = Detail.objects.select_related("so").order_by(
        "so__nam", "so__thang", "created_at"
    )
    for detail in queryset.iterator(chunk_size=500):
        if detail.loai_tinh_toan != "counter":
            continue
        key = (detail.ma_dinh_danh, detail.so.nam)
        baseline = baselines.setdefault(key, detail.dau_thang or 0)
        Detail.objects.filter(pk=detail.pk).update(
            dau_nam=baseline,
            luy_ke_nam=(detail.cuoi_thang or 0) - baseline,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("nhatkyvanhanh", "0066_monthly_switch_dual_source"),
    ]

    operations = [
        migrations.RunPython(
            recalculate_counter_baselines,
            migrations.RunPython.noop,
        ),
    ]
