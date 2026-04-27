from django.db import migrations, models
import django.db.models.deletion


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
        ("khovattu", "0002_bang_de_nghi_nhap_nguoi_de_nghi_and_more"),
        ("nhatkyvanhanh", "0011_remove_khacphucsukien_lich_su_xu_ly_tiep_tuc"),
    ]

    operations = [
        migrations.AddField(
            model_name="sukien",
            name="nha_may",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="su_kiens",
                to="khovattu.bang_nha_may",
                verbose_name="Nha may",
            ),
        ),
        migrations.AddField(
            model_name="sogiaonhancavh",
            name="nha_may",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="so_giao_nhan_ca_vh",
                to="khovattu.bang_nha_may",
                verbose_name="Nha may",
            ),
        ),
        migrations.RunPython(backfill_factory, migrations.RunPython.noop),
    ]
