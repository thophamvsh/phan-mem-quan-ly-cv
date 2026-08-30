from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0045_alter_userprofile_nha_may"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="individual_permissions",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Các quyền ngoại lệ được cộng thêm vào quyền của vai trò. "
                    "Không dùng trường này để thu hồi quyền đã có từ vai trò."
                ),
                verbose_name="Quyền cấp thêm cho cá nhân",
            ),
        ),
    ]
