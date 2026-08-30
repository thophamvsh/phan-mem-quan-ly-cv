from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_userprofile_can_confirm_weekly_equipment_switch_logs'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='can_view_monthly_equipment_switch_templates',
            field=models.BooleanField(
                default=True,
                verbose_name='Xem mẫu chuyển đổi TB tháng',
                help_text='Có quyền xem cấu hình danh mục mẫu chuyển đổi thiết bị tháng',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_create_monthly_equipment_switch_templates',
            field=models.BooleanField(
                default=False,
                verbose_name='Thêm thiết bị vào mẫu tháng',
                help_text='Có quyền thêm thiết bị mới vào mẫu chuyển đổi thiết bị tháng',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_edit_monthly_equipment_switch_templates',
            field=models.BooleanField(
                default=False,
                verbose_name='Sửa mẫu chuyển đổi TB tháng',
                help_text='Có quyền chỉnh sửa thông tin thiết bị trong mẫu chuyển đổi thiết bị tháng',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_delete_monthly_equipment_switch_templates',
            field=models.BooleanField(
                default=False,
                verbose_name='Xóa thiết bị khỏi mẫu tháng',
                help_text='Có quyền xóa thiết bị khỏi mẫu chuyển đổi thiết bị tháng',
            ),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_confirm_monthly_equipment_switch_logs',
            field=models.BooleanField(
                default=False,
                verbose_name='Duyệt / Xác nhận sổ chuyển đổi TB tháng',
                help_text='Có quyền ký duyệt xác nhận và khóa sổ chuyển đổi thiết bị tháng',
            ),
        ),
    ]
