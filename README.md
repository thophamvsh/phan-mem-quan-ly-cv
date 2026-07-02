# VSH Backend System - Phần mềm Quản lý Vận hành & Kho Vật tư

Hệ thống Backend được xây dựng trên nền tảng **Django & Django REST Framework (DRF)** nhằm phục vụ cho phần mềm quản lý kho vật tư và giám sát vận hành các nhà máy thủy điện thuộc VSH (Vĩnh Sơn - Sông Hinh).

---

## 1. Kiến trúc Hệ thống (System Architecture)

Dự án được ảo hóa toàn bộ qua Docker và quản lý bởi **Docker Compose** với các dịch vụ chính:

*   **`redis`** (`redis:7-alpine`): Làm hàng đợi tin nhắn (Message Broker) cho các tác vụ bất đồng bộ của Celery.
*   **`db`** (`pgvector/pgvector:pg13`): Cơ sở dữ liệu PostgreSQL 13 tích hợp sẵn extension `pgvector` phục vụ cho lưu trữ và tìm kiếm vector ngữ nghĩa (semantic search) của Trợ lý AI.
*   **`app`** (Django Web App): Điểm nhận các kết nối API, cung cấp RESTful APIs cho Client, tự động tích hợp công cụ hot-reload khi lập trình.
*   **`worker`** (Celery Worker): Xử lý các tác vụ ngầm chạy chậm như phân tích file tài liệu PDF bằng AI (OpenAI/Anthropic), xuất báo cáo, hay gửi tin nhắn Telegram.
*   **`celery-beat`** (Celery Beat Scheduler): Lên lịch chạy các tác vụ định kỳ, ví dụ tự động dọn dẹp log hệ thống vào lúc 2:00 sáng hàng ngày.

---

## 2. Các Phân hệ Chính (Core Apps)

Dự án được chia nhỏ thành các ứng dụng Django chuyên biệt:

*   **`core`**: Quản lý tài khoản, phân quyền, cấu hình hệ thống, và ghi nhận nhật ký đăng nhập/đăng xuất của người dùng (`UserActivityLog`).
*   **`quanlyvanhanh`**: Quản lý thông tin thiết bị, thông số vận hành hàng ngày của tổ máy/trạm 110kV, và cấu hình ngưỡng cảnh báo thông số. Tích hợp Audit Trail (`django-auditlog`) để theo dõi mọi chỉnh sửa dữ liệu.
*   **`nhatkyvanhanh`**: Quản lý nhật ký ca trực vận hành (Sổ giao nhận ca VH/HC), quản lý sự kiện thiết bị, và tích hợp bộ xử lý tín hiệu (Signals) tự động đẩy thông báo ra nhóm/kênh Telegram.
*   **`thongsothuyvan`**: Quản lý thông số mực nước hồ, lưu lượng về/chạy máy/xả lũ, sản lượng điện kế hoạch và mực nước giới hạn tuần.
*   **`khovattu`**: Quản lý danh mục vật tư, kho bãi, tạo mã QR/Barcode và quản lý phiếu nhập - xuất kho.
*   **`ai_tools` & `documents`**: Tích hợp các thư viện AI (`openai`, `anthropic`, `docling`) để phân tích tài liệu kỹ thuật, chuyển đổi PDF/Image thành văn bản và hỗ trợ chatbot trả lời tự động dựa trên RAG (Retrieval-Augmented Generation).

---

## 3. Hướng dẫn Khởi chạy Dự án (Setup & Installation)

### Bước 1: Chuẩn bị tệp môi trường
Sao chép tệp cấu hình mẫu và điền đầy đủ các thông tin cần thiết (các khóa API AI, thông số DB, cấu hình Telegram):
```bash
cp .env.example .env
```

### Bước 2: Khởi động các container Docker
Chạy lệnh sau để Docker tự động build mã nguồn và khởi chạy toàn bộ hệ thống ở chế độ chạy ngầm (detached mode):
```bash
docker-compose up -d --build
```

### Bước 3: Chạy migrations để khởi tạo database
```bash
docker-compose exec app python manage.py migrate
```

### Bước 4: Tạo tài khoản quản trị (Superuser)
```bash
docker-compose exec app python manage.py createsuperuser
```

Giao diện Django Admin sẽ có tại địa chỉ: `http://localhost:8000/admin/`

---

## 4. API & Tài liệu hóa (API Versioning)

*   **Tài liệu API tự động:** Hệ thống tự động tạo đặc tả OpenAPI thông qua thư viện `drf-spectacular`. Tài liệu Swagger UI có sẵn tại: `http://localhost:8000/api/schema/swagger-ui/`
*   **Phân bản API (Versioning):**
    *   Các route cũ vẫn được giữ nguyên tại đầu mục `/api/...` nhằm tương thích ngược với các client phiên bản cũ.
    *   Các route mới khuyên dùng nên được gọi qua prefix `/api/v1/...` (ví dụ: `/api/v1/auth/login/`).

---

## 5. Tài liệu hướng dẫn chuyên sâu

Để xem chi tiết cấu hình và vận hành các phân hệ cụ thể, vui lòng tham khảo:

1.  **Cấu trúc thư mục:** [docs/REPO_STRUCTURE.md](docs/REPO_STRUCTURE.md)
2.  **Thông báo Telegram:** [huongdan.md](huongdan.md) - Hướng dẫn cấu hình Bot Telegram để tự động gửi thông báo vận hành.
3.  **Hệ thống Log:** [huongdan_log.md](huongdan_log.md) - Hướng dẫn quản trị hệ thống log hoạt động và lịch sử thay đổi dữ liệu (Audit Trail).
4.  **Phần mềm quản lý vận hành:** [app/quanlyvanhanh/README.md](app/quanlyvanhanh/README.md) và [API_DOCUMENTATION.md](app/quanlyvanhanh/API_DOCUMENTATION.md).
