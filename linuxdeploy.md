# Huong Dan Deploy Backend Tren Linux / Raspberry Pi

Tai lieu nay dung cho server Linux, Raspberry Pi hoac Ubuntu Server. Backend chay bang Docker Compose production, Nginx lam reverse proxy, Redis/Celery xu ly tac vu nen, PostgreSQL/pgvector lam database.

Duong dan mac dinh trong tai lieu:

```bash
/var/www/ats-backend/phan-mem-quan-ly-cv
```

Domain API dang dung:

```text
https://api.thoiot.uk
```

Neu server/domain khac, thay cac gia tri tuong ung.

---

## 1. Cai Dat He Thong

Cap nhat may:

```bash
sudo apt update && sudo apt upgrade -y
```

Cai Docker va Docker Compose plugin:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

Kiem tra:

```bash
docker --version
docker compose version
```

Cai Git va Nginx:

```bash
sudo apt install -y git nginx
```

---

## 2. Lay Ma Nguon

```bash
sudo mkdir -p /var/www/ats-backend
sudo chown -R $USER:$USER /var/www/ats-backend
cd /var/www/ats-backend
git clone https://github.com/thophamvsh/phan-mem-quan-ly-cv.git
cd phan-mem-quan-ly-cv
```

Neu da clone roi:

```bash
cd /var/www/ats-backend/phan-mem-quan-ly-cv
git pull
```

---

## 3. Cau Hinh Secrets Google Sheet

Khong commit file JSON credential len Git. Production compose se mount thu muc `./secrets` vao container tai:

```text
/run/secrets/vsh
```

### 3.1. Thu muc secrets tren Raspberry

Neu ban dang luu key tai `/opt/vsh/secrets`:

```bash
sudo mkdir -p /opt/vsh/secrets
sudo chown -R $USER:$USER /opt/vsh/secrets
```

Copy 2 file vao:

```text
/opt/vsh/secrets/ai-project-484022-8239457b26bb.json
/opt/vsh/secrets/vinhson-account-key.json
```

Tao symlink trong project:

```bash
cd /var/www/ats-backend/phan-mem-quan-ly-cv
rm -rf secrets
ln -s /opt/vsh/secrets secrets
```

Cap quyen doc cho container user `django`:

```bash
sudo chmod 755 /opt/vsh
sudo chmod 755 /opt/vsh/secrets
sudo chmod 644 /opt/vsh/secrets/*.json
```

Kiem tra:

```bash
ls -ld secrets
ls -l secrets
```

---

## 4. Tao File `.env` Production

Tao tu file mau:

```bash
cp .env.prod.example .env
nano .env
```

Cau hinh toi thieu:

```env
DJANGO_ENV=prod
DEBUG=False
DJANGO_SECRET_KEY=thay-bang-chuoi-bi-mat-dai-va-ngau-nhien

DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api.thoiot.uk
KHO_BACKEND_BASE_URL=https://api.thoiot.uk

CORS_ALLOW_ALL_ORIGINS=false
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOWED_ORIGINS=https://thoiot.uk

DB_HOST=db
DB_PORT=5432
DB_NAME=vsh_prod
DB_USER=vsh_user
DB_PASS=thay-bang-mat-khau-db-manh

APP_PORT=8000
DOCUMENTS_USE_CELERY=true
REALTIME_SNAPSHOT_SCHEDULER_ENABLED=False
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CELERY_TIMEZONE=Asia/Ho_Chi_Minh
CELERY_WORKER_CONCURRENCY=2

SONGHINH_GOOGLE_CREDENTIALS=/run/secrets/vsh/ai-project-484022-8239457b26bb.json
VINHSON_GOOGLE_CREDENTIALS=/run/secrets/vsh/vinhson-account-key.json

RUN_MIGRATIONS=1
COLLECTSTATIC=1
CREATE_SUPERUSER=0
```

Neu dang test frontend tu may tinh local:

```env
CORS_ALLOWED_ORIGINS=https://thoiot.uk,http://localhost:5173,http://127.0.0.1:5173,http://192.168.88.104:5173
```

Luu y: origin CORS khong co dau `/` cuoi.

---

## 5. Chay Docker Compose Production

Tao thu muc volume:

```bash
mkdir -p vol/web/static vol/web/media vol/web/logs
```

Build va chay:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Kiem tra trang thai:

```bash
docker compose -f docker-compose.prod.yml ps
```

Xem log:

```bash
docker compose -f docker-compose.prod.yml logs app -f
docker compose -f docker-compose.prod.yml logs worker -f
docker compose -f docker-compose.prod.yml logs celery-beat -f
docker compose -f docker-compose.prod.yml logs db --tail=100
```

Kiem tra health:

```bash
curl http://localhost:8000/health/
```

Kiem tra container thay secrets:

```bash
docker compose -f docker-compose.prod.yml exec app ls -l /run/secrets/vsh
```

---

## 6. Tao Superuser

Cach thu cong:

```bash
docker compose -f docker-compose.prod.yml exec app python manage.py createsuperuser
```

Du an dung email de dang nhap.

Cach tu dong mot lan bang `.env`:

```env
CREATE_SUPERUSER=1
DJANGO_SUPERUSER_EMAIL=admin@thoiot.uk
DJANGO_SUPERUSER_PASSWORD=thay-bang-mat-khau-admin-manh
```

Chay lai app:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate app
```

Sau khi tao xong, nen doi lai:

```env
CREATE_SUPERUSER=0
```

roi recreate app lan nua.

---

## 7. Cau Hinh Nginx Reverse Proxy

Tao file:

```bash
sudo nano /etc/nginx/sites-available/api.thoiot.uk
```

Noi dung:

```nginx
server {
    listen 80;
    server_name api.thoiot.uk;

    client_max_body_size 100M;
    client_body_timeout 300s;

    location /static/ {
        alias /var/www/ats-backend/phan-mem-quan-ly-cv/vol/web/static/;
        access_log off;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /media/ {
        alias /var/www/ats-backend/phan-mem-quan-ly-cv/vol/web/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        send_timeout 300s;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Kich hoat:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/api.thoiot.uk /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 8. HTTPS Bang Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.thoiot.uk
```

Kiem tra tu dong gia han:

```bash
sudo certbot renew --dry-run
```

---

## 9. Kiem Tra Sau Deploy

Backend:

```bash
curl -i https://api.thoiot.uk/health/
```

CORS cho frontend production:

```bash
curl -i -X OPTIONS https://api.thoiot.uk/api/v1/auth/login/ \
  -H "Origin: https://thoiot.uk" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

CORS cho frontend local/mobile:

```bash
curl -i -X OPTIONS https://api.thoiot.uk/api/v1/auth/login/ \
  -H "Origin: http://192.168.88.104:5173" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

Neu dung dung, response co header:

```text
access-control-allow-origin: <origin-da-gui>
```

Celery:

```bash
docker compose -f docker-compose.prod.yml exec worker celery -A app inspect registered
docker compose -f docker-compose.prod.yml logs celery-beat --tail=100
docker compose -f docker-compose.prod.yml logs worker --tail=100
```

---

## 10. Cap Nhat Phien Ban Moi

```bash
cd /var/www/ats-backend/phan-mem-quan-ly-cv
git pull
docker compose -f docker-compose.prod.yml up -d --build --force-recreate
docker compose -f docker-compose.prod.yml ps
```

Neu chi sua `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker celery-beat
```

---

## 11. Loi Thuong Gap

### App bao `Database unavailable`

Kiem tra:

```bash
docker compose -f docker-compose.prod.yml logs db --tail=100
docker compose -f docker-compose.prod.yml config | grep -E "DB_NAME|DB_USER|POSTGRES_DB|POSTGRES_USER"
```

Neu volume DB da tao voi password cu, `DB_PASS` moi khong tu doi password. Neu chua co du lieu quan trong:

```bash
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
```

Can giu du lieu thi doi password trong PostgreSQL:

```bash
docker compose -f docker-compose.prod.yml exec db psql -U vsh_user -d vsh_prod -c "ALTER USER vsh_user WITH PASSWORD 'mat-khau-moi';"
docker compose -f docker-compose.prod.yml restart app worker celery-beat
```

### Khong thay `/run/secrets/vsh`

Kiem tra compose co mount secrets:

```bash
grep -n "run/secrets/vsh" docker-compose.prod.yml
docker compose -f docker-compose.prod.yml config | grep -A5 -B2 "/run/secrets/vsh"
```

Kiem tra symlink:

```bash
ls -ld secrets
ls -l /opt/vsh/secrets
```

### `Permission denied` khi doc secrets

```bash
sudo chmod 755 /opt/vsh
sudo chmod 755 /opt/vsh/secrets
sudo chmod 644 /opt/vsh/secrets/*.json
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker celery-beat
```

### CORS bi chan tren browser

Them origin frontend vao `.env`:

```env
CORS_ALLOWED_ORIGINS=https://thoiot.uk,http://localhost:5173,http://127.0.0.1:5173,http://192.168.88.104:5173
```

Restart:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate app
```

### Request bi timeout

Trong `.env` backend:

```env
GUNICORN_TIMEOUT=300
```

Trong Nginx them/sua:

```nginx
proxy_read_timeout 300s;
proxy_send_timeout 300s;
client_body_timeout 300s;
```

Reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
docker compose -f docker-compose.prod.yml up -d --force-recreate app
```

### Worker hoac celery-beat bi unhealthy

Trong compose production da disable healthcheck cho `worker` va `celery-beat` vi hai service nay khong chay HTTP server. Neu van thay unhealthy, pull code moi va recreate:

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build --force-recreate worker celery-beat
```

---

## 12. Ghi Chu Van Hanh

- Chi chay mot `celery-beat` neu nhieu thiet bi dung chung Redis/DB production. Chay nhieu beat se ban task dinh ky trung.
- Khong commit `.env` va file JSON credential.
- Neu frontend chay tu may khac trong LAN, them origin `http://IP_FRONTEND:5173` vao `CORS_ALLOWED_ORIGINS`.
- Sau khi sua `.env`, can recreate container thi bien moi moi co tac dung.
