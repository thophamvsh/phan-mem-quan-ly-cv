from django.db import migrations, models


def migrate_legacy_permissions(apps, schema_editor):
    UserRole = apps.get_model("core", "UserRole")
    UserProfile = apps.get_model("core", "UserProfile")

    UserProfile.objects.filter(
        can_edit_diesel_operation_logbooks=True,
    ).update(can_edit_own_diesel_operation_logbooks=True)
    UserProfile.objects.filter(
        can_delete_diesel_operation_logbooks=True,
    ).update(can_delete_own_diesel_operation_logbooks=True)
    UserProfile.objects.filter(
        can_create_diesel_operation_logbooks=True,
    ).update(
        can_edit_own_diesel_operation_logbooks=True,
        can_delete_own_diesel_operation_logbooks=True,
    )

    for role in UserRole.objects.all().iterator():
        permissions = dict(role.permissions or {})
        can_create = bool(permissions.get("can_create_diesel_operation_logbooks"))
        can_edit_own = can_create or bool(
            permissions.get("can_edit_diesel_operation_logbooks")
        )
        can_delete_own = can_create or bool(
            permissions.get("can_delete_diesel_operation_logbooks")
        )
        if can_edit_own:
            permissions["can_edit_own_diesel_operation_logbooks"] = True
        if can_delete_own:
            permissions["can_delete_own_diesel_operation_logbooks"] = True
        if can_edit_own or can_delete_own:
            role.permissions = permissions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0034_userprofile_so_an_toan_object_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_own_diesel_operation_logbooks",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen sua so nhat ky van hanh Diesel do minh tao",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_delete_own_diesel_operation_logbooks",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen xoa so nhat ky van hanh Diesel do minh tao",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_manage_all_diesel_operation_logbooks",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen sua va xoa tat ca so nhat ky van hanh Diesel",
            ),
        ),
        migrations.RunPython(migrate_legacy_permissions, migrations.RunPython.noop),
    ]
