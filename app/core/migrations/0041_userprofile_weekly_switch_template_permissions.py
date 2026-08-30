from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_userprofile_can_create_admin_shift_duty_rosters_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='can_view_weekly_equipment_switch_templates',
            field=models.BooleanField(
                default=True,
                verbose_name='Xem mẫu chuyển đổi thiết bị tuần',
                help_text='Có quyền xem cấu hình danh mục mẫu chuyển đổi thiết bị tuần',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_create_weekly_equipment_switch_templates',
            field=models.BooleanField(
                default=False,
                verbose_name='Thêm thiết bị vào mẫu tuần',
                help_text='Có quyền thêm thiết bị mới vào mẫu chuyển đổi thiết bị tuần',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_edit_weekly_equipment_switch_templates',
            field=models.BooleanField(
                default=False,
                verbose_name='Sửa mẫu chuyển đổi thiết bị tuần',
                help_text='Có quyền chỉnh sửa thông tin thiết bị trong mẫu chuyển đổi thiết bị tuần',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_delete_weekly_equipment_switch_templates',
            field=models.BooleanField(
                default=False,
                verbose_name='Xóa thiết bị khỏi mẫu tuần',
                help_text='Có quyền xóa thiết bị khỏi mẫu chuyển đổi thiết bị tuần',
            ),
        ),
    ]
