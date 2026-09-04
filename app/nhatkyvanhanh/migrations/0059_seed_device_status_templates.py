from django.db import migrations


PRESETS = {
    "SH": [
        ("sh-cap-110-220kv", "Trạng thái máy cắt 110 kV/220 kV", [("MC 171", "dong"), ("MC 172", "dong"), ("MC 173", "dong"), ("MC 174", "dong")]),
        ("sh-cap-22kv", "Trạng thái máy cắt 22 kV", [("MC 471", "dong"), ("MC 472", "cat"), ("MC 412", "cat")]),
        ("sh-tu-dung", "Trạng thái máy cắt tự dùng", [("MC 641", "dong"), ("MC 642", "dong"), ("MC 601", "cat"), ("MC 602", "cat")]),
    ],
    "VS": [
        ("vs-cap-110kv", "Trạng thái máy cắt 110 kV", [("MC 171", "dong"), ("MC 172", "dong")]),
        ("vs-cap-35kv", "Trạng thái máy cắt 35 kV", []),
        ("vs-cap-11kv", "Trạng thái máy cắt 11 kV", [("MC 671", "dong"), ("MC 672", "dong"), ("MC 600", "cat")]),
        ("vs-cap-10-13kv", "Trạng thái máy cắt 10,5/13 kV", [("MC 933", "dong"), ("MC 934", "dong"), ("MC 941", "cat"), ("MC 942", "cat")]),
    ],
    "TKT": [
        ("tkt-cap-220kv", "Trạng thái máy cắt 220 kV", [("MC 271", "dong"), ("MC 272", "dong"), ("MC 200", "cat")]),
        ("tkt-cap-22kv", "Trạng thái máy cắt 22 kV", [("MC 471", "dong"), ("MC 472", "cat")]),
        ("tkt-tu-dung", "Trạng thái máy cắt tự dùng", [("MC 431", "dong"), ("MC 432", "cat")]),
    ],
}


def seed_templates(apps, schema_editor):
    NhaMay = apps.get_model("tochuc", "NhaMay")
    Template = apps.get_model("nhatkyvanhanh", "MauTrangThaiThietBiCa")
    Group = apps.get_model("nhatkyvanhanh", "NhomMauTrangThaiThietBiCa")
    Detail = apps.get_model("nhatkyvanhanh", "ChiTietMauTrangThaiThietBiCa")
    for code, groups in PRESETS.items():
        plant = NhaMay.objects.filter(ma_nha_may=code).first()
        if not plant or Template.objects.filter(nha_may=plant).exists():
            continue
        template = Template.objects.create(nha_may=plant, ten_mau=f"Mẫu vận hành {code}", phien_ban=1, dang_ap_dung=True)
        for group_order, (group_code, title, devices) in enumerate(groups, 1):
            group = Group.objects.create(mau=template, ma_nhom=group_code, tieu_de=title, thu_tu=group_order)
            for device_order, (device_code, state) in enumerate(devices, 1):
                Detail.objects.create(nhom=group, ma_hien_thi=device_code, trang_thai_mac_dinh=state, thu_tu=device_order)


class Migration(migrations.Migration):
    dependencies = [("nhatkyvanhanh", "0058_sogiaonhancavh_ghi_chu_van_hanh_bo_sung_and_more")]
    operations = [migrations.RunPython(seed_templates, migrations.RunPython.noop)]
