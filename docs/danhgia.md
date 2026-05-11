# Đánh Giá Backend — `phan-mem-quan-ly-cv`

> **Ngày đánh giá:** 10/05/2026  
> **Phiên bản Django:** 3.2.x  
> **Người đánh giá:** Antigravity AI Code Review

---

## 1. Tổng Quan Dự Án

Backend được xây dựng bằng **Django REST Framework (DRF)**, phục vụ hệ thống quản lý vận hành nhà máy thuỷ điện (Sông Hinh, Vĩnh Sơn). Hệ thống bao gồm 5 ứng dụng con:

| App | Chức năng |
|---|---|
| `core` | Xác thực, phân quyền, quản lý người dùng |
| `khovattu` | Quản lý kho vật tư, nhập/xuất, kiểm kê |
| `nhatkyvanhanh` | Nhật ký vận hành, sự kiện, sổ giao nhận ca |
| `quanlyvanhanh` | Thông số vận hành, giờ máy H1/H2, báo cáo |
| `thongsothuyvan` | Dữ liệu thuỷ văn và sản xuất realtime |

**Stack công nghệ:** Python 3.12, Django 3.2, DRF, PostgreSQL, JWT, Docker, drf-spectacular (Swagger), pandas, openpyxl.

---

## 2. Kiến Trúc Hệ Thống

### 2.1 Điểm Mạnh

#### ✅ Phân tầng rõ ràng
Dự án tổ chức theo mô hình Django apps chuẩn — mỗi domain nghiệp vụ là một app riêng biệt với `models`, `serializers`, `views`, `urls` và `admin` độc lập. Điều này giúp code dễ bảo trì và mở rộng.

#### ✅ Settings được tách theo môi trường
```
settings_base.py   ← cấu hình chung
settings_dev.py    ← ghi đè cho development
settings_prod.py   ← ghi đè cho production
settings.py        ← điểm vào chính (load theo ENV)
```
Sử dụng biến môi trường (`os.environ.get`) cho hầu hết cấu hình nhạy cảm.

#### ✅ Hỗ trợ versioning API
URL patterns có cả route legacy (`/api/`) lẫn versioned (`/api/v1/`) — đảm bảo backward compatibility khi nâng cấp.

#### ✅ Multi-stage Dockerfile tốt
Dockerfile dùng **3 stage** (`builder → production → development`), image production không chứa build tools, chạy với user không phải root (`django:django`), có **HEALTHCHECK** tích hợp.

#### ✅ Factory Scope Pattern được thiết kế tốt
`core/factory_scope.py` triển khai mixin `FactoryScopedViewSetMixin` tái sử dụng được — tự động filter queryset và inject factory khi create/update theo quyền của user. Đây là pattern chắc chắn và dễ test.

#### ✅ Swagger / OpenAPI tích hợp sẵn
`drf-spectacular` được cài đặt và cấu hình với 3 endpoint: `/api/schema/`, `/api/docs/`, `/api/redoc/` — giúp frontend dev không cần đọc code.

### 2.2 Điểm Yếu Về Kiến Trúc

#### ⚠️ URL trùng lặp không cần thiết
Trong `core/urls.py`, nhiều endpoint được mount hai lần:
```python
path('profile/', ...)          # /api/profile/
path('auth/profile/', ...)     # /api/auth/profile/
```
Và tất cả lại được mount thêm với prefix `khovattu/auth/`. Cần chuẩn hoá và loại bỏ các alias không cần thiết.

#### ⚠️ `views.py` quá lớn trong khovattu
File `khovattu/views.py` có **89.053 bytes (~2700+ dòng)**. Đây là dấu hiệu của "God View" — vi phạm Single Responsibility Principle. Cần chia nhỏ theo chức năng tương tự cách `quanlyvanhanh` đã làm (`views_h1.py`, `views_h2.py`, `views_excel.py`).

---

## 3. Mô Hình Dữ Liệu (Models)

### 3.1 Điểm Mạnh

#### ✅ Custom User Model đúng chuẩn
`User` kế thừa `AbstractBaseUser + PermissionsMixin`, đặt `USERNAME_FIELD = 'email'` — đây là cách làm chuẩn cho Django custom auth.

#### ✅ UserProfile được thiết kế chi tiết
`UserProfile` chứa **40+ trường boolean phân quyền chi tiết** theo từng chức năng cụ thể (xem/thêm/sửa/xóa/phê duyệt từng loại nghiệp vụ). Hệ thống phân quyền hạt nhân (fine-grained) này rất phù hợp với nghiệp vụ vận hành nhà máy.

#### ✅ Sử dụng UUID làm PK cho bảng nghiệp vụ quan trọng
`nhatkyvanhanh` sử dụng `UUID` làm primary key — giúp tránh xung đột ID khi merge data từ nhiều nhà máy.

#### ✅ DB Constraints tại tầng database
```python
CheckConstraint(check=Q(ton_kho__gte=0), name="chk_vattu_ton_kho_gte_0")
UniqueConstraint(fields=["bang_nha_may", "ma_bravo"], name="uniq_vattu_nhamay_mabravo")
```
Bảo vệ tính toàn vẹn dữ liệu ở cả tầng Django lẫn database.

#### ✅ Tự động đồng bộ chữ ký (signature sync)
Logic trong `nhatkyvanhanh/models.py` tự động copy chữ ký từ `UserProfile` vào các bản ghi khi user ký — giảm thiểu thao tác thủ công.

### 3.2 Điểm Yếu Về Models

#### ⚠️ Bidirectional sync có nguy cơ vòng lặp
`User.save()` gọi `UserProfile.save()` và ngược lại, được kiểm soát bằng flag `sync_from_profile` / `sync_from_user`. Cơ chế này dễ bị lỗi nếu không cẩn thận. Nên xem xét dùng Django `signals` (post_save) để tách biệt rõ ràng hơn.

#### ⚠️ `Bang_kiem_ke` thiếu trường nhà máy FK
```python
class Bang_kiem_ke(models.Model):
    ma_nha_may = models.CharField(max_length=20, default="")  # CharField, không phải FK!
```
Trong khi các bảng khác dùng `ForeignKey` đến `Bang_nha_may`, bảng này dùng plain `CharField` — mất tính toàn vẹn quan hệ.

#### ⚠️ `Bang_kiem_ke` thiếu audit fields
Bảng này không có `created_at`, `updated_at`, không có `nguoi_tao` — khó truy vết lịch sử.

#### ⚠️ Naming convention không nhất quán
- Một số model dùng tiếng Việt không dấu: `Bang_nha_may`, `Bang_vat_tu`
- Một số dùng CamelCase: `SuKien`, `TimestampedUUIDModel`, `SogiaonhancaVH`
- Cần thống nhất một convention (khuyến nghị: CamelCase PEP 8).

---

## 4. Bảo Mật

### 4.1 Điểm Mạnh

#### ✅ JWT với thời gian hết hạn hợp lý
```python
ACCESS_TOKEN_LIFETIME  = timedelta(days=7)
REFRESH_TOKEN_LIFETIME = timedelta(days=30)
ROTATE_REFRESH_TOKENS  = True
BLACKLIST_AFTER_ROTATION = True
```
Refresh token rotation + blacklist giúp giảm rủi ro token bị đánh cắp.

#### ✅ Password validation đầy đủ
Sử dụng đủ 4 Django built-in validators (UserAttributeSimilarity, MinimumLength 8, CommonPassword, Numeric) và kiểm tra mật khẩu tại cả model layer lẫn serializer layer.

#### ✅ Phân quyền theo nhà máy
`HasFactoryAccess`, `HasFactoryAccessStrict`, `CanViewMaterials`... — các permission class tách biệt, dễ test, dễ kết hợp.

#### ✅ Xác thực hỗ trợ cả email lẫn username
`UserLoginSerializer` tự động detect email format để chọn authentication method phù hợp.

### 4.2 Vấn Đề Bảo Mật Cần Xử Lý

#### 🔴 CRITICAL: Secret key có giá trị mặc định không an toàn
```python
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")
```
Nếu biến môi trường không được set, key không an toàn này sẽ được dùng ngay cả trong production. Cần **bắt buộc** key phải được set:
```python
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]  # Raise KeyError nếu thiếu
```

#### 🔴 CRITICAL: File credential GCP được commit vào repo
```
ai-project-484022-8239457b26bb.json   ← trong thư mục gốc
vinhson-account-key.json              ← trong app/
```
**Đây là rủi ro bảo mật nghiêm trọng.** Các file này phải được xoá khỏi git history, thu hồi credential cũ và thêm vào `.gitignore` ngay lập tức.

#### 🔴 Token JWT: thời gian tồn tại Access Token quá dài
`ACCESS_TOKEN_LIFETIME = timedelta(days=7)` là **quá dài** cho access token. Nếu token bị lộ, attacker có 7 ngày để khai thác. Khuyến nghị: 15 phút – 1 giờ.

#### 🟡 MEDIUM: Bare `except` trong serializers
```python
def get_full_name(self, obj):
    try:
        ...
    except:        # ← bắt hết Exception, che giấu lỗi thật
        return f"{obj.first_name} {obj.last_name}".strip()
```
Nên bắt exception cụ thể (`except UserProfile.DoesNotExist`) để không vô tình ẩn các lỗi nghiêm trọng.

#### 🟡 MEDIUM: Upload file không kiểm tra magic bytes
`upload_views.py` chỉ kiểm tra `content_type` do client gửi lên — dễ bị bypass. Cần kiểm tra nội dung file thực tế bằng thư viện như `python-magic`.

#### 🟡 MEDIUM: Thiếu rate limiting
Không có rate limiting cho các endpoint đăng nhập (`/api/auth/login/`) — dễ bị brute force. Cần thêm `django-ratelimit` hoặc cấu hình tại tầng reverse proxy (Nginx).

---

## 5. Chất Lượng Code

### 5.1 Điểm Mạnh

#### ✅ Tests cho core module
`core/tests/` có 4 file test:
- `test_models.py`: 11 test cases cho User/UserProfile
- `test_api.py`: test API endpoints
- `test_factory_scope.py`: test factory scoping logic
- `test_commands.py`: test management commands

Đây là nền tảng tốt.

#### ✅ `factory_scope.py` được viết rõ ràng, có thể test độc lập
Các helper function thuần tuý (`has_all_factory_access`, `get_user_factory_code`) không phụ thuộc vào request — dễ unit test.

#### ✅ Docstrings đầy đủ cho models và views quan trọng
Hầu hết các method quan trọng đều có docstring ngắn bằng tiếng Việt — phù hợp với đội ngũ phát triển Việt Nam.

### 5.2 Điểm Yếu Về Code Quality

#### ⚠️ `UserSerializer` bị định nghĩa hai lần trong cùng một file
```python
# serializers.py - dòng 92
class UserSerializer(serializers.ModelSerializer):
    """Serializer cho thông tin user với thông tin từ profile"""
    ...

# serializers.py - dòng 316
class UserSerializer(serializers.ModelSerializer):
    """Serializer cho thông tin user cơ bản"""
    ...
```
Class thứ hai ghi đè class thứ nhất — **đây là bug tiềm ẩn**. Class đầu tiên (có nhiều trường hơn) sẽ không bao giờ được sử dụng.

#### ⚠️ Thiếu tests cho các module chính
`khovattu/tests.py` chỉ có 1 dòng comment, `nhatkyvanhanh` không có thư mục tests. Đây là phần có logic nghiệp vụ phức tạp nhất nhưng lại ít được test nhất.

#### ⚠️ Thiếu type hints
Không có type annotations trong toàn bộ codebase. Với Python 3.12, nên áp dụng type hints cho function signatures.

#### ⚠️ Import trong method body
```python
def avatar_url(self):
    if self.avatar:
        from django.conf import settings  # ← import trong property
        return f"{getattr(settings, 'BASE_URL', ...)}{self.avatar.url}"
```
Import nên được đặt ở đầu file.

---

## 6. Hiệu Năng

### 6.1 Điểm Mạnh

#### ✅ Pagination được cấu hình mặc định
```python
'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
'PAGE_SIZE': 10,
```
Tất cả list endpoint đều được phân trang theo mặc định.

#### ✅ DB Indexes cho các trường hay query
```python
indexes = [
    Index(fields=["ten_vat_tu"]),
    Index(fields=["ma_bravo"]),
    Index(fields=["vat_tu", "thu_tu"]),
]
```

#### ✅ `select_related` / `prefetch_related` xuất hiện ở một số views
Module `quanlyvanhanh` có các views optimized (`views_optimized.py`) — cho thấy team đã nhận thức về vấn đề N+1 queries.

### 6.2 Điểm Yếu Về Hiệu Năng

#### ⚠️ N+1 queries trong UserSerializer
`UserSerializer` có **8 `SerializerMethodField`**, mỗi field thực hiện một truy cập `obj.profile` riêng biệt — dù có thể cùng query cơ sở dữ liệu. Cần dùng `select_related('profile')` ở queryset.

#### ⚠️ Không có caching layer
Không thấy Redis hoặc Django cache framework được cấu hình. Các dữ liệu ít thay đổi (danh sách nhà máy, danh mục vật tư) nên được cache.

#### ⚠️ QR code được tạo đồng bộ khi import
Hàm `ensure_qr_image()` trong `Bang_vat_tu` tạo QR code trong quá trình import — có thể làm chậm batch import lớn. Nên xử lý bằng Celery task bất đồng bộ.

---

## 7. DevOps & Deployment

### 7.1 Điểm Mạnh

#### ✅ Docker Compose đầy đủ và rõ ràng
- Database PostgreSQL với healthcheck
- Named volumes cho data persistence
- Hot-reload volume mount cho development
- Network isolation (`vsh-net`)

#### ✅ Wait-for-DB trước khi migrate
```yaml
command: sh -c "python manage.py wait_for_db && python manage.py migrate && ..."
```
Tránh race condition khi container app start trước database.

#### ✅ `.env.example` có sẵn
Giúp developer mới onboard dễ dàng cấu hình môi trường.

### 7.2 Điểm Yếu Về Deployment

#### 🔴 File `.env` chứa thông tin thật bị commit vào repo
File `.env` (1965 bytes) xuất hiện trong working directory — **không** nên có trong version control. Cần thêm `.env` vào `.gitignore`.

#### ⚠️ `docker-compose.yml` dùng `version: "3.9"` đã deprecated
Docker Compose v2 không còn dùng `version` key. Nên xoá dòng này.

#### ⚠️ Thiếu Nginx / Reverse Proxy trong docker-compose
Production không nên để Django nhận request trực tiếp. Cần thêm Nginx để serve static/media files và làm reverse proxy cho Gunicorn.

#### ⚠️ Thiếu CI/CD pipeline
Thư mục `.github/` có nhưng không rõ có workflow file nào không. Cần thêm GitHub Actions chạy tests và linting khi push.

---

## 8. API Documentation

### ✅ Swagger UI tự động
drf-spectacular tạo schema tự động và expose tại `/api/docs/`. Đây là điểm cộng lớn cho team frontend.

### ⚠️ Thiếu `@extend_schema` decorator
Các views không có `@extend_schema` annotation — Swagger schema sẽ thiếu description, ví dụ về request/response body.

### ⚠️ Health check endpoint quá đơn giản
```python
def health_check(request):
    return JsonResponse({"status": "ok"})
```
Nên bổ sung kiểm tra kết nối database, cache để Kubernetes/load balancer phát hiện app unhealthy:
```python
def health_check(request):
    from django.db import connection
    connection.ensure_connection()
    return JsonResponse({"status": "ok", "db": "ok"})
```

---

## 9. Bảng Điểm Tổng Hợp

| Hạng mục | Điểm | Nhận xét |
|---|:---:|---|
| **Kiến trúc tổng thể** | 8/10 | Cấu trúc rõ ràng, settings tách biệt tốt |
| **Mô hình dữ liệu** | 7/10 | Design tốt nhưng còn inconsistencies |
| **Bảo mật** | 5/10 | Credential bị leak là vấn đề nghiêm trọng |
| **Chất lượng code** | 6/10 | UserSerializer trùng lặp, thiếu type hints |
| **Hiệu năng** | 6/10 | Có index nhưng thiếu caching, N+1 queries |
| **Testing** | 5/10 | Chỉ core có test, thiếu test cho nghiệp vụ |
| **DevOps** | 7/10 | Docker tốt nhưng thiếu Nginx, CI/CD |
| **Documentation** | 7/10 | Swagger sẵn có, nhưng thiếu annotations |
| **🎯 Tổng thể** | **6.4/10** | |

---

## 10. Các Ưu Tiên Cần Xử Lý

### 🔴 Ưu tiên cao (Cần xử lý ngay)

1. **Thu hồi và xoá các file credential GCP** (`ai-project-484022-8239457b26bb.json`, `vinhson-account-key.json`) khỏi git history.
2. **Thêm `.env` vào `.gitignore`** và không commit file `.env` thật vào repo.
3. **Bắt buộc `DJANGO_SECRET_KEY` phải được set** — raise exception nếu thiếu.
4. **Giảm `ACCESS_TOKEN_LIFETIME`** xuống 15 phút hoặc tối đa 1 giờ.
5. **Sửa bug `UserSerializer` bị định nghĩa hai lần** trong `core/serializers.py`.

### 🟡 Ưu tiên trung bình

6. Thêm rate limiting cho login endpoint.
7. Validate magic bytes khi upload file.
8. Thêm `select_related('profile__nha_may')` vào UserSerializer queryset.
9. Tách `khovattu/views.py` thành các file nhỏ hơn theo chức năng.
10. Thêm Nginx vào docker-compose cho production.

### 🟢 Cải tiến dài hạn

11. Viết tests cho `khovattu` và `nhatkyvanhanh`.
12. Thêm `@extend_schema` annotations cho tất cả views.
13. Áp dụng type hints trên toàn bộ codebase.
14. Cân nhắc nâng Django lên 4.2 LTS hoặc 5.0.
15. Thêm Redis caching cho dữ liệu danh mục.
16. Chuyển tạo QR code sang Celery task bất đồng bộ.

---

## 11. Kết Luận

Backend `phan-mem-quan-ly-cv` được xây dựng trên nền tảng kiến trúc tốt với Django REST Framework. Hệ thống phân quyền chi tiết và `FactoryScopedViewSetMixin` là những điểm sáng về thiết kế. Tuy nhiên, **vấn đề bảo mật về credential bị lộ và token lifetime quá dài cần được xử lý ngay lập tức** trước khi deploy ra production.

Code chất lượng nhìn chung ổn nhưng cần refactor một số điểm quan trọng (UserSerializer trùng, God View) và tăng test coverage đáng kể — đặc biệt là các module có logic nghiệp vụ phức tạp.

> **Điểm tổng thể: 6.4/10** — Tiềm năng tốt, cần ưu tiên xử lý bảo mật trước khi production-ready.
