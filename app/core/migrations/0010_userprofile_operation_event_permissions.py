from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_auto_20251004_0318"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="can_view_operation_events",
            field=models.BooleanField(default=True, help_text="Co quyen xem nhat ky su kien van hanh"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_create_operation_events",
            field=models.BooleanField(default=False, help_text="Co quyen tao moi su kien van hanh"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_own_operation_events",
            field=models.BooleanField(default=True, help_text="Co quyen sua su kien van hanh do minh tao khi chua ghi nhan"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_all_operation_events",
            field=models.BooleanField(default=False, help_text="Co quyen sua tat ca su kien van hanh"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_delete_own_operation_events",
            field=models.BooleanField(default=True, help_text="Co quyen xoa su kien van hanh do minh tao khi chua khoa"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_delete_all_operation_events",
            field=models.BooleanField(default=False, help_text="Co quyen xoa tat ca su kien van hanh"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_acknowledge_operation_events",
            field=models.BooleanField(default=False, help_text="Co quyen ghi nhan su kien van hanh"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_process_operation_events",
            field=models.BooleanField(default=False, help_text="Co quyen xu ly/khac phuc su kien van hanh"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_confirm_operation_events",
            field=models.BooleanField(default=False, help_text="Co quyen xac nhan xu ly su kien van hanh"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_add_event_developments",
            field=models.BooleanField(default=False, help_text="Co quyen them dien bien su kien van hanh"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_own_event_developments",
            field=models.BooleanField(default=True, help_text="Co quyen sua dien bien su kien do minh tao"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_all_event_developments",
            field=models.BooleanField(default=False, help_text="Co quyen sua tat ca dien bien su kien"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_own_remediations",
            field=models.BooleanField(default=True, help_text="Co quyen sua noi dung khac phuc do minh tao khi chua xac nhan"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="can_edit_all_remediations",
            field=models.BooleanField(default=False, help_text="Co quyen sua tat ca noi dung khac phuc khi chua xac nhan"),
        ),
    ]
