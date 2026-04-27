# App Quản Lý Vận Hành

## Giới thiệu

App Django để quản lý vận hành hệ thống.

## Cấu trúc

```
quanlyvanhanh/
├── __init__.py
├── admin.py           # Cấu hình Django Admin
├── apps.py            # Cấu hình app
├── models.py          # Định nghĩa models/database tables
├── views.py           # Logic xử lý requests
├── urls.py            # URL routing
├── serializers.py     # REST API serializers
├── tests.py           # Unit tests
└── migrations/        # Database migrations
```

## Sử dụng

### 1. Tạo Model

Thêm models vào `models.py`:

```python
from django.db import models

class YourModel(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'your_table_name'
        verbose_name = 'Your Model'
        verbose_name_plural = 'Your Models'
```

### 2. Tạo Migrations

```bash
docker-compose exec app python manage.py makemigrations quanlyvanhanh
docker-compose exec app python manage.py migrate
```

### 3. Tạo Serializer

Thêm vào `serializers.py`:

```python
from rest_framework import serializers
from .models import YourModel

class YourModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = YourModel
        fields = '__all__'
```

### 4. Tạo Views

Thêm vào `views.py`:

```python
from rest_framework import viewsets
from .models import YourModel
from .serializers import YourModelSerializer

class YourModelViewSet(viewsets.ModelViewSet):
    queryset = YourModel.objects.all()
    serializer_class = YourModelSerializer
```

### 5. Cấu hình URLs

Thêm vào `urls.py`:

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'your-endpoint', views.YourModelViewSet)

app_name = 'quanlyvanhanh'

urlpatterns = [
    path('', include(router.urls)),
]
```

### 6. Đăng ký Admin

Thêm vào `admin.py`:

```python
from django.contrib import admin
from .models import YourModel

@admin.register(YourModel)
class YourModelAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'created_at']
    search_fields = ['name']
```

## API Endpoints

Sau khi cấu hình, endpoints sẽ có dạng:

- `GET /api/quanlyvanhanh/your-endpoint/` - Lấy danh sách
- `POST /api/quanlyvanhanh/your-endpoint/` - Tạo mới
- `GET /api/quanlyvanhanh/your-endpoint/{id}/` - Lấy chi tiết
- `PUT /api/quanlyvanhanh/your-endpoint/{id}/` - Cập nhật
- `DELETE /api/quanlyvanhanh/your-endpoint/{id}/` - Xóa

## Lưu ý

- App đã được đăng ký trong `settings.py` > `INSTALLED_APPS`
- URLs đã được include trong `app/urls.py` với prefix `/api/quanlyvanhanh/`
- Sử dụng Docker để chạy các lệnh Django: `docker-compose exec app python manage.py <command>`
