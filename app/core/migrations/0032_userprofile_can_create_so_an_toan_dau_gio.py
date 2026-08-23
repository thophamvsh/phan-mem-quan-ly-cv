from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_userprofile_can_receive_alert_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="can_create_so_an_toan_dau_gio",
            field=models.BooleanField(
                default=False,
                help_text="Co quyen tao so an toan dau gio",
            ),
        ),
    ]
