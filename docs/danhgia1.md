# Đánh giá Backend phan-mem-quan-ly-cv

## 1. Tổng quan kiến trúc

Hệ thống backend `phan-mem-quan-ly-cv` được xây dựng bằng **Django** + **Django REST Framework**, với cấu trúc module tách biệt rõ ràng theo nghiệp vụ:

- `core`: quản lý người dùng, custom User model, UserProfile, JWT auth và quyền truy cập.
- `khovattu`: quản lý vật tư, vị trí kho, đề nghị nhập/xuất, kiểm kê, import/export Excel và QR code.
- `nhatkyvanhanh`: quản lý nhật ký sự kiện vận hành nhà máy.
- `quanlyvanhanh`: quản lý thiết bị, bảng thiết bị và thông số vận hành.
- `thongsothuyvan`: dữ liệu thủy văn, mực nước và sản xuất.

Cấu hình môi trường được chia thành `settings_base.py`, `settings_dev.py` và `settings_prod.py`; Docker Compose dùng PostgreSQL cho dev và chạy backend với `runserver` trong container.

## 2. Điểm mạnh

### 2.1. Kiến trúc phân quyền chi tiết

- Hệ thống dùng custom User model với `AUTH_USER_MODEL = 'core.User'`.
- `UserProfile` lưu thông tin bổ sung và hàng loạt quyền boolean theo module (xem, tạo, sửa, xóa, import/export, duyệt đề nghị, xem báo cáo, v.v.).
- Có cơ chế phân quyền theo nhà máy: `nha_may` và `is_all_factories` giúp giới hạn truy cập dữ liệu theo phạm vi.

### 2.2. Thiết kế dữ liệu và ràng buộc tốt

- Các model vật tư như `Bang_vat_tu`, `Bang_vi_tri`, `Bang_nha_may` đều có các `Index`, `UniqueConstraint`, `CheckConstraint` phù hợp.
- Trường số lượng và tồn kho được bảo vệ không âm nhờ `CheckConstraint`.
- Mã QR được auto-generare trong model `Bang_vat_tu.ensure_qr_image()` với lưu file `ImageField`.

### 2.3. Công nghệ và tính năng hỗ trợ nghiệp vụ

- Hỗ trợ API Swagger/OpenAPI (`drf_spectacular`) và versioning route (`api/` + `api/v1/`).
- Sử dụng `django-import-export`, `pandas`, `openpyxl` để xử lý import/export Excel phức tạp.
- Có view xử lý upload/download file, import Excel và chuyển đổi dữ liệu Bravo.
- Docker Compose được cấu hình rõ, gồm service `db` và `app`, volumes media/static/logs, healthcheck `health/`.

### 2.4. Quản lý môi trường tốt

- `settings_base.py` hỗ trợ `env_bool()` và cấu hình mặc định an toàn cho CORS, JWT, database.
- Nếu không có `DB_HOST` thì fallback sang SQLite, thuận tiện cho môi trường dev nhanh.

## 3. Các điểm cần cải thiện

### 3.1. Tách logic nghiệp vụ khỏi views

- Một số file views trong `khovattu` có khối lượng logic lớn (như import Excel, phân tích `ma_bravo`, filter query phức tạp).
- **Recommendation**: tách nghiệp vụ ra `services.py`, `managers.py` hoặc `use_cases.py`, để `views` chỉ còn nhiệm vụ orchestrate request/response.

### 3.2. Kiểm thử chưa rõ ràng

- Repository có thư mục `tests/` nhưng chưa kiểm tra chi tiết nội dung. Cần bổ sung test coverage cho:
  - truy vấn phân quyền nhà máy,
  - import/export Excel,
  - tính toán mực nước/nhật ký vận hành,
  - generation QR và API auth.

### 3.3. Bảo mật và permission object-level

- Cấu hình `DEFAULT_PERMISSION_CLASSES` mặc định là `IsAuthenticated`, nhưng các API tùy theo hành động cần permission riêng.
- Nên kiểm tra thêm object-level permission trong các endpoint chỉnh sửa/xóa để đảm bảo chỉ user phù hợp có quyền thao tác.

### 3.4. Potential performance issues

- Các serializer lớn với nhiều `SerializerMethodField` có thể gây ra N+1 nếu không dùng `select_related`/`prefetch_related` đủ.
- Dữ liệu thủy văn và nhật ký vận hành nếu lưu trữ dài hạn cần chính sách archive/cleanup để tránh table quá lớn.

## 4. Kết luận

Backend `phan-mem-quan-ly-cv` có cấu trúc rõ ràng, phù hợp cho hệ thống quản lý kho và vận hành nhà máy. Thiết kế module gọn, support JWT, Docker và các tính năng nghiệp vụ thực tế.

Tuy nhiên, nên cải thiện cách tách logic nghiệp vụ khỏi views và bổ sung test, đồng thời kiểm tra kỹ các permission object-level để giảm rủi ro bảo mật.

---

_File đánh giá tạo ngày 13/05/2026_
