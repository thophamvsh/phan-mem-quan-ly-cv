# Huong Dan Lenh Docker / Docker Compose Cho Backend Server

Tai lieu nay tong hop cac lenh Docker thuong dung khi van hanh backend `phan-mem-quan-ly-cv`.

Mac dinh chay tai thu muc:

```bash
cd /var/www/ats-backend/phan-mem-quan-ly-cv
```

File compose production:

```bash
docker-compose.prod.yml
```

Neu chay local development thi bo `-f docker-compose.prod.yml`.

---

## 1. Kiem Tra Docker

Kiem tra phien ban:

```bash
docker --version
docker compose version
```

Kiem tra Docker daemon co dang chay:

```bash
docker info
```

Xem tat ca container:

```bash
docker ps
docker ps -a
```

Xem image:

```bash
docker images
```

Xem volume:

```bash
docker volume ls
```

Xem network:

```bash
docker network ls
```

---

## 2. Docker Compose Production

Khoi dong toan bo stack production:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Build lai image va khoi dong:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Build lai va recreate tat ca service:

```bash
docker compose -f docker-compose.prod.yml up -d --build --force-recreate
```

Dung stack:

```bash
docker compose -f docker-compose.prod.yml stop
```

Dung va xoa container/network, giu volume database:

```bash
docker compose -f docker-compose.prod.yml down
```

Dung va xoa ca volume database:

```bash
docker compose -f docker-compose.prod.yml down -v
```

Can than: `down -v` se xoa database volume production.

Khoi dong lai service cu the:

```bash
docker compose -f docker-compose.prod.yml restart app
docker compose -f docker-compose.prod.yml restart worker
docker compose -f docker-compose.prod.yml restart celery-beat
docker compose -f docker-compose.prod.yml restart db
docker compose -f docker-compose.prod.yml restart redis
```

Recreate service sau khi sua `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate app
docker compose -f docker-compose.prod.yml up -d --force-recreate worker celery-beat
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker celery-beat
```

---

## 3. Xem Trang Thai

Xem trang thai cac service:

```bash
docker compose -f docker-compose.prod.yml ps
```

Xem cau hinh compose da resolve bien `.env`:

```bash
docker compose -f docker-compose.prod.yml config
```

Kiem tra cau hinh compose co hop le:

```bash
docker compose -f docker-compose.prod.yml config --quiet
```

Loc bien quan trong:

```bash
docker compose -f docker-compose.prod.yml config | grep -E "DJANGO_ENV|DB_NAME|DB_USER|POSTGRES_DB|POSTGRES_USER|CORS_ALLOWED_ORIGINS|DJANGO_ALLOWED_HOSTS"
```

Kiem tra mount secrets:

```bash
docker compose -f docker-compose.prod.yml config | grep -A5 -B2 "/run/secrets/vsh"
```

---

## 4. Xem Logs

Theo doi log app:

```bash
docker compose -f docker-compose.prod.yml logs app -f
```

Xem 100 dong cuoi:

```bash
docker compose -f docker-compose.prod.yml logs app --tail=100
```

Log worker:

```bash
docker compose -f docker-compose.prod.yml logs worker -f
docker compose -f docker-compose.prod.yml logs worker --tail=100
```

Log Celery Beat:

```bash
docker compose -f docker-compose.prod.yml logs celery-beat -f
docker compose -f docker-compose.prod.yml logs celery-beat --tail=100
```

Log database:

```bash
docker compose -f docker-compose.prod.yml logs db -f
docker compose -f docker-compose.prod.yml logs db --tail=100
```

Log Redis:

```bash
docker compose -f docker-compose.prod.yml logs redis --tail=100
```

Xem log cua tat ca service:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

---

## 5. Vao Container

Mo shell trong app:

```bash
docker compose -f docker-compose.prod.yml exec app sh
```

Chay lenh Python/Django:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py check
docker compose -f docker-compose.prod.yml exec app python manage.py showmigrations
docker compose -f docker-compose.prod.yml exec app python manage.py migrate --noinput
docker compose -f docker-compose.prod.yml exec app python manage.py collectstatic --noinput
```

Mo Django shell:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py shell
```

Tao superuser:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py createsuperuser
```

Chay lenh khong can TTY, huu ich cho script:

```bash
docker compose -f docker-compose.prod.yml exec -T app python manage.py check
```

---

## 6. Kiem Tra Health Va API

Kiem tra health ben trong host:

```bash
curl http://localhost:8000/health/
```

Kiem tra qua domain HTTPS:

```bash
curl -i https://api.thoiot.uk/health/
```

Kiem tra CORS production:

```bash
curl -i -X OPTIONS https://api.thoiot.uk/api/v1/auth/login/ \
  -H "Origin: https://thoiot.uk" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

Kiem tra CORS frontend local:

```bash
curl -i -X OPTIONS https://api.thoiot.uk/api/v1/auth/login/ \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

Kiem tra CORS frontend dien thoai/LAN:

```bash
curl -i -X OPTIONS https://api.thoiot.uk/api/v1/auth/login/ \
  -H "Origin: http://192.168.88.104:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

Neu dung, response co:

```text
access-control-allow-origin: <origin>
```

---

## 7. Database PostgreSQL

Mo psql trong container DB:

```bash
docker compose -f docker-compose.prod.yml exec db psql -U vsh_user -d vsh_prod
```

Kiem tra database san sang:

```bash
docker compose -f docker-compose.prod.yml exec db pg_isready -U vsh_user -d vsh_prod
```

Liet ke database:

```bash
docker compose -f docker-compose.prod.yml exec db psql -U vsh_user -d vsh_prod -c "\l"
```

Liet ke bang:

```bash
docker compose -f docker-compose.prod.yml exec db psql -U vsh_user -d vsh_prod -c "\dt"
```

Doi password user DB:

```bash
docker compose -f docker-compose.prod.yml exec db psql -U vsh_user -d vsh_prod -c "ALTER USER vsh_user WITH PASSWORD 'mat-khau-moi';"
```

Backup database:

```bash
mkdir -p backups
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U vsh_user -d vsh_prod > backups/vsh_prod_$(date +%Y%m%d_%H%M%S).sql
```

Restore database tu file SQL:

```bash
docker compose -f docker-compose.prod.yml exec -T db psql -U vsh_user -d vsh_prod < backups/ten_file_backup.sql
```

Backup dang custom format:

```bash
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U vsh_user -d vsh_prod -Fc > backups/vsh_prod.dump
```

Restore custom format:

```bash
docker compose -f docker-compose.prod.yml exec -T db pg_restore -U vsh_user -d vsh_prod --clean --if-exists < backups/vsh_prod.dump
```

---

## 8. Redis

Mo Redis CLI:

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli
```

Ping Redis:

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

Xem so key:

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli dbsize
```

Xoa toan bo Redis DB hien tai:

```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli flushdb
```

Can than: `flushdb` se xoa queue/result trong Redis.

---

## 9. Celery Worker Va Celery Beat

Kiem tra worker da register task:

```bash
docker compose -f docker-compose.prod.yml exec worker celery -A app inspect registered
```

Kiem tra worker active:

```bash
docker compose -f docker-compose.prod.yml exec worker celery -A app inspect active
```

Kiem tra scheduled/reserved:

```bash
docker compose -f docker-compose.prod.yml exec worker celery -A app inspect scheduled
docker compose -f docker-compose.prod.yml exec worker celery -A app inspect reserved
```

Kiem tra Celery ping:

```bash
docker compose -f docker-compose.prod.yml exec worker celery -A app inspect ping
```

Xem log worker va beat:

```bash
docker compose -f docker-compose.prod.yml logs worker --tail=100
docker compose -f docker-compose.prod.yml logs celery-beat --tail=100
```

Restart worker/beat:

```bash
docker compose -f docker-compose.prod.yml restart worker celery-beat
```

Chay task bang Django shell:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py shell
```

Trong shell:

```python
from thongsothuyvan.tasks import save_all_realtime_snapshots_task
save_all_realtime_snapshots_task.delay()
```

Luu y: neu nhieu server dung chung Redis/DB, chi nen chay mot `celery-beat`.

---

## 10. Secrets Va File Upload

Kiem tra secrets tren host:

```bash
ls -ld secrets
ls -l secrets
```

Kiem tra secrets trong container:

```bash
docker compose -f docker-compose.prod.yml exec app ls -l /run/secrets/vsh
docker compose -f docker-compose.prod.yml exec worker ls -l /run/secrets/vsh
```

Kiem tra static/media/logs:

```bash
ls -l vol/web/static
ls -l vol/web/media
ls -l vol/web/logs
```

Cap quyen secrets tren Linux/Raspberry:

```bash
sudo chmod 755 /opt/vsh
sudo chmod 755 /opt/vsh/secrets
sudo chmod 644 /opt/vsh/secrets/*.json
```

---

## 11. Build Image

Build rieng cac image production:

```bash
docker compose -f docker-compose.prod.yml build app worker celery-beat
```

Build khong dung cache:

```bash
docker compose -f docker-compose.prod.yml build --no-cache app worker celery-beat
```

Build hien log chi tiet:

```bash
docker compose -f docker-compose.prod.yml build --progress=plain app worker celery-beat
```

Xem image sau build:

```bash
docker images | grep vsh
```

---

## 12. Cleanup Docker

Xoa container da stop:

```bash
docker container prune
```

Xoa image khong dung:

```bash
docker image prune
```

Xoa build cache:

```bash
docker builder prune
```

Xoa tat ca resource khong dung:

```bash
docker system prune
```

Xoa ca volume khong dung:

```bash
docker system prune --volumes
```

Can than: khong chay `--volumes` neu chua chac volume DB nao dang dung.

Xem dung luong Docker:

```bash
docker system df
```

---

## 13. Quy Trinh Deploy Code Moi

Quy trinh an toan:

```bash
cd /var/www/ats-backend/phan-mem-quan-ly-cv
git pull
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml up -d --build --force-recreate
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health/
```

Theo doi log:

```bash
docker compose -f docker-compose.prod.yml logs app --tail=100
docker compose -f docker-compose.prod.yml logs worker --tail=100
docker compose -f docker-compose.prod.yml logs celery-beat --tail=100
```

Neu chi sua `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker celery-beat
```

Neu chi sua Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 14. Lenh Development Local

Chay stack development:

```bash
docker compose up -d --build
```

Xem log dev:

```bash
docker compose logs app -f
docker compose logs worker -f
docker compose logs celery-beat -f
```

Dung dev:

```bash
docker compose down
```

Vao app dev:

```bash
docker compose exec app sh
```

---

## 15. Loi Thuong Gap

### App bao `Database unavailable`

Xem log DB:

```bash
docker compose -f docker-compose.prod.yml logs db --tail=100
```

Kiem tra bien DB:

```bash
docker compose -f docker-compose.prod.yml config | grep -E "DB_NAME|DB_USER|POSTGRES_DB|POSTGRES_USER"
```

Neu volume DB cu da tao voi password khac, `.env` moi khong tu doi password. Neu chua co du lieu quan trong:

```bash
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
```

### Loi CORS tren browser

Them origin frontend vao `.env` backend:

```env
CORS_ALLOWED_ORIGINS=https://thoiot.uk,http://localhost:5173,http://127.0.0.1:5173,http://192.168.88.104:5173
```

Recreate:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate app
```

### Khong thay `/run/secrets/vsh`

```bash
grep -n "run/secrets/vsh" docker-compose.prod.yml
docker compose -f docker-compose.prod.yml config | grep -A5 -B2 "/run/secrets/vsh"
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker celery-beat
```

### Permission denied khi doc secrets

```bash
sudo chmod 755 /opt/vsh
sudo chmod 755 /opt/vsh/secrets
sudo chmod 644 /opt/vsh/secrets/*.json
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker celery-beat
```

### Backend timeout

Trong `.env`:

```env
GUNICORN_TIMEOUT=300
```

Recreate app:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate app
```

Neu co Nginx, them:

```nginx
proxy_read_timeout 300s;
proxy_send_timeout 300s;
client_body_timeout 300s;
```

Reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Worker/Beat khong xu ly task

```bash
docker compose -f docker-compose.prod.yml logs worker --tail=200
docker compose -f docker-compose.prod.yml logs celery-beat --tail=200
docker compose -f docker-compose.prod.yml exec worker celery -A app inspect registered
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

---

## 16. Ghi Chu An Toan

- Khong commit `.env`, file JSON credential, backup database.
- Khong chay `docker compose down -v` tren production neu chua backup DB.
- Chi chay mot `celery-beat` neu nhieu server dung chung Redis/DB.
- Sau khi sua `.env`, phai recreate container.
- Sau khi sua Dockerfile/requirements, phai build lai image.
