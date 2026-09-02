# Release E — Hoàn thiện danh mục tổ chức dùng chung

## Phạm vi

- `tochuc` sở hữu `NhaMay`, `DonViToChuc`, `BoPhan` và `NhanSu`.
- API chính thức: `/api/v1/tochuc/`.
- Django Admin và import/export nhà máy thuộc app `tochuc`.
- Quyền user/group của ContentType cũ được chuyển sang ContentType `tochuc`.
- API tổ chức cũ tiếp tục hoạt động đến hết thời gian chuyển tiếp và trả header
  `Deprecation`, `Sunset`, `Link`.
- Tên bảng PostgreSQL cũ được giữ nguyên để bảo toàn ID, khóa ngoại và dữ liệu.

## Cập nhật production

```bash
docker compose -f docker-compose.prod.yml run --rm app \
  python manage.py migrate --noinput

docker compose -f docker-compose.prod.yml run --rm app \
  python manage.py audit_organization_migration --fail-on-error
```

Để kiểm tra nghiêm ngặt cả dữ liệu thiếu phạm vi nhà máy:

```bash
docker compose -f docker-compose.prod.yml run --rm app \
  python manage.py audit_organization_migration \
  --fail-on-error --strict-factory-scope
```

Không xóa ContentType, permission hoặc endpoint legacy khi kiểm tra nghiêm ngặt
chưa đạt. Không tự động gán nhà máy cho thiết bị/thông số nếu không có quy tắc
nghiệp vụ xác định chắc chắn.

## API chuyển tiếp

| API cũ | API chính thức |
|---|---|
| `/api/v1/khovattu/auth/nha-may/` | `/api/v1/tochuc/nha-may/` |
| `/api/v1/quanlycatruc/don-vi/` | `/api/v1/tochuc/don-vi/` |
| `/api/v1/quanlycatruc/bo-phan/` | `/api/v1/tochuc/bo-phan/` |
| `/api/v1/quanlycatruc/nhan-su/` | `/api/v1/tochuc/nhan-su/` |

## Điều kiện hoàn tất

- Migration và audit ownership/quyền đạt.
- API mới đúng phạm vi nhà máy và yêu cầu đăng nhập.
- Frontend không còn gọi API danh sách nhà máy từ `khovattu`.
- Admin nhà máy mở tại `tochuc.NhaMay` và giữ chức năng XLSX.
- Test, lint và build đạt.
- ContentType/API legacy chỉ được xóa ở release sau khi production không còn
  request và audit strict đạt.
