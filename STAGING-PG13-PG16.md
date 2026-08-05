# Staging và diễn tập PostgreSQL 13 → 16

## Mục tiêu và nguyên tắc an toàn

- Staging dùng project Docker `vsh-staging`, port `18000` và volume
  `vsh-staging_staging-db-data-pg16` riêng.
- Không gắn data directory PostgreSQL 13 vào PostgreSQL 16.
- Chỉ chuyển dữ liệu bằng `pg_dump`/`pg_restore` định dạng custom.
- Không commit `.env.staging`, file dump, media, static hoặc log runtime.
- Không chạy `docker compose down -v` nếu cần giữ database staging.

## Chuẩn bị cấu hình

```powershell
Copy-Item .env.staging.example .env.staging
```

Thay toàn bộ placeholder trong `.env.staging`. Origin staging phải là HTTPS vì
staging chạy bằng production settings và production fail-fast. Kiểm tra compose:

```powershell
$staging = @(
  "--env-file", ".env.staging",
  "-f", "docker-compose.prod.yml",
  "-f", "docker-compose.staging.yml"
)
docker compose @staging config --quiet
```

## Tạo dump từ PostgreSQL 13

Thực hiện khi app/worker nguồn đã dừng ghi dữ liệu:

```powershell
docker exec <postgres13-container> pg_dump `
  --username <DB_USER> `
  --dbname <DB_NAME> `
  --format custom `
  --no-owner `
  --no-acl `
  --file /tmp/vsh-pg13.dump

docker cp <postgres13-container>:/tmp/vsh-pg13.dump `
  E:\SangKien\backups\vsh-pg13.dump
```

## Restore vào PostgreSQL 16 staging

```powershell
docker compose @staging up -d --wait db redis
docker cp E:\SangKien\backups\vsh-pg13.dump `
  vsh-staging-db-1:/tmp/vsh-pg13.dump

docker exec vsh-staging-db-1 sh -c `
  'pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --clean --if-exists --no-owner --no-acl /tmp/vsh-pg13.dump'
```

Chỉ khởi động app sau khi `pg_restore` thành công:

```powershell
docker compose @staging build app
docker compose @staging up -d --wait app
docker compose @staging up -d worker celery-beat
```

## Kiểm tra sau restore

```powershell
docker compose @staging exec -T app python manage.py migrate --check
docker compose @staging exec -T app python manage.py check --deploy
docker compose @staging ps
docker compose @staging logs --tail 100 app worker celery-beat
```

Kiểm tra PostgreSQL và extension:

```sql
SHOW server_version;
SELECT extname, extversion FROM pg_extension ORDER BY extname;
SELECT count(*) FROM core_user;
SELECT count(*) FROM core_user WHERE is_active;
SELECT count(*) FROM django_migrations;
SELECT pg_database_size(current_database());
```

Với staging local chưa có reverse proxy TLS, kiểm tra health bằng cách giả lập
header HTTPS từ proxy:

```powershell
curl.exe -sS -o NUL -w "%{http_code}" `
  -H "Host: staging.localhost" `
  -H "X-Forwarded-Proto: https" `
  http://localhost:18000/health/
```

Kết quả mong đợi là `200`. Truy cập HTTP trực tiếp có thể nhận redirect HTTPS;
đây là hành vi production đúng, không phải lỗi health check.

## Reverse proxy TLS và frontend staging

Build frontend bằng cấu hình staging trước khi khởi động proxy:

```powershell
Set-Location E:\SangKien\VshProject
Copy-Item .env.staging.example .env.staging
# Sửa URL trong .env.staging thành domain staging thực tế.
npm ci
npm run build -- --mode staging

Set-Location E:\SangKien\phan-mem-quan-ly-cv
docker compose @staging up -d proxy
```

Staging local dùng `https://staging.localhost`. Caddy phục vụ frontend build và
reverse proxy `/api`, `/media`, `/static` vào Django. Caddy lưu CA/certificate
trong volume `vsh-staging_staging-caddy-data`; không commit certificate private.

Có thể xuất public root CA để kiểm tra bằng curl mà không dùng `-k`:

```powershell
docker cp `
  vsh-staging-proxy-1:/data/caddy/pki/authorities/local/root.crt `
  E:\SangKien\backups\vsh-staging-caddy-root.crt

curl.exe `
  --cacert E:\SangKien\backups\vsh-staging-caddy-root.crt `
  --ssl-no-revoke `
  https://staging.localhost/
```

`--ssl-no-revoke` chỉ cần cho Schannel trên Windows vì CA local không cung cấp
CRL; hostname và chuỗi CA vẫn được xác minh. Để smoke bằng browser không có cảnh
báo certificate, nhập public root CA vào kho Trusted Root của máy kiểm thử theo
quy trình quản trị nội bộ. Không cài CA local này trên máy production.

## Kết quả diễn tập local ngày 2026-08-05

- Restore dump PostgreSQL 13 hoàn tất, không có lỗi `pg_restore`.
- PostgreSQL: `16.14`; pgvector: `0.8.6`.
- Người dùng: `15`, tất cả `15` đang active.
- Migration: `169`, không còn migration chờ chạy.
- Database sau restore/migrate: `126491671` byte.
- Đã chạy `vacuumdb --analyze-in-stages` để tái tạo optimizer statistics.
- Index không hợp lệ: `0`; constraint chưa validate: `0`.
- App/Gunicorn healthy; HTTPS-simulated health trả `200`.
- Worker kết nối Redis và báo `ready`; Celery Beat khởi động thành công.
- Reverse proxy Caddy TLS hoạt động tại `https://staging.localhost`.
- Frontend `/` và SPA fallback trả `200`; API CSRF trả `200` và cookie có
  thuộc tính `Secure`.
- Login với mật khẩu cố ý sai trả `400` thay vì CSRF `403`; protected profile
  khi chưa đăng nhập trả `401`.
- `check --deploy` không có lỗi chặn khởi động; còn cảnh báo schema
  drf-spectacular đã biết và cảnh báo HSTS do staging local đặt HSTS bằng `0`.

## Dừng staging và rollback diễn tập

Dừng container nhưng giữ volume PostgreSQL 16:

```powershell
docker compose @staging down
```

Rollback production chỉ được thực hiện theo cửa sổ bảo trì: dừng toàn bộ ghi dữ
liệu, chạy lại image Release 3 với PostgreSQL 13 và volume 13 cũ. Không tự động
đồng bộ ngược dữ liệu đã phát sinh trên PostgreSQL 16.
