# Release 4 — Nâng backend framework, PostgreSQL và production fail-fast

## Phạm vi

- Django 5.2 LTS và Django REST framework 3.16/3.17.
- PostgreSQL 16 với pgvector.
- Production dừng ngay khi thiếu hoặc dùng cấu hình bảo mật yếu.
- Chưa triển khai staging hoặc production trong giai đoạn thay đổi mã local.

## Lưu ý quan trọng về PostgreSQL

Không gắn volume PostgreSQL 13 trực tiếp vào container PostgreSQL 16. Hai major version không dùng chung data directory.

Compose Release 4 sử dụng volume mới:

```text
Development: vsh-dev_dev-db-data-pg16
Production:  vsh-prod_prod-db-data-pg16
```

Volume PostgreSQL 13 cũ không bị xóa và được giữ để rollback. Không chạy `docker compose down -v` trong quá trình nâng cấp.

## Sao lưu PostgreSQL 13

Thực hiện khi ứng dụng cũ vẫn dùng PostgreSQL 13:

```powershell
docker exec <postgres13-container> pg_dump `
  --username <DB_USER> `
  --dbname <DB_NAME> `
  --format custom `
  --no-owner `
  --no-acl `
  --file /tmp/vsh-pg13-before-release4.dump

docker cp <postgres13-container>:/tmp/vsh-pg13-before-release4.dump `
  E:\SangKien\backup\vsh-pg13-before-release4.dump
```

Kiểm tra file dump và tạo thêm một bản backup ngoài máy triển khai:

```powershell
Get-Item E:\SangKien\backup\vsh-pg13-before-release4.dump
```

## Khởi tạo PostgreSQL 16

Điền đầy đủ biến môi trường production, sau đó chỉ khởi động database mới:

```powershell
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml up -d db
docker compose -f docker-compose.prod.yml ps
```

Chờ health check của database đạt `healthy`.

## Phục hồi dữ liệu vào PostgreSQL 16

```powershell
docker cp E:\SangKien\backup\vsh-pg13-before-release4.dump `
  <postgres16-container>:/tmp/vsh-pg13-before-release4.dump

docker exec <postgres16-container> pg_restore `
  --username <DB_USER> `
  --dbname <DB_NAME> `
  --clean `
  --if-exists `
  --no-owner `
  --no-acl `
  /tmp/vsh-pg13-before-release4.dump
```

Nếu database đích phải tạo lại, thực hiện trong cửa sổ bảo trì và đảm bảo ứng dụng/worker cũ đã dừng ghi dữ liệu.

Sau restore:

```powershell
docker compose -f docker-compose.prod.yml run --rm app `
  sh -c "python manage.py wait_for_db && python manage.py migrate --noinput"
```

Kiểm tra extension:

```sql
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

## Production fail-fast

Compose production bắt buộc:

```text
DJANGO_SECRET_KEY
DJANGO_ALLOWED_HOSTS
CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS
DB_NAME
DB_USER
DB_PASS
```

Django từ chối khởi động khi:

- Secret ngắn, có tiền tố development hoặc dùng placeholder phổ biến.
- `ALLOWED_HOSTS` chứa `*`.
- CORS/CSRF origin không phải URL HTTPS tuyệt đối.
- Mật khẩu database dùng giá trị mặc định phổ biến.
- HTTPS redirect hoặc secure refresh cookie bị tắt.

Kiểm tra trước khi triển khai:

```powershell
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml run --rm app `
  sh -c "python manage.py check --deploy"
```

## Kiểm tra Release 4

```powershell
docker compose run --rm app `
  sh -c "python manage.py wait_for_db && python manage.py test"

docker compose run --rm app `
  sh -c "python manage.py makemigrations --check --dry-run"

docker compose run --rm app sh -c "flake8"
```

## Rollback

Nếu kiểm tra PostgreSQL 16 thất bại:

1. Dừng app, worker và beat Release 4.
2. Không xóa volume PostgreSQL 16 để còn dữ liệu điều tra.
3. Khởi động lại mã/image Release 3 cùng PostgreSQL 13 và volume cũ.
4. Xác minh dữ liệu phát sinh trong cửa sổ nâng cấp trước khi mở lại ứng dụng.

Rollback database chỉ an toàn nếu đã dừng ghi dữ liệu trong suốt quá trình chuyển đổi hoặc có kế hoạch đồng bộ dữ liệu phát sinh.
