from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("quanlyvanhanh", "0001_initial"),
        ("nhatkyvanhanh", "0034_sochuyendoithietbituan_ca_truc"),
    ]

    operations = [
        migrations.AddField(
            model_name="sukien",
            name="thiet_bi",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="su_kiens",
                to="quanlyvanhanh.thietbi",
                verbose_name="Thiet bi lien quan",
            ),
        ),
    ]
