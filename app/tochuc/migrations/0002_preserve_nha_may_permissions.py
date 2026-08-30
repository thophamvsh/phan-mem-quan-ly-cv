from django.db import migrations


PERMISSION_ACTIONS = ("add", "change", "delete", "view")


def copy_permissions(apps, schema_editor, *, reverse=False):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    source_app, source_model = (
        ("tochuc", "nhamay") if reverse else ("khovattu", "bang_nha_may")
    )
    target_app, target_model = (
        ("khovattu", "bang_nha_may") if reverse else ("tochuc", "nhamay")
    )
    source_type = ContentType.objects.filter(
        app_label=source_app,
        model=source_model,
    ).first()
    if source_type is None:
        return

    target_type, _ = ContentType.objects.get_or_create(
        app_label=target_app,
        model=target_model,
    )
    for action in PERMISSION_ACTIONS:
        source = Permission.objects.filter(
            content_type=source_type,
            codename=f"{action}_{source_model}",
        ).first()
        if source is None:
            continue
        target, _ = Permission.objects.get_or_create(
            content_type=target_type,
            codename=f"{action}_{target_model}",
            defaults={"name": source.name.replace("Bang nha may", "Nha may")},
        )
        target.user_set.add(*source.user_set.all())
        target.group_set.add(*source.group_set.all())


def forwards(apps, schema_editor):
    copy_permissions(apps, schema_editor)


def backwards(apps, schema_editor):
    copy_permissions(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [
        ("khovattu", "0003_move_nha_may_to_tochuc"),
        ("tochuc", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
