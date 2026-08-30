from django.db import migrations


OLD_CYCLE = [
    {"team": "HC2"}, {"team": "HC2"}, {"team": "HC2"},
    {"team": "HC1", "from": "HC2", "transition": True},
    {"team": "HC1"}, {"team": "HC1"}, {"team": "HC1"}, {"team": "HC1"},
    {"team": "HC2", "from": "HC1", "transition": True},
    {"team": "HC2"}, {"team": "HC2"}, {"team": "HC2"},
]

NEW_CYCLE = [
    {"team": "HC2"}, {"team": "HC2"}, {"team": "HC2"},
    {"team": "HC1", "from": "HC2", "transition": True},
    {"team": "HC1"}, {"team": "HC1"}, {"team": "HC1"}, {"team": "HC1"}, {"team": "HC1"},
    {"team": "HC2", "from": "HC1", "transition": True},
    {"team": "HC2"}, {"team": "HC2"},
]


def align_default_cycles(apps, schema_editor):
    Template = apps.get_model("quanlycatruc", "MauChuKyCaTruc")
    for template in Template.objects.filter(chu_ky_hanh_chinh=OLD_CYCLE):
        template.chu_ky_hanh_chinh = NEW_CYCLE
        template.save(update_fields=["chu_ky_hanh_chinh"])


def restore_default_cycles(apps, schema_editor):
    Template = apps.get_model("quanlycatruc", "MauChuKyCaTruc")
    for template in Template.objects.filter(chu_ky_hanh_chinh=NEW_CYCLE):
        template.chu_ky_hanh_chinh = OLD_CYCLE
        template.save(update_fields=["chu_ky_hanh_chinh"])


class Migration(migrations.Migration):
    dependencies = [("quanlycatruc", "0007_unique_batch_for_legacy_adjustments")]

    operations = [migrations.RunPython(align_default_cycles, restore_default_cycles)]
