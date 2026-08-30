from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_userprofile_weekly_switch_template_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='can_confirm_weekly_equipment_switch_logs',
            field=models.BooleanField(
                default=False,
                verbose_name='Duyệt / Xác nhận sổ chuyển đổi thiết bị tuần',
                help_text='Có quyền ký duyệt xác nhận và khóa sổ chuyển đổi thiết bị tuần',
            ),
        ),
    ]
