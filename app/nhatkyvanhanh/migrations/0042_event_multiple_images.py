import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("nhatkyvanhanh", "0041_nhansusogiaonhancavh")]

    operations = [
        migrations.CreateModel(
            name="AnhTruocSuCo",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("hinh_anh", models.ImageField(upload_to="operations/nhat_ky_su_kien/truoc_su_co/")),
                ("su_kien", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="anh_truoc_su_cos", to="nhatkyvanhanh.sukien")),
            ],
            options={"verbose_name": "Ảnh trước sự cố", "verbose_name_plural": "Ảnh trước sự cố", "ordering": ["created_at", "id"]},
        ),
        migrations.CreateModel(
            name="AnhSauXuLy",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("hinh_anh", models.ImageField(upload_to="operations/nhat_ky_su_kien/sau_xu_ly/")),
                ("khac_phuc", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="anh_sau_xu_lys", to="nhatkyvanhanh.khacphucsukien")),
            ],
            options={"verbose_name": "Ảnh sau xử lý", "verbose_name_plural": "Ảnh sau xử lý", "ordering": ["created_at", "id"]},
        ),
    ]
