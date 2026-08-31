import django.db.models.deletion
from django.db import migrations, models


def move_staff_content_type(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="quanlycatruc",
        model="nhansu",
    ).update(app_label="tochuc")


def restore_staff_content_type(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="tochuc",
        model="nhansu",
    ).update(app_label="quanlycatruc")


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("quanlycatruc", "0019_move_organization_directory_state"),
        ("tochuc", "0004_shared_staff_directory"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="phamvinhansucatruc",
                    name="nhan_su",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pham_vi_ca_truc",
                        to="tochuc.nhansu",
                    ),
                ),
                migrations.AlterField(
                    model_name="thanhvienkiptruc",
                    name="nhan_su",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="phan_cong_kip_truc",
                        to="tochuc.nhansu",
                    ),
                ),
                migrations.AlterField(
                    model_name="chitietphuonganphancongca",
                    name="nhan_su",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cac_phuong_an_phan_cong",
                        to="tochuc.nhansu",
                    ),
                ),
                migrations.AlterField(
                    model_name="phancongnhansuhcngay",
                    name="nhan_su",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="phan_cong_hc_theo_ngay",
                        to="tochuc.nhansu",
                    ),
                ),
                migrations.AlterField(
                    model_name="dieuchinhnhansucatruc",
                    name="nhan_su_vang",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cac_ca_vang",
                        to="tochuc.nhansu",
                    ),
                ),
                migrations.AlterField(
                    model_name="dieuchinhnhansucatruc",
                    name="nhan_su_thay",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cac_ca_truc_thay",
                        to="tochuc.nhansu",
                    ),
                ),
                migrations.DeleteModel(name="NhanSu"),
            ],
        ),
        migrations.RunPython(
            move_staff_content_type,
            restore_staff_content_type,
        ),
    ]
