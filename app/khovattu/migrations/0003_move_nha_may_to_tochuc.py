import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Move model ownership without touching the existing PostgreSQL table."""

    dependencies = [
        ("khovattu", "0002_bang_de_nghi_nhap_nguoi_de_nghi_and_more"),
        ("tochuc", "0001_initial"),
        ("core", "0045_alter_userprofile_nha_may"),
        ("nhatkyvanhanh", "0056_alter_bangphancongnhiemvuhc_nha_may_and_more"),
        ("quanlycatruc", "0018_alter_donvitochuc_nha_may_alter_kiptruc_nha_may_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="bang_vat_tu",
                    name="bang_nha_may",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="vat_tu",
                        to="tochuc.nhamay",
                    ),
                ),
                migrations.DeleteModel(name="Bang_nha_may"),
            ],
        ),
    ]
