# Cấu trúc & Hướng dẫn Chi tiết về module `app/core`

Module `core` đóng vai trò là xương sống của hệ thống, quản lý tài khoản người dùng, phân quyền động dựa trên vai trò (Dynamic RBAC), giới hạn phạm vi truy cập theo nhà máy (Factory Scoping), và ghi nhật ký hoạt động hệ thống (System Logging & Audit Trail).

---

## 1. Bản đồ Cấu trúc File trong `app/core`

```text
app/core/
├── management/
│   └── commands/
│       └── wait_for_db.py     # Lệnh kiểm tra và đợi database sẵn sàng
├── migrations/                # Thư mục chứa các file migration cơ sở dữ liệu
├── tests/                     # Bộ kiểm thử (Unit Tests)
│   ├── test_api.py            # Test các API đăng ký, đăng nhập, profile
│   ├── test_commands.py       # Test lệnh wait_for_db
│   ├── test_factory_scope.py  # Test cơ chế phân quyền nhà máy
│   ├── test_logging.py        # Test hệ thống ghi log và tự động dọn dẹp
│   └── test_models.py         # Test đồng bộ quyền giữa UserRole và UserProfile
├── admin.py                   # Cấu hình Django Admin (Giao diện quản lý)
├── apps.py                    # Đăng ký AppConfig và kích hoạt Signals
├── auth_views.py              # Xử lý các API Authentication (Login, Logout, Change Password)
├── factory_scope.py           # Bộ lọc phạm vi nhà máy & kiểm tra quyền
├── middleware.py              # Middleware DRF Authentication sớm phục vụ ghi log
├── models.py                  # Định nghĩa cấu trúc cơ sở dữ liệu (Database Models)
├── profile_views.py           # Xử lý các API xem và cập nhật Hồ sơ cá nhân
├── serializers.py             # Bộ tuần tự hóa dữ liệu cho API (DRF Serializers)
├── signals.py                 # Lắng nghe các sự kiện Auth (Login, Logout) để ghi log
├── tasks.py                   # Các tác vụ chạy ngầm định kỳ (Celery Tasks)
└── urls.py                    # Định tuyến API (URL Routing)
```

---

## 2. Chi tiết Chức năng từng File

### 2.1. Cấu trúc Mô hình Dữ liệu (`models.py`)
Định nghĩa 4 thực thể chính:
1. **`User`**: Kế thừa `AbstractBaseUser` và `PermissionsMixin`. Sử dụng `email` làm định danh chính thay vì username.
2. **`UserRole`**: Vai trò người dùng động do Quản trị viên tự định nghĩa (ví dụ: Trưởng ca, Trưởng ngành, Nhân viên...). Quyền hạn được lưu dưới dạng JSON ở trường `permissions`. Khi cập nhật quyền trên `UserRole`, hệ thống sẽ tự động kích hoạt cập nhật (cascade update) toàn bộ hồ sơ `UserProfile` liên kết để đồng bộ quyền tức thời.
3. **`UserProfile`**: Liên kết 1-1 với `User` và tham chiếu đến `UserRole`. Chứa thông tin bổ sung (họ tên, chức danh, chữ ký, ảnh đại diện) và phân vùng nhà máy (`nha_may`, `is_all_factories`). Đặc biệt chứa hơn 80 trường phân quyền dạng Boolean (`can_...`). Khi profile lưu lại, nó sẽ tự động đồng bộ hóa thông tin họ tên sang model `User` để đảm bảo tính nhất quán.
4. **`UserActivityLog`**: Nhật ký hoạt động, ghi lại các sự kiện `LOGIN`, `LOGOUT`, `LOGIN_FAILED` kèm theo thông tin chi tiết về thời gian, địa chỉ IP (`ip_address`) và trình duyệt/thiết bị (`user_agent`).

### 2.2. Giao diện Quản trị (`admin.py`)
- Định nghĩa **`UserRoleForm`** động để quét toàn bộ các trường `can_` của `UserProfile` và tạo thành các checkbox phân quyền trên trang quản trị Vai trò.
- Đăng ký **`UserRoleAdmin`**: Tổ chức giao diện quản lý vai trò dạng các tab gập mở (collapsible fieldsets) để dễ dàng cấu hình.
- Đăng ký **`UserAdmin`** và **`UserProfileAdmin`**: Hiển thị bảng điều khiển người dùng, nhúng inline `UserProfileInline` giúp xem nhanh và sửa trực tiếp thông tin hồ sơ của người dùng từ trang quản lý tài khoản User.

### 2.3. Logic REST API Views (`auth_views.py`, `profile_views.py`, `upload_views.py`)
- **`auth_views.py`**:
  - `UserRegistrationAPIView`: API đăng ký tài khoản công khai.
  - `UserLoginAPIView`: API đăng nhập hỗ trợ cả Email và Username, tích hợp ghi log và sinh JWT Token.
  - `UserLogoutAPIView`: API đăng xuất, đưa token hiện tại vào Blacklist để vô hiệu hóa hoàn toàn và ghi log logout.
  - `ChangePasswordAPIView`: API thay đổi mật khẩu an toàn.
- **`profile_views.py`**:
  - `UserProfileAPIView`: Xem và cập nhật thông tin hồ sơ cá nhân của tài khoản hiện tại.
  - `UserListAPIView`: Danh sách người dùng dành cho nội bộ hệ thống.
- **`upload_views.py`**:
  - `UploadAvatarAPIView` & `UploadSignatureAPIView`: API upload ảnh đại diện và chữ ký cá nhân, xử lý việc lưu tệp vào thư mục media.

### 2.4. Khai báo Đường dẫn API (`urls.py`)
- Cung cấp toàn bộ các URL routing liên quan đến bảo mật và thông tin cá nhân.
- Hỗ trợ đầy đủ các endpoint tương thích ngược cho ứng dụng **Kho vật tư** cũ (`khovattu/auth/...`) giúp chạy song song nhiều phân hệ phần mềm mà không cần thay đổi client side.

### 2.5. Xử lý Tuần tự hóa (`serializers.py`)
- Chứa các class chuyển đổi dữ liệu qua lại giữa JSON và Object.
- **`UserProfileSerializer`**: Định nghĩa đầy đủ tất cả các trường dữ liệu cá nhân cùng với hàng chục trường quyền `can_...` (bao gồm trường mới thêm `can_receive_alert_notifications`) để phản hồi về Frontend, phục vụ việc ẩn/hiện chức năng trên giao diện UI/UX của Frontend.

### 2.6. Quản lý Lọc dữ liệu & Quyền hạn (`factory_scope.py`)
Đây là công cụ phụ trợ (utility module) phục vụ phân quyền ngang (Data-level/Row-level security):
- **`filter_queryset_by_factory(qs, user, field_name, field_kind)`**: Tự động lọc bất kỳ Django QuerySet nào dựa theo nhà máy được gán của người dùng hiện tại (nếu user không phải superuser và không có quyền truy cập tất cả nhà máy).
- **`FactoryScopedViewSetMixin`**: ViewSet Mixin dùng cho các API, tự động ghi đè `get_queryset` và gán tự động nhà máy khi tạo mới hoặc cập nhật đối tượng dữ liệu.
- **`has_profile_permission(user, permission_field)`**: Kiểm tra xem người dùng hiện tại có sở hữu quyền chức năng cụ thể nào đó hay không (Ví dụ: `can_view_operation_parameters`). Tự động trả về `True` trong môi trường kiểm thử (test) để tối giản việc cài đặt DB test hoặc superuser.

### 2.7. Ghi Log Hoạt động (`signals.py`, `middleware.py`)
- **`signals.py`**: Sử dụng cơ chế Signal của Django để tự động ghi log vào bảng `UserActivityLog` mỗi khi có sự kiện đăng nhập, đăng xuất hoặc đăng nhập thất bại.
- **`middleware.py`**: Do JWT token chỉ được xác thực trong view lớp sau khi middleware mặc định đã chạy xong, `DRFAuthenticationMiddleware` được triển khai để giải mã và gán sớm `request.user` từ JWT token ngay trong chu kỳ request. Điều này giúp `django-auditlog` (Audit Trail) ghi lại chính xác danh tính người thực hiện thao tác dữ liệu thay vì ghi nhận nhầm thành tài khoản từ Session cũ của trình duyệt hoặc `AnonymousUser`.

### 2.8. Tác vụ Định kỳ (`tasks.py`)
- Định nghĩa Celery Task **`clear_old_logs_task`**.
- Tự động dọn dẹp các bản ghi log hoạt động (`UserActivityLog`) và vết thay đổi dữ liệu (`LogEntry` của django-auditlog) cũ hơn số ngày cấu hình (mặc định là 180 ngày) để tối ưu dung lượng cơ sở dữ liệu.

---

## 3. Hướng dẫn Tích hợp & Phát triển Tiếp theo

### 3.1. Quy trình Thêm một Quyền Hạn mới (Permission Field)
Nếu hệ thống có thêm chức năng mới cần bảo mật, ví dụ: quyền quản lý kế hoạch tuần (`can_manage_weekly_plan`), bạn thực hiện theo các bước sau:

1. **Thêm trường vào Model `UserProfile`** (`app/core/models.py`):
   ```python
   can_manage_weekly_plan = models.BooleanField(
       default=False,
       verbose_name="Quản lý kế hoạch tuần",
       help_text="Quyền tạo và chỉnh sửa kế hoạch vận hành tuần."
   )
   ```
2. **Khai báo trong Django Admin** (`app/core/admin.py`):
   Thêm `'can_manage_weekly_plan'` vào danh mục fieldsets tương ứng trong cả `UserProfileInline` và `UserProfileAdmin` để hiển thị trên giao diện admin:
   ```python
   ('Quyền kế hoạch vận hành', {
       'fields': (..., 'can_manage_weekly_plan'),
       'description': '...'
   })
   ```
3. **Khai báo trong Serializer** (`app/core/serializers.py`):
   Thêm `'can_manage_weekly_plan'` vào danh sách `fields` của `UserProfileSerializer` để API trả về đầy đủ thông tin quyền cho Frontend.
4. **Tạo và Chạy Migration**:
   ```bash
   docker compose run --rm app python manage.py makemigrations core
   docker compose run --rm app python manage.py migrate
   ```

*Do cơ chế của `UserRoleForm` đã được viết động, trường mới này sẽ tự động xuất hiện làm checkbox trong giao diện tạo/sửa vai trò (UserRole) mà không cần viết thêm mã nguồn.*

### 3.2. Áp dụng Phân quyền Nhà máy vào View mới
Để giới hạn dữ liệu của một ViewSet chỉ hiển thị các bản ghi thuộc nhà máy của user đang đăng nhập:

```python
from core.factory_scope import FactoryScopedViewSetMixin
from rest_framework import viewsets
from .models import KeHoachVanhHanh
from .serializers import KeHoachSerializer

class KeHoachViewSet(FactoryScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = KeHoachSerializer
    queryset = KeHoachVanhHanh.objects.all()
    
    # Cấu hình trường liên kết nhà máy trong model KeHoachVanhHanh
    factory_field = "nha_may"
    factory_field_kind = "fk"  # Hoặc 'code' / 'string' / 'fk_code' tùy thiết kế DB
```

### 3.3. Kiểm tra Quyền chức năng trong View
Để kiểm tra quyền trước khi xử lý logic nghiệp vụ:

```python
from core.factory_scope import has_profile_permission
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

class DuyetKeHoachView(APIView):
    def post(self, request, *args, **kwargs):
        # Kiểm tra quyền duyệt kế hoạch
        if not has_profile_permission(request.user, "can_manage_weekly_plan"):
            return Response(
                {"detail": "Bạn không có quyền duyệt kế hoạch."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        # Thực hiện logic duyệt kế hoạch...
        return Response({"status": "Thành công"})
```
