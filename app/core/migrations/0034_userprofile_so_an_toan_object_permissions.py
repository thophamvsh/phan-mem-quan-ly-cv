from django.db import migrations, models


def migrate_legacy_permissions(apps, schema_editor):
    UserRole = apps.get_model("core", "UserRole")
    UserProfile = apps.get_model("core", "UserProfile")

    UserProfile.objects.filter(can_edit_so_an_toan_dau_gio=True).update(
        can_edit_own_so_an_toan_dau_gio=True,
    )
    UserProfile.objects.filter(can_delete_so_an_toan_dau_gio=True).update(
        can_delete_own_so_an_toan_dau_gio=True,
    )

    for role in UserRole.objects.all().iterator():
        permissions = dict(role.permissions or {})
        changed = False
        if permissions.get("can_edit_so_an_toan_dau_gio"):
            permissions["can_edit_own_so_an_toan_dau_gio"] = True
            changed = True
        if permissions.get("can_delete_so_an_toan_dau_gio"):
            permissions["can_delete_own_so_an_toan_dau_gio"] = True
            changed = True
        if changed:
            role.permissions = permissions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_backfill_so_an_toan_create_permission"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_own_so_an_toan_dau_gio",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen sua so an toan dau gio do minh tao",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_delete_own_so_an_toan_dau_gio",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen xoa so an toan dau gio do minh tao",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_manage_all_so_an_toan_dau_gio",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen sua va xoa tat ca so an toan dau gio",
            ),
        ),
        migrations.RunPython(migrate_legacy_permissions, migrations.RunPython.noop),
    ]
