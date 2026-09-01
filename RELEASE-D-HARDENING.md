# Release D — Ổn định vận hành và khả năng phục hồi

Release D không thêm nghiệp vụ. Mục tiêu là loại bỏ khác biệt môi trường và
giúp lỗi/backup production có thể kiểm tra được.

## Phạm vi

1. Migration bảo đảm PostgreSQL có extension `unaccent` cho tìm thiết bị không dấu.
2. Lỗi trong DRF trả JSON an toàn; lỗi Django tại đường dẫn `/api/` cũng trả JSON khi `DEBUG=False`.
3. Route `/api/` cũ tiếp tục hoạt động nhưng có header `Deprecation`, `Sunset` và `Link` đến `/api/v1/`.
4. Frontend chuyển endpoint còn lại sang `/api/v1/` trước khi route cũ bị gỡ trong một release tương lai.
5. Backup media có checksum, lệnh verify và restore chỉ vào thư mục trống.

## Cập nhật production

```bash
docker compose -f docker-compose.prod.yml run --rm app \
  python manage.py migrate --noinput

docker compose -f docker-compose.prod.yml run --rm app \
  python manage.py shell -c \
  "from django.db import connection; c=connection.cursor(); c.execute(\"select extversion from pg_extension where extname='unaccent'\"); print(c.fetchone())"
```

## Backup media

```bash
bash ./scripts/backup_media.sh

archive="$(ls -1t backups/media/vsh-media-*.tar.gz | head -1)"
bash ./scripts/verify_media_backup.sh "$archive"
```

Sao chép cả file `.tar.gz` và `.sha256` sang thiết bị/vị trí khác Orange Pi.
Database dump và media backup là hai phần độc lập, phải giữ cùng một mốc thời gian.

## Diễn tập restore không ghi đè

```bash
mkdir -p /home/orangepi/restore-test/media
bash ./scripts/restore_media_backup.sh "$archive" /home/orangepi/restore-test/media
find /home/orangepi/restore-test/media -type f | head
```

Script từ chối restore vào thư mục không rỗng. Chỉ đổi media mount production
sau khi đã kiểm tra dữ liệu phục hồi.

## Kiểm tra API

```bash
curl -I https://api.thoiot.uk/api/quanlyvanhanh/thiet-bi/
curl -I https://api.thoiot.uk/api/v1/quanlyvanhanh/thiet-bi/
```

Request legacy có header `Deprecation: true`; request v1 không có header này.

## Điều kiện đạt

- Migration và `migrate --check` thành công.
- Tìm `may cat` trả về thiết bị tên `Máy cắt` trên PostgreSQL.
- API 404/500 không trả trang HTML trong production.
- Route legacy vẫn hoạt động trong giai đoạn chuyển tiếp.
- Backup media qua checksum và đọc được danh sách tar.
- Backend test/lint và frontend audit/lint/test/build đạt.
