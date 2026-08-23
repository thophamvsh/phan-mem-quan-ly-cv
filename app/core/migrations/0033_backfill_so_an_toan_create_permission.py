import unicodedata

from django.db import migrations


def _normalize(value):
    normalized = unicodedata.normalize("NFD", str(value or ""))
    return " ".join(
        "".join(char for char in normalized if unicodedata.category(char) != "Mn")
        .replace("đ", "d")
        .replace("Đ", "D")
        .lower()
        .split()
    )


def backfill_create_permission(apps, schema_editor):
    UserRole = apps.get_model("core", "UserRole")
    UserProfile = apps.get_model("core", "UserProfile")

    eligible_role_ids = []
    for role in UserRole.objects.all().iterator():
        permissions = dict(role.permissions or {})
        should_create = bool(permissions.get("can_create_operation_logbooks")) or (
            "truong ca" in _normalize(role.name)
        )
        if should_create:
            permissions["can_create_so_an_toan_dau_gio"] = True
            role.permissions = permissions
            role.save(update_fields=["permissions"])
            eligible_role_ids.append(role.id)

    profiles = UserProfile.objects.filter(can_create_operation_logbooks=True)
    profiles.update(can_create_so_an_toan_dau_gio=True)

    shift_leader_ids = [
        profile.id
        for profile in UserProfile.objects.only("id", "chuc_danh").iterator()
        if _normalize(profile.chuc_danh) == "truong ca"
    ]
    if shift_leader_ids:
        UserProfile.objects.filter(id__in=shift_leader_ids).update(
            can_create_so_an_toan_dau_gio=True,
        )

    if eligible_role_ids:
        UserProfile.objects.filter(role_id__in=eligible_role_ids).update(
            can_create_so_an_toan_dau_gio=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_userprofile_can_create_so_an_toan_dau_gio"),
    ]

    operations = [
        migrations.RunPython(backfill_create_permission, migrations.RunPython.noop),
    ]
