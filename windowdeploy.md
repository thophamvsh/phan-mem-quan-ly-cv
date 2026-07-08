# Huong Dan Deploy Backend Tren Windows

Tai lieu nay dung cho may Windows chay Docker Desktop. Co the chay production compose de kiem thu local, hoac dung lam may deploy noi bo. Neu deploy public that, Linux/Raspberry + Nginx/HTTPS van la phuong an on dinh hon.

Duong dan vi du:

```text
E:\SangKien\phan-mem-quan-ly-cv
```

---

## 1. Cai Dat Cong Cu

Can co:

- Docker Desktop for Windows, bat WSL 2 backend.
- Git for Windows.
- PowerShell hoac Windows Terminal.
- Nginx for Windows neu muon reverse proxy qua port 80.

Kiem tra:

```powershell
docker --version
docker compose version
git --version
```

---

## 2. Lay Ma Nguon

```powershell
cd E:\SangKien
git clone https://github.com/thophamvsh/phan-mem-quan-ly-cv.git
cd E:\SangKien\phan-mem-quan-ly-cv
```

Neu da co source:

```powershell
cd E:\SangKien\phan-mem-quan-ly-cv
git pull
```

---

## 3. Cau Hinh Secrets Google Sheet

Production compose mount:

```yaml
./secrets:/run/secrets/vsh:ro
```

Tao thu muc:

```powershell
cd E:\SangKien\phan-mem-quan-ly-cv
mkdir secrets
```

Copy 2 file JSON vao:

```text
E:\SangKien\phan-mem-quan-ly-cv\secrets\ai-project-484022-8239457b26bb.json
E:\SangKien\phan-mem-quan-ly-cv\secrets\vinhson-account-key.json
```

Khong copy vao Git. Thu muc `secrets/` da duoc ignore.

---

## 4. Tao File `.env`

```powershell
copy .env.prod.example .env
notepad .env
```

Cau hinh mau cho Windows local:

```env
DJANGO_ENV=prod
DEBUG=False
DJANGO_SECRET_KEY=thay-bang-chuoi-bi-mat-dai-va-ngau-nhien

DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api.thoiot.uk
KHO_BACKEND_BASE_URL=http://localhost:8000

CORS_ALLOW_ALL_ORIGINS=false
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

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

Neu frontend chay tren may khac trong LAN, them origin vao `CORS_ALLOWED_ORIGINS`, vi du:

```env
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://192.168.88.104:5173
```

---

## 5. Chay Backend Bang Docker Compose

```powershell
cd E:\SangKien\phan-mem-quan-ly-cv
docker compose -f docker-compose.prod.yml up -d --build
```

Kiem tra:

```powershell
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs app -f
```

Kiem tra health:

```powershell
curl.exe http://localhost:8000/health/
```

Kiem tra secrets trong container:

```powershell
docker compose -f docker-compose.prod.yml exec app ls -l /run/secrets/vsh
```

Kiem tra Celery:

```powershell
docker compose -f docker-compose.prod.yml exec worker celery -A app inspect registered
docker compose -f docker-compose.prod.yml logs worker --tail=100
docker compose -f docker-compose.prod.yml logs celery-beat --tail=100
```

---

## 6. Tao Superuser

Cach thu cong:

```powershell
docker compose -f docker-compose.prod.yml exec app python manage.py createsuperuser
```

Du an dang nhap bang email.

Cach tu dong mot lan bang `.env`:

```env
CREATE_SUPERUSER=1
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=thay-bang-mat-khau-admin-manh
```

Recreate app:

```powershell
docker compose -f docker-compose.prod.yml up -d --force-recreate app
```

Sau khi tao xong, doi lai:

```env
CREATE_SUPERUSER=0
```

---

## 7. Nginx For Windows

Neu chi test backend local, co the truy cap thang:

```text
http://localhost:8000/admin/
```

Neu muon dung Nginx lam reverse proxy qua port 80:

1. Tai Nginx stable ban Windows tai `https://nginx.org/en/download.html`.
2. Giai nen vao `C:\nginx`.
3. Sua `C:\nginx\conf\nginx.conf`.

Server block mau:

```nginx
server {
    listen 80;
    server_name localhost api.thoiot.uk;

    client_max_body_size 100M;
    client_body_timeout 300s;

    location /static/ {
        alias E:/SangKien/phan-mem-quan-ly-cv/vol/web/static/;
        access_log off;
        expires 30d;
        add_header Cache-Control "public, no-transform";
    }

    location /media/ {
        alias E:/SangKien/phan-mem-quan-ly-cv/vol/web/media/;
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

Lenh dieu khien Nginx bang CMD Admin:

```cmd
cd C:\nginx
nginx -t
start nginx
nginx -s reload
nginx -s stop
```

Neu dung domain `api.thoiot.uk` local, them vao file hosts cua Windows:

```text
127.0.0.1 api.thoiot.uk
```

File hosts nam tai:

```text
C:\Windows\System32\drivers\etc\hosts
```

---

## 8. Frontend Ket Noi Backend

Trong project frontend `VshProject`, file `.env` nen dung:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_URL=http://localhost:8000/api
```

Neu frontend ket noi API production Raspberry:

```env
VITE_API_BASE_URL=https://api.thoiot.uk
VITE_API_URL=https://api.thoiot.uk/api
```

Luu y:

- `VITE_API_BASE_URL` khong nen co dau `/` cuoi.
- Vite doc `.env` luc build, sua `.env` xong phai build lai.

Build frontend:

```powershell
cd E:\SangKien\VshProject
npm install
npm run build
```

---

## 9. Cap Nhat Phien Ban

```powershell
cd E:\SangKien\phan-mem-quan-ly-cv
git pull
docker compose -f docker-compose.prod.yml up -d --build --force-recreate
docker compose -f docker-compose.prod.yml ps
```

Neu chi sua `.env`:

```powershell
docker compose -f docker-compose.prod.yml up -d --force-recreate app worker celery-beat
```

---

## 10. Loi Thuong Gap

### `Database unavailable`

Kiem tra:

```powershell
docker compose -f docker-compose.prod.yml logs db --tail=100
docker compose -f docker-compose.prod.yml config | findstr "DB_NAME DB_USER POSTGRES_DB POSTGRES_USER"
```

Neu DB volume da tao bang password cu, `.env` moi khong tu doi password. Neu chua can giu du lieu:

```powershell
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d --build
```

### Khong thay secrets

```powershell
docker compose -f docker-compose.prod.yml config | findstr "run/secrets/vsh"
docker compose -f docker-compose.prod.yml exec app ls -l /run/secrets/vsh
```

Neu thu muc rong, kiem tra `E:\SangKien\phan-mem-quan-ly-cv\secrets`.

### CORS bi chan

Them origin frontend vao `.env` backend:

```env
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://IP_MAY_FRONTEND:5173
```

Recreate app:

```powershell
docker compose -f docker-compose.prod.yml up -d --force-recreate app
```

### Request bi timeout

Trong `.env`:

```env
GUNICORN_TIMEOUT=300
```

Neu co Nginx, them:

```nginx
proxy_read_timeout 300s;
proxy_send_timeout 300s;
client_body_timeout 300s;
```

Recreate:

```powershell
docker compose -f docker-compose.prod.yml up -d --force-recreate app
```

### Worker/Celery Beat

`worker` va `celery-beat` khong chay web server nen healthcheck HTTP bi disable trong compose. Kiem tra dung bang log:

```powershell
docker compose -f docker-compose.prod.yml logs worker --tail=100
docker compose -f docker-compose.prod.yml logs celery-beat --tail=100
```

---

## 11. Ghi Chu

- Khong commit `.env` va file JSON credential.
- Chi chay mot `celery-beat` neu nhieu may dung chung Redis/DB.
- Sau khi sua `.env`, can recreate container.
- Sau khi sua frontend `.env`, can build lai frontend.
