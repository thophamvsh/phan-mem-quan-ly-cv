from django.db import migrations


def backfill_factory(apps, schema_editor):
    SuKien = apps.get_model("nhatkyvanhanh", "SuKien")
    SogiaonhancaVH = apps.get_model("nhatkyvanhanh", "SogiaonhancaVH")
    UserProfile = apps.get_model("core", "UserProfile")

    profile_factory_by_user_id = {
        profile.user_id: profile.nha_may_id
        for profile in UserProfile.objects.exclude(nha_may_id__isnull=True)
    }

    for su_kien in SuKien.objects.filter(nha_may_id__isnull=True).only(
        "id",
        "nguoi_tao_id",
        "ben_ghi_nhan_su_kien_id",
        "nha_may_id",
    ):
        factory_id = (
            profile_factory_by_user_id.get(su_kien.nguoi_tao_id)
            or profile_factory_by_user_id.get(su_kien.ben_ghi_nhan_su_kien_id)
        )
        if factory_id:
            su_kien.nha_may_id = factory_id
            su_kien.save(update_fields=["nha_may"])

    for so in SogiaonhancaVH.objects.filter(nha_may_id__isnull=True).only(
        "id",
        "user_giao_ca_id",
        "user_nhan_ca_id",
        "nha_may_id",
    ):
        factory_id = (
            profile_factory_by_user_id.get(so.user_giao_ca_id)
            or profile_factory_by_user_id.get(so.user_nhan_ca_id)
        )
        if factory_id:
            so.nha_may_id = factory_id
            so.save(update_fields=["nha_may"])


class Migration(migrations.Migration):

    dependencies = [
        ("nhatkyvanhanh", "0012_add_factory_scope"),
    ]

    operations = [
        migrations.RunPython(backfill_factory, migrations.RunPython.noop),
    ]
