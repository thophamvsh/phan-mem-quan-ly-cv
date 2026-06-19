# Hướng dẫn Hệ thống Ghi Log Hoạt động và Lịch sử Thay đổi Dữ liệu

Tài liệu này hướng dẫn cách thức hoạt động, cấu hình, quản trị và phát triển mở rộng hệ thống ghi log trong ứng dụng. Hệ thống ghi log được thiết kế chia làm 2 phần chính:
1. **Nhật ký Hoạt động Người dùng (User Activity Log):** Ghi lại các sự kiện như Đăng nhập, Đăng xuất, Đăng nhập lỗi.
2. **Lịch sử Thay đổi Dữ liệu (Audit Trail):** Tự động theo dõi các hành động Thêm, Sửa, Xóa trên các bảng cơ sở dữ liệu quan trọng.

---

## 1. Nhật ký Hoạt động Người dùng (User Activity Log)

Hệ thống tự động ghi nhận các sự kiện xác thực của người dùng thông qua cơ chế **Django Authentication Signals** tại backend.

### Các hành động được ghi lại (`action_type`):
*   `LOGIN`: Đăng nhập thành công.
*   `LOGOUT`: Đăng xuất khỏi hệ thống.
*   `LOGIN_FAILED`: Thử đăng nhập nhưng không thành công (sai mật khẩu, tài khoản không tồn tại).

### Cấu trúc cơ sở dữ liệu (`UserActivityLog` model):
Nằm trong ứng dụng `core` (`core/models.py`), chứa các trường:
*   `user`: Người dùng thực hiện hành động (null nếu đăng nhập lỗi).
*   `action_type`: Loại hành động (`LOGIN`, `LOGOUT`, `LOGIN_FAILED`).
*   `description`: Mô tả chi tiết (ví dụ: *"Người dùng đăng nhập thành công"*, *"Đăng nhập thất bại cho tài khoản: abc"*).
*   `ip_address`: Địa chỉ IP của client thực hiện request.
*   `user_agent`: Thông tin trình duyệt và thiết bị của người dùng.
*   `timestamp`: Thời điểm ghi nhận hệ thống.

### Cách thức hoạt động:
Mỗi khi có một request đăng nhập/đăng xuất thành công hoặc thất bại (kể cả thông qua Session thông thường hay qua REST Framework JWT Token), Django sẽ phát ra tín hiệu. File [signals.py](file:///e:/SangKien/phan-mem-quan-ly-cv/app/core/signals.py) lắng nghe các tín hiệu này và tự động lưu thông tin vào database mà không cần can thiệp thủ công vào các controller/views xử lý login.

---

## 2. Lịch sử Thay đổi Dữ liệu (Audit Trail)

Sử dụng thư viện mã nguồn mở **`django-auditlog`** để tự động theo dõi các hành động tạo mới, cập nhật và xóa dữ liệu.

### Cách liên kết User với thay đổi:
Thư viện sử dụng middleware `auditlog.middleware.AuditlogMiddleware` đăng ký trong `settings_base.py`. Khi người dùng thực hiện thay đổi dữ liệu qua API hoặc Django Admin, middleware này bắt thông tin người dùng từ request hiện tại và gán vào log thay đổi tương ứng.

### Các Model hiện đang được giám sát:
Được đăng ký trong phương thức `ready()` của ứng dụng `quanlyvanhanh` ([apps.py](file:///e:/SangKien/phan-mem-quan-ly-cv/app/quanlyvanhanh/apps.py)):
*   `ThietBi` (Thiết bị vận hành)
*   `ThongSoVanHanh` (Thông số vận hành)
*   `ThongSoToMay` (Thông số tổ máy)
*   `ThongSoTram110KV` (Thông số trạm 110kV)
*   `NguongThongSo` (Ngưỡng cảnh báo, sự cố của thông số)

### Cấu trúc thông tin thay đổi:
Thông tin được lưu trữ trong bảng `auditlog_logentry` bao gồm:
*   **Actor (Ai thực hiện):** User đăng nhập gửi request.
*   **Action (Hành động):** `CREATE`, `UPDATE` hoặc `DELETE`.
*   **Changes (Thay đổi cái gì):** Dữ liệu lưu dưới định dạng JSON thể hiện các trường thay đổi kèm giá trị cũ và giá trị mới.
    *   *Ví dụ:* `{"ten": ["Thiết bị A", "Thiết bị B"], "trang_thai": ["Offline", "Online"]}`

---

## 3. Quản trị và Xem Log trong Django Admin

Cả hai hệ thống log đều được hiển thị trực quan trong giao diện Admin `/admin/`:

### Xem Nhật ký Hoạt động Người dùng:
*   Truy cập mục **Nhật ký hoạt động** (trong phần Core).
*   **Bảo mật:** Log này được thiết lập **chỉ đọc (readonly)** đối với tất cả quản trị viên trong Django Admin để tránh việc sửa đổi hoặc xóa dấu vết log. Không có nút "Thêm mới" hay "Xóa" trên giao diện.

### Xem Lịch sử Thay đổi Dữ liệu:
*   Truy cập mục **Log entries** (trong phần Auditlog).
*   Tại đây bạn có thể lọc thay đổi theo thời gian, theo Actor (người thực hiện), loại hành động hoặc theo Model cụ thể.

---

## 4. Cách phát triển mở rộng

### Đăng ký thêm Model cần theo dõi lịch sử:
Để theo dõi lịch sử thay đổi của một model mới, bạn chỉ cần import model đó và đăng ký trong hàm `ready()` của file `apps.py` tương ứng của ứng dụng đó.
```python
# Ví dụ đăng ký theo dõi model VatTu trong ứng dụng của bạn
from auditlog.registry import auditlog
from .models import VatTu

auditlog.register(VatTu)
```

### Tự truy vấn dữ liệu log cho Frontend API:
Nếu frontend cần hiển thị lịch sử thay đổi của một đối tượng dữ liệu cụ thể (ví dụ: hiển thị dòng thời gian chỉnh sửa thiết bị):
```python
from auditlog.models import LogEntry
from quanlyvanhanh.models import ThietBi

# Lấy đối tượng thiết bị cần xem
tb = ThietBi.objects.get(id=1)

# Lấy tất cả lịch sử thay đổi của thiết bị đó
logs = LogEntry.objects.get_for_object(tb)
for log in logs:
    print(f"Người dùng {log.actor} đã {log.get_action_display()} lúc {log.timestamp}")
    if log.action == LogEntry.Action.UPDATE:
        print("Chi tiết thay đổi:", log.changes())
```

---

## 5. Cơ chế Tự động Dọn dẹp Log (Log Cleanup)

Hệ thống cung cấp một tác vụ chạy ngầm định kỳ sử dụng **Celery Beat** để tự động xóa các log cũ quá hạn, giúp tối ưu hóa dung lượng cơ sở dữ liệu.

### Cấu hình thời gian lưu trữ log:
Trong tệp cấu hình của hệ thống (môi trường `.env`), bạn cấu hình thời gian lưu giữ log bằng cách khai báo:
```env
LOG_RETENTION_DAYS=180
```
*(Nếu không khai báo, hệ thống sẽ tự động sử dụng giá trị mặc định là **180 ngày**).*

### Cơ chế hoạt động:
*   Tác vụ ngầm được định nghĩa tại `core.tasks.clear_old_logs_task` ([tasks.py](file:///e:/SangKien/phan-mem-quan-ly-cv/app/core/tasks.py)).
*   Tác vụ này được lên lịch chạy vào lúc **2:00 sáng hàng ngày** trong `CELERY_BEAT_SCHEDULE` ([settings_base.py](file:///e:/SangKien/phan-mem-quan-ly-cv/app/app/settings_base.py)).
*   Khi chạy, nó sẽ tự động tính toán thời điểm giới hạn (`timezone.now() - LOG_RETENTION_DAYS`) và thực hiện xóa:
    1.  Các bản ghi `UserActivityLog` cũ hơn hạn định.
    2.  Các bản ghi `LogEntry` cũ của `django-auditlog`.

```
