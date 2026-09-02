from django.db import migrations


MODEL_MAPPINGS = (
    ("khovattu", "bang_nha_may", "tochuc", "nhamay"),
    ("quanlycatruc", "donvitochuc", "tochuc", "donvitochuc"),
    ("quanlycatruc", "bophan", "tochuc", "bophan"),
    ("quanlycatruc", "nhansu", "tochuc", "nhansu"),
)
PERMISSION_ACTIONS = ("add", "change", "delete", "view")


def transfer_permissions(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    for source_app, source_model, target_app, target_model in MODEL_MAPPINGS:
        source_type = ContentType.objects.filter(
            app_label=source_app,
            model=source_model,
        ).first()
        target_type = ContentType.objects.filter(
            app_label=target_app,
            model=target_model,
        ).first()
        if source_type is None or target_type is None:
            continue

        for action in PERMISSION_ACTIONS:
            source = Permission.objects.filter(
                content_type=source_type,
                codename=f"{action}_{source_model}",
            ).first()
            target = Permission.objects.filter(
                content_type=target_type,
                codename=f"{action}_{target_model}",
            ).first()
            if source is None or target is None:
                continue
            target.user_set.add(*source.user_set.all())
            target.group_set.add(*source.group_set.all())


class Migration(migrations.Migration):
    dependencies = [
        ("tochuc", "0004_shared_staff_directory"),
    ]

    operations = [
        migrations.RunPython(transfer_permissions, migrations.RunPython.noop),
    ]
