# Repo Structure

## Muc tieu

Repo nay dang chua backend Django, file runtime va du lieu local. Muc tieu cau truc la giu source code tach biet voi media/static/database de de review va deploy hon.

## Cau truc hien tai

```text
phan-mem-quan-ly-cv/
|-- app/
|   |-- app/                # Django project settings, urls, wsgi, asgi
|   |-- core/               # User, auth, profile, JWT, permission nen tang
|   |-- khovattu/           # Nghiep vu kho vat tu, QR, import/export Excel
|   |-- quanlyvanhanh/      # Nghiep vu van hanh thiet bi, thong so, export
|   |-- media/              # Upload runtime, QR code, avatar
|   |-- staticfiles/        # Static collect runtime
|   `-- .expo/              # Artefact local, khong nen dua vao git
|-- data/
|   `-- db/                 # Du lieu Postgres local
|-- scripts/                # Script khoi dong/wait_for_db
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
`-- requirements.dev.txt
```

## Nen dua vao git

- `app/app`
- `app/core`
- `app/khovattu`
- `app/quanlyvanhanh`
- `scripts`
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `requirements.dev.txt`
- `docs`

## Khong nen dua vao git

- `app/media`
- `app/staticfiles`
- `app/.expo`
- `data`
- `__pycache__`
- file `.env` local

## Huong cau truc de xuat

```text
phan-mem-quan-ly-cv/
|-- app/                    # Chi chua source Django
|-- docs/                   # Tai lieu repo va nghiep vu
|-- scripts/
|-- runtime/                # Tuy chon neu khong dung Docker volume
|   |-- media/
|   |-- static/
|   `-- logs/
`-- data/                   # Chi dung local, khong track git
```

## Ghi chu don repo

- `.gitignore` da duoc bo sung de chan `app/media`, `app/staticfiles`, `app/.expo`.
- `app/media` da duoc bo khoi git index bang `git rm --cached`, nhung file local van con tren may.
- Neu can tiep tuc don repo, nen tao commit rieng cho phan "repo hygiene" de tranh lon voi thay doi nghiep vu.
