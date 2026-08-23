from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0036_userprofile_equipment_switch_object_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="can_view_operation_events",
            field=models.BooleanField(default=True, help_text="Có quyền xem nhật ký sự kiện vận hành"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_create_operation_events",
            field=models.BooleanField(default=False, help_text="Có quyền tạo mới sự kiện vận hành"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_edit_own_operation_events",
            field=models.BooleanField(default=True, help_text="Có quyền sửa sự kiện vận hành do mình tạo khi chưa ghi nhận"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_edit_all_operation_events",
            field=models.BooleanField(default=False, help_text="Có quyền sửa tất cả sự kiện vận hành chưa ghi nhận"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_delete_own_operation_events",
            field=models.BooleanField(default=True, help_text="Có quyền xóa sự kiện vận hành do mình tạo khi chưa khóa"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_delete_all_operation_events",
            field=models.BooleanField(default=False, help_text="Có quyền xóa tất cả sự kiện vận hành chưa khóa"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_acknowledge_operation_events",
            field=models.BooleanField(default=False, help_text="Có quyền ghi nhận sự kiện vận hành"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_process_operation_events",
            field=models.BooleanField(default=False, help_text="Có quyền xử lý/khắc phục sự kiện vận hành"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_confirm_operation_events",
            field=models.BooleanField(default=False, help_text="Có quyền xác nhận xử lý sự kiện vận hành"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_add_event_developments",
            field=models.BooleanField(default=False, help_text="Có quyền thêm diễn biến sự kiện vận hành"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_edit_own_event_developments",
            field=models.BooleanField(default=True, help_text="Có quyền sửa diễn biến sự kiện do mình tạo"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_edit_all_event_developments",
            field=models.BooleanField(default=False, help_text="Có quyền sửa tất cả diễn biến sự kiện"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_edit_own_remediations",
            field=models.BooleanField(default=True, help_text="Có quyền sửa nội dung khắc phục do mình tạo khi chưa xác nhận"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_edit_all_remediations",
            field=models.BooleanField(default=False, help_text="Có quyền sửa tất cả nội dung khắc phục khi chưa xác nhận"),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="can_edit_leadership_directives",
            field=models.BooleanField(default=False, help_text="Có quyền nhập chỉ đạo sự kiện vận hành"),
        ),
    ]
