# Kế hoạch Triển khai Backend Core - Dự án Quản lý Vận hành & Kho Vật tư

Tài liệu này phác thảo kế hoạch xây dựng phần cốt lõi (Foundational Backend Core) cho dự án. Mục tiêu là thiết lập một khung backend tối giản, chỉ bao gồm ứng dụng `core` (Xác thực, Phân quyền, Nhật ký hoạt động, Docker, và cấu hình chạy ngầm Celery). Các ứng dụng nghiệp vụ khác (như Quản lý vận hành, Kho vật tư) sẽ được thiết kế độc lập và có thể phát triển riêng biệt sau này.

---

## 1. Công nghệ Sử dụng (Tech Stack)

*   **Framework chính:** Django 3.2.x & Django REST Framework (DRF) 3.12.x.
*   **Xác thực:** JWT (JSON Web Token) qua thư viện `djangorestframework-simplejwt`.
*   **Cơ sở dữ liệu:** PostgreSQL 13 (đã cấu hình sẵn UTF-8).
*   **Hàng đợi & Tác vụ ngầm:** Redis + Celery + Celery Beat.
*   **Ảo hóa:** Docker & Docker Compose.

---

## 2. Chi tiết Thiết kế Ứng dụng `core` (Core App Specs)

Ứng dụng `core` đóng vai trò là nền tảng quản trị hệ thống, bao gồm các chức năng:

### A. Quản lý Người dùng & Phân quyền (User & Auth)
*   **Custom User Model:** Kế thừa từ `AbstractUser` để quản lý người dùng với các trường bổ sung:
    *   Quyền truy cập nhà máy (nhà máy cụ thể hoặc tất cả nhà máy).
    *   Quyền vận hành riêng biệt (xem/sửa nhật ký ca trực, xem/sửa ngưỡng thông số,...).
*   **API Xác thực (JWT Auth):**
    *   `POST /api/v1/auth/login/`: Nhận username/password, trả về Access Token (thời hạn ngắn) và Refresh Token (thời hạn dài).
    *   `POST /api/v1/auth/refresh/`: Nhận Refresh Token để cấp mới Access Token.
    *   `POST /api/v1/auth/logout/`: Vô hiệu hóa Refresh Token (cho vào blacklist).

### B. Nhật ký Hoạt động Người dùng (User Activity Log)
*   **Database Schema (`UserActivityLog`):**
    *   `user`: Liên kết với User Model (null nếu đăng nhập lỗi).
    *   `action_type`: Thể loại hành động (`LOGIN`, `LOGOUT`, `LOGIN_FAILED`).
    *   `description`: Mô tả chi tiết (ví dụ: "Đăng nhập lỗi do sai mật khẩu").
    *   `ip_address`: Địa chỉ IP của thiết bị gửi request.
    *   `user_agent`: Trình duyệt, thiết bị của người dùng.
    *   `timestamp`: Thời điểm ghi nhận.
*   **Cơ chế hoạt động:** Sử dụng **Django Authentication Signals** (`user_logged_in`, `user_logged_out`, `user_login_failed`) để tự động ghi log khi có sự kiện xác thực mà không làm ảnh hưởng đến luồng code xử lý API.

### C. Tác vụ ngầm Tự động Dọn dẹp Log (Celery Beat Task)
*   **Cấu hình:** Đọc số ngày lưu giữ log từ biến môi trường `LOG_RETENTION_DAYS` (mặc định là 180 ngày).
*   **Hoạt động:** Định nghĩa task `clear_old_logs_task` trong `core/tasks.py`. Cấu hình Celery Beat chạy task này vào lúc 2:00 sáng hàng ngày để xóa sạch các bản ghi log cũ hơn hạn định nhằm giải phóng dung lượng DB.

### D. Trang quản trị Django Admin
*   Đăng ký quản lý User và hiển thị trực quan bảng nhật ký hoạt động.
*   Thiết lập bảng Nhật ký hoạt động ở chế độ **Chỉ đọc (Read-only)** để đảm bảo tính toàn vẹn của dữ liệu giám sát (không ai có quyền thêm, sửa, xóa log này trên giao diện Admin).

---

## 3. Cấu trúc Thư mục bootstrap tối giản

```text
phan-mem-quan-ly-cv/
├── .env.example            # Tệp biến môi trường mẫu
├── .gitignore              # Cấu hình bỏ qua tệp của Git
├── Dockerfile              # Dockerfile build Django app
├── docker-compose.yml      # Cấu hình các dịch vụ container (db, redis, app, worker, beat)
├── requirements.txt        # Danh sách các thư viện Python tối giản cần dùng
└── app/
    ├── manage.py           # Tệp điều khiển chính của Django
    ├── app/
    │   ├── __init__.py
    │   ├── celery.py       # Cấu hình Celery instance
    │   ├── settings.py     # Cấu hình Django settings chính
    │   └── urls.py         # Định tuyến URL chính
    └── core/
        ├── __init__.py
        ├── admin.py        # Giao diện Django Admin chỉ đọc cho logs
        ├── apps.py         # Nơi đăng ký Signals khi app khởi động
        ├── models.py       # Khai báo Custom User & UserActivityLog
        ├── signals.py      # Lắng nghe Login/Logout/Login Failed
        ├── tasks.py        # Tác vụ dọn dẹp log định kỳ (Celery)
        └── views.py        # API Login/Logout/Refresh
```

---

## 4. Các Bước Triển khai (Step-by-Step Implementation)

### Bước 1: Thiết lập Môi trường & Thư viện
1.  Tạo tệp `requirements.txt` tối giản chứa:
    ```text
    Django>=3.2.4,<3.3
    djangorestframework>=3.12.4,<3.13
    djangorestframework-simplejwt>=5.0.0
    django-cors-headers>=4.0.0
    psycopg2-binary==2.9.9
    celery>=5.3.0,<6.0
    redis>=5.0.0,<6.0
    ```
2.  Tạo cấu hình `Dockerfile` đa giai đoạn (multi-stage) để tối ưu dung lượng ảnh build.
3.  Tạo tệp `docker-compose.yml` định nghĩa các service: `db` (Postgres), `redis`, `app` (Django), `worker` (Celery), và `celery-beat` (Scheduler).

### Bước 2: Cấu hình Dự án Django
1.  Khởi tạo dự án Django bằng lệnh `django-admin startproject app .`
2.  Tạo app core bằng lệnh `python manage.py startapp core`.
3.  Cấu hình `settings.py`:
    *   Đăng ký `rest_framework`, `corsheaders`, và `core`.
    *   Chỉ định sử dụng Custom User model: `AUTH_USER_MODEL = 'core.CustomUser'`.
    *   Cấu hình kết nối DB PostgreSQL thông qua biến môi trường.
    *   Thiết lập CORS allowed origins cho phép frontend kết nối.
    *   Cấu hình REST Framework sử dụng xác thực JWT (`JWTAuthentication`).
4.  Cấu hình `app/celery.py` để tích hợp Celery và nạp lịch trình dọn dẹp log hàng ngày.

### Bước 3: Thiết lập Mô hình dữ liệu & Migrations
1.  Trong `core/models.py`, định nghĩa `CustomUser` kế thừa `AbstractUser`.
2.  Định nghĩa `UserActivityLog` để lưu vết đăng nhập.
3.  Chạy lệnh tạo và áp dụng migration để cấu hình DB ban đầu:
    ```bash
    python manage.py makemigrations core
    python manage.py migrate
    ```

### Bước 4: Viết bộ lắng nghe Sự kiện Đăng nhập (Signals)
1.  Trong `core/signals.py`, sử dụng `@receiver` lắng nghe 3 tín hiệu:
    *   `django.contrib.auth.signals.user_logged_in`
    *   `django.contrib.auth.signals.user_logged_out`
    *   `django.contrib.auth.signals.user_login_failed`
2.  Viết hàm helper lấy IP của Client từ `request.META` (xử lý cả trường hợp proxy qua HTTP_X_FORWARDED_FOR).
3.  Khi có tín hiệu, thực hiện tạo bản ghi vào bảng `UserActivityLog`.
4.  Đăng ký import `signals` trong phương thức `ready()` của `core/apps.py`.

### Bước 5: Thiết lập APIs Xác thực (Auth APIs)
1.  Cấu hình URLs định tuyến các endpoint JWT của `djangorestframework-simplejwt` trong `core/urls.py` và include vào `app/urls.py`.
2.  Viết thêm logic ghi nhận log `LOGOUT` thủ công nếu cần thiết hoặc dựa trên tín hiệu logout mặc định của Django khi token bị đưa vào danh sách đen (blacklist).

### Bước 6: Viết Task Dọn dẹp Log & Cấu hình Beat
1.  Trong `core/tasks.py`, viết task Celery:
    ```python
    @shared_task
    def clear_old_logs_task():
        # Xóa các bản ghi UserActivityLog có timestamp nhỏ hơn hạn định
    ```
2.  Cấu hình Scheduler trong `settings.py` để lập lịch chạy tác vụ này hàng ngày.

### Bước 7: Đăng ký Trang quản trị Django Admin
1.  Trong `core/admin.py`, đăng ký hiển thị `UserActivityLog`.
2.  Gán phương thức `has_add_permission`, `has_change_permission`, `has_delete_permission` trả về `False` để khóa khả năng sửa đổi log trên giao diện Admin.

---

## 5. Kế hoạch Kiểm thử & Bàn giao (Verification)

*   **Khởi chạy hệ thống:** Thực hiện lệnh `docker-compose up -d --build` và kiểm tra tất cả các container đều ở trạng thái `running` (hoạt động).
*   **Test Đăng nhập thành công/Thất bại:** Sử dụng Postman gửi request đăng nhập vào `/api/v1/auth/login/` với thông tin đúng/sai. Kiểm tra xem DB có tự động tạo ra bản ghi `UserActivityLog` tương ứng hay không.
*   **Test Celery Beat:** Chạy thử task `clear_old_logs_task` thủ công trong Django shell để kiểm tra logic lọc xóa dữ liệu log cũ hoạt động chính xác.
*   **Kiểm tra Django Admin:** Đăng nhập vào trang quản trị `/admin/`, đảm bảo bảng Nhật ký hoạt động chỉ hiển thị dạng xem (Read-only) và không thể chỉnh sửa.
