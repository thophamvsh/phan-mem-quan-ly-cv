# Đánh giá backend `phan-mem-quan-ly-cv`

## 1) Tổng quan
- **Stack**: Django 3.2 + Django REST Framework + JWT (`simplejwt`), chia theo app: `core`, `khovattu`, `nhatkyvanhanh`, `quanlyvanhanh`.
- **Mục tiêu nghiệp vụ**: quản lý kho vật tư và vận hành (nhật ký vận hành, bàn giao ca, thiết bị, vật tư...).
- **Điểm tích cực**:
  - Cấu trúc app tách theo domain khá rõ.
  - Có custom `User` + `UserProfile` phục vụ phân quyền chi tiết theo nghiệp vụ.
  - Có API health check (`/health/`) và route nhóm theo module.

## 2) Các vấn đề quan trọng (ưu tiên xử lý sớm)

### 2.1. Rủi ro bảo mật cao trong cấu hình
**Phát hiện** (file `app/app/settings.py`):
- `SECRET_KEY` hard-code trực tiếp trong source.
- `DEBUG = True`.
- `ALLOWED_HOSTS` chứa `'*'`.
- `CORS_ALLOW_ALL_ORIGINS = True`.
- Chính sách mật khẩu bị nới quá mức (min length 4).

**Khuyến nghị**:
1. Đưa `SECRET_KEY`, `DEBUG`, DB config, CORS vào biến môi trường.
2. Tách settings theo môi trường (`base.py`, `dev.py`, `prod.py`).
3. Production: `DEBUG=False`, bỏ `'*'`, whitelist domain cụ thể.
4. Khôi phục password validators chuẩn (>=8, common password, numeric...).

### 2.2. Nhiều endpoint để `AllowAny` dù thao tác trên dữ liệu user
**Phát hiện** (file `app/core/views.py`):
- Các API profile / đổi mật khẩu / upload avatar / upload chữ ký / logout có comment “temporarily allow for testing” nhưng vẫn đang dùng `AllowAny`.

**Khuyến nghị**:
- Chuyển các endpoint trên sang `IsAuthenticated`.
- Tách endpoint public/private rõ ràng.
- Bổ sung test cho authz (401/403/200).

### 2.3. Trùng route và nguy cơ khó bảo trì
**Phát hiện** (file `app/core/urls.py`):
- `path('auth/logout/', ...)` xuất hiện 2 lần trỏ tới 2 handler khác nhau.

**Khuyến nghị**:
- Chuẩn hóa 1 endpoint logout duy nhất.
- Xoá endpoint cũ hoặc version hóa API (`/v1/...`).

### 2.4. Bắt lỗi quá rộng (`except:`) nhiều nơi
**Phát hiện**:
- Có nhiều `except:` trần trong codebase.

**Khuyến nghị**:
- Chỉ bắt exception cụ thể (`DoesNotExist`, `ValidationError`, `IntegrityError`, ...).
- Log lỗi có cấu trúc; trả mã lỗi nhất quán.

## 3) Chất lượng kiến trúc & code
### Điểm tốt
- Tách app theo module nghiệp vụ tương đối rõ ràng.
- Có custom model user và profile permissions chi tiết.
- Có migration và command hỗ trợ import/export nghiệp vụ.

### Hạn chế
- `core/views.py` khá dài, chứa nhiều trách nhiệm.
- Có dấu hiệu code trùng giữa class-based và function-based APIs.
- Một số chuỗi tiếng Việt bị lỗi encoding trong response message.

### Khuyến nghị
- Chia nhỏ view theo domain: `auth_views.py`, `profile_views.py`, `upload_views.py`.
- Chuẩn hóa style API response.
- Chuẩn hóa UTF-8 toàn bộ file và pipeline.

## 4) Vận hành & hiệu năng
- Fallback SQLite cho local dev là hợp lý.
- Production nên dùng PostgreSQL + backup policy.
- Nên bổ sung logging tập trung, rate limiting, kiểm soát upload chặt hơn.

## 5) Mức độ sẵn sàng production (đánh giá nhanh)
- Có thể chạy dev tốt, nhưng chưa an toàn để production public nếu giữ nguyên cấu hình/quyền hiện tại.
- Mức độ: Trung bình–Yếu về bảo mật, Trung bình về kiến trúc nghiệp vụ.

## 6) Kế hoạch ưu tiên
1. Khóa bảo mật cấu hình.
2. Đóng endpoint cần auth về `IsAuthenticated`.
3. Gỡ route trùng.
4. Thay `except:` bằng exception cụ thể + logging.
5. Refactor `core/views.py` + bổ sung test.

## 7) Kết luận
Backend có nền tảng nghiệp vụ tốt, nhưng cần xử lý ngay nhóm vấn đề bảo mật/cấu hình và chuẩn hóa endpoint để sẵn sàng production.
