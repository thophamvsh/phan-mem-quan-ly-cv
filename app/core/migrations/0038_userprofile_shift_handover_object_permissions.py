from django.db import migrations, models


def migrate_legacy_permissions(apps, schema_editor):
    UserRole = apps.get_model("core", "UserRole")
    UserProfile = apps.get_model("core", "UserProfile")

    UserProfile.objects.filter(can_edit_shift_handover_logs=True).update(
        can_edit_own_shift_handover_logs=True
    )
    UserProfile.objects.filter(can_delete_shift_handover_logs=True).update(
        can_delete_own_shift_handover_logs=True
    )
    UserProfile.objects.filter(can_create_shift_handover_logs=True).update(
        can_edit_own_shift_handover_logs=True,
        can_delete_own_shift_handover_logs=True,
    )

    for role in UserRole.objects.all().iterator():
        permissions = dict(role.permissions or {})
        changed = False
        can_create = bool(permissions.get("can_create_shift_handover_logs"))
        if can_create or bool(permissions.get("can_edit_shift_handover_logs")):
            permissions["can_edit_own_shift_handover_logs"] = True
            changed = True
        if can_create or bool(permissions.get("can_delete_shift_handover_logs")):
            permissions["can_delete_own_shift_handover_logs"] = True
            changed = True
        if changed:
            role.permissions = permissions
            role.save(update_fields=["permissions"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_operation_event_permission_help_texts"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_own_shift_handover_logs",
            field=models.BooleanField(
                default=False,
                help_text="Có quyền sửa sổ giao nhận ca vận hành do mình tạo khi chưa nhận ca",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_delete_own_shift_handover_logs",
            field=models.BooleanField(
                default=False,
                help_text="Có quyền xóa sổ giao nhận ca vận hành do mình tạo khi chưa nhận ca",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_manage_all_shift_handover_logs",
            field=models.BooleanField(
                default=False,
                help_text="Có quyền sửa và xóa tất cả sổ giao nhận ca vận hành khi chưa nhận ca",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_view_shift_handover_logs",
            field=models.BooleanField(
                default=True,
                help_text="Có quyền xem sổ giao nhận ca vận hành",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_create_shift_handover_logs",
            field=models.BooleanField(
                default=False,
                help_text="Có quyền tạo sổ giao nhận ca vận hành",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_receive_shift_handover_logs",
            field=models.BooleanField(
                default=False,
                help_text="Có quyền ký nhận ca trong sổ giao nhận ca vận hành",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_edit_shift_handover_logs",
            field=models.BooleanField(
                default=False,
                help_text="Quyền cũ: sửa sổ giao nhận ca vận hành",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_delete_shift_handover_logs",
            field=models.BooleanField(
                default=False,
                help_text="Quyền cũ: xóa sổ giao nhận ca vận hành",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_view_shift_handover_directives",
            field=models.BooleanField(
                default=False,
                help_text="Có quyền xem lưu ý chỉ đạo sổ giao nhận ca vận hành",
            ),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_create_shift_handover_directives",
            field=models.BooleanField(
                default=False,
                help_text="Có quyền tạo lưu ý chỉ đạo sổ giao nhận ca vận hành khi chưa nhận ca",
            ),
        ),
        migrations.RunPython(migrate_legacy_permissions, migrations.RunPython.noop),
    ]
