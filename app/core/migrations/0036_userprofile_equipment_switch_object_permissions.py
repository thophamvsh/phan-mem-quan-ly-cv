from django.db import migrations, models


PERMISSION_GROUPS = (
    (
        "weekly_equipment_switch_logs",
        "can_create_weekly_equipment_switch_logs",
        "can_edit_weekly_equipment_switch_logs",
        "can_delete_weekly_equipment_switch_logs",
    ),
    (
        "monthly_equipment_switch_logs",
        "can_create_monthly_equipment_switch_logs",
        "can_edit_monthly_equipment_switch_logs",
        "can_delete_monthly_equipment_switch_logs",
    ),
)


def migrate_legacy_permissions(apps, schema_editor):
    UserRole = apps.get_model("core", "UserRole")
    UserProfile = apps.get_model("core", "UserProfile")

    for suffix, create_name, edit_name, delete_name in PERMISSION_GROUPS:
        edit_own_name = f"can_edit_own_{suffix}"
        delete_own_name = f"can_delete_own_{suffix}"

        UserProfile.objects.filter(**{edit_name: True}).update(
            **{edit_own_name: True}
        )
        UserProfile.objects.filter(**{delete_name: True}).update(
            **{delete_own_name: True}
        )
        UserProfile.objects.filter(**{create_name: True}).update(
            **{edit_own_name: True, delete_own_name: True}
        )

    for role in UserRole.objects.all().iterator():
        permissions = dict(role.permissions or {})
        changed = False
        for suffix, create_name, edit_name, delete_name in PERMISSION_GROUPS:
            can_create = bool(permissions.get(create_name))
            if can_create or bool(permissions.get(edit_name)):
                permissions[f"can_edit_own_{suffix}"] = True
                changed = True
            if can_create or bool(permissions.get(delete_name)):
                permissions[f"can_delete_own_{suffix}"] = True
                changed = True
        if changed:
            role.permissions = permissions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_userprofile_diesel_object_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_own_weekly_equipment_switch_logs",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen sua so va lan chuyen doi thiet bi tuan do minh tao",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_delete_own_weekly_equipment_switch_logs",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen xoa so va lan chuyen doi thiet bi tuan do minh tao",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_manage_all_weekly_equipment_switch_logs",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen sua va xoa tat ca so chuyen doi thiet bi tuan",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_own_monthly_equipment_switch_logs",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen sua so chuyen doi TB thang do minh tao",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_delete_own_monthly_equipment_switch_logs",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen xoa so chuyen doi TB thang do minh tao",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_manage_all_monthly_equipment_switch_logs",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen sua va xoa tat ca so chuyen doi TB thang",
            ),
        ),
        migrations.RunPython(migrate_legacy_permissions, migrations.RunPython.noop),
    ]
