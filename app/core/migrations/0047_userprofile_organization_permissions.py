from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0046_userprofile_individual_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="can_manage_organization_directory",
            field=models.BooleanField(
                default=False,
                help_text="Có quyền tạo, sửa và ngừng sử dụng đơn vị, bộ phận",
            ),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_view_organization_directory",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Có quyền xem danh mục đơn vị và bộ phận trong phạm vi nhà máy"
                ),
            ),
        ),
    ]
