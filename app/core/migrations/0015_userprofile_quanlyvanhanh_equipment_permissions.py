from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_userprofile_can_create_diesel_operation_logbooks_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='can_create_equipment',
            field=models.BooleanField(default=False, help_text='Co quyen tao thiet bi van hanh'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_create_operation_parameters',
            field=models.BooleanField(default=False, help_text='Co quyen them thong so van hanh'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_delete_equipment',
            field=models.BooleanField(default=False, help_text='Co quyen xoa thiet bi van hanh'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_delete_operation_parameters',
            field=models.BooleanField(default=False, help_text='Co quyen xoa thong so van hanh'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_edit_equipment',
            field=models.BooleanField(default=False, help_text='Co quyen sua thiet bi van hanh'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_edit_operation_parameters',
            field=models.BooleanField(default=False, help_text='Co quyen sua thong so van hanh'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_view_equipment',
            field=models.BooleanField(default=True, help_text='Co quyen xem danh sach thiet bi van hanh'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='can_view_operation_parameters',
            field=models.BooleanField(default=True, help_text='Co quyen xem thong so van hanh'),
        ),
    ]
