import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "quanlycatruc",
            "0018_alter_donvitochuc_nha_may_alter_kiptruc_nha_may_and_more",
        ),
        ("tochuc", "0003_shared_organization_directory"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="nhansu",
                    name="bo_phan",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nhan_su",
                        to="tochuc.bophan",
                    ),
                ),
                migrations.AlterField(
                    model_name="nhomlichtruc",
                    name="bo_phan",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nhom_lich_truc",
                        to="tochuc.bophan",
                    ),
                ),
                migrations.RemoveField(
                    model_name="donvitochuc",
                    name="don_vi_cha",
                ),
                migrations.RemoveField(
                    model_name="donvitochuc",
                    name="nha_may",
                ),
                migrations.AlterField(
                    model_name="nhomlichtruc",
                    name="don_vi",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nhom_lich_truc",
                        to="tochuc.donvitochuc",
                    ),
                ),
                migrations.AlterField(
                    model_name="nhansu",
                    name="don_vi",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="nhan_su",
                        to="tochuc.donvitochuc",
                    ),
                ),
                migrations.DeleteModel(name="BoPhan"),
                migrations.DeleteModel(name="DonViToChuc"),
            ],
        ),
    ]
