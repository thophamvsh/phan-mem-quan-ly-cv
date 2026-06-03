# Huong dan RAG cho Tro ly AI

Tai lieu nay mo ta cach su dung kho tai lieu AI tren frontend va co che backend dang xu ly RAG.

## 1. Muc dich

RAG giup Tro ly AI tra loi dua tren tai lieu noi bo da upload, vi du:

- Quy trinh van hanh
- Quy dinh an toan
- Huong dan xu ly su co
- Bao cao ky thuat
- Tai lieu rieng theo nha may

Nguoi dung upload tai lieu len he thong. Backend chuyen tai lieu thanh markdown, cat thanh cac doan nho, tao embedding va luu vao database. Khi chat, AI co the tu goi tool tim kiem tai lieu noi bo de lay ngu canh truoc khi tra loi.

## 2. Su dung tren frontend

### 2.1. Mo trang quan ly tai lieu

Vao:

```text
Cai dat -> Kho tai lieu AI
```

Hoac truy cap truc tiep:

```text
/settings/ai-documents
```

Trang nay nam tai:

```text
VshProject/src/pages/Caidat/AiDocumentsSettings.jsx
```

### 2.2. Upload tai lieu

Tai khu vuc `Upload tai lieu`, nhap/cau hinh:

- `Tieu de`: co the de trong, he thong se lay ten file.
- `File`: chon file can dua vao kho RAG.
- `Pham vi`: chon pham vi tai lieu:
  - `Chung`
  - `Song Hinh`
  - `Vinh Son`
  - `Thuong Kon Tum`
- `Loai tai lieu`: nen nhap ma ngan de loc ve sau, vi du:
  - `quy_trinh`
  - `quy_dinh`
  - `bao_cao`
  - `huong_dan`

Sau do bam:

```text
Upload va tao embedding
```

Hien tai backend xu ly dong bo ngay trong request upload. Voi file lon, thao tac nay co the mat thoi gian. Neu sau nay du lieu nhieu, nen chuyen sang hang doi nen nhu Celery/RQ.

Luu y: file Word `.doc` cu khong duoc Docling ho tro truc tiep trong pipeline hien tai. Hay chuyen file sang `.docx` hoac `.pdf` truoc khi upload. Neu upload `.doc`, API se tra ve HTTP 400 voi thong bao yeu cau chuyen dinh dang.

Voi PDF scan, backend se thu Docling truoc, sau do thu trich text bang `pypdf`. Neu noi dung text qua it, backend se fallback sang OCR bang Tesseract tieng Viet/Anh. OCR cham hon convert PDF text thong thuong, nen file scan lon co the mat nhieu thoi gian hon.

### 2.3. Trang thai tai lieu

Bang `Tai lieu RAG` hien thi:

- `Tai lieu`: ten tai lieu.
- `Pham vi`: nha may/pham vi ap dung.
- `Loai`: loai tai lieu.
- `Trang thai`:
  - `uploaded`: moi upload.
  - `processing`: dang xu ly.
  - `ready`: da san sang cho AI tra cuu.
  - `failed`: xu ly loi.
- `Chunks`: so doan noi dung da cat.

Chi cac tai lieu `ready` moi duoc dung khi AI tra cuu.

### 2.4. Tim thu retrieval

O khung `Tim thu trong kho tai lieu`, nhap cau hoi hoac tu khoa, vi du:

```text
Quy trinh xu ly khi muc nuoc ho tang nhanh la gi?
```

Bam `Tim kiem`.

Frontend goi API:

```text
POST /api/v1/documents/search/
```

Ket qua tra ve cac chunk lien quan nhat, gom:

- Ten tai lieu
- Heading/path trong tai lieu
- Diem lien quan
- Noi dung chunk

### 2.5. Xu ly lai hoac xoa tai lieu

Moi dong tai lieu co:

- `Xu ly lai`: convert lai markdown, cat chunk lai va tao embedding lai.
- `Xoa`: xoa tai lieu va toan bo chunk lien quan.

## 3. Co che backend

Backend RAG nam trong app:

```text
phan-mem-quan-ly-cv/app/documents/
```

### 3.1. Model luu tru

File:

```text
phan-mem-quan-ly-cv/app/documents/models.py
```

Co 2 model chinh:

#### Document

Luu thong tin file goc va metadata:

- `title`: tieu de tai lieu.
- `original_file`: file goc upload.
- `markdown_text`: noi dung markdown sau khi convert.
- `status`: trang thai xu ly.
- `factory`: pham vi nha may.
- `document_type`: loai tai lieu.
- `created_by`: nguoi upload.
- `processed_at`: thoi diem xu ly thanh cong.
- `error_message`: loi neu xu ly that bai.

#### DocumentChunk

Luu tung doan noi dung da cat:

- `document`: lien ket ve tai lieu goc.
- `chunk_index`: thu tu chunk.
- `heading_path`: duong dan heading, vi du `Chuong 1 > Muc 1.2`.
- `content`: noi dung chunk.
- `token_count`: uoc tinh so token/tu.
- `metadata`: thong tin phu.
- `embedding`: vector embedding.

Hien tai embedding luu bang `JSONField` de chay duoc tren ca SQLite khi dev va PostgreSQL khi deploy. Khi du lieu lon, co the chuyen sang `pgvector` hoac Qdrant.

### 3.2. API

File:

```text
phan-mem-quan-ly-cv/app/documents/urls.py
phan-mem-quan-ly-cv/app/documents/views.py
```

Routes chinh:

```text
GET    /api/v1/documents/
POST   /api/v1/documents/
DELETE /api/v1/documents/<id>/
POST   /api/v1/documents/<id>/reprocess/
POST   /api/v1/documents/search/
```

Tat ca API dung permission:

```text
CanUseAiTools
```

Nguoi dung phai co quyen su dung Tro ly AI moi quan ly/tra cuu tai lieu.

### 3.3. Pipeline ingest

Pipeline xu ly nam tai:

```text
phan-mem-quan-ly-cv/app/documents/services/ingest.py
```

Luong xu ly:

```text
Upload file
-> Tao Document
-> process_document(document)
-> Convert file sang markdown
-> Chunk markdown theo heading
-> Tao embedding cho tung chunk
-> Luu DocumentChunk
-> Cap nhat Document.status = ready
```

Neu co loi:

```text
Document.status = failed
Document.error_message = noi dung loi
```

### 3.4. Convert bang Docling

File:

```text
phan-mem-quan-ly-cv/app/documents/services/docling_convert.py
```

Co che:

- File `.md`, `.markdown`, `.txt`, `.csv`, `.log`: doc truc tiep.
- File `.doc` cu: khong nhan, can chuyen sang `.docx` hoac `.pdf`.
- File khac: thu import `docling.document_converter.DocumentConverter`.
- Neu co Docling: convert sang markdown bang `export_to_markdown()`.
- Voi PDF: neu Docling khong lay duoc text, backend thu `pypdf`; neu van qua it text thi OCR bang `pytesseract + pdf2image`.
- Neu chua cai Docling hoac convert khong duoc voi file khac: fallback doc text UTF-8.

Dependency da them:

```text
docling>=2.0.0
pypdf>=5.0.0
pytesseract>=0.3.13
pdf2image>=1.17.0
```

Docker image backend can co system packages:

```text
poppler-utils
tesseract-ocr
tesseract-ocr-vie
tesseract-ocr-eng
```

Sau khi rebuild backend, Docling va OCR fallback se duoc cai trong container.

### 3.5. Chunk theo heading

File:

```text
phan-mem-quan-ly-cv/app/documents/services/chunking.py
```

Co che:

- Tach markdown theo heading `#`, `##`, `###`...
- Luu `heading_path` de biet chunk nam trong muc nao.
- Chunk dai se duoc cat nho theo gioi han ky tu.
- Co overlap ngan giua cac chunk de giam mat ngu canh.

Mac dinh hien tai:

```text
max_chars = 2400
overlap_chars = 220
```

### 3.6. Tao embedding

File:

```text
phan-mem-quan-ly-cv/app/documents/services/embeddings.py
```

Neu co `OPENAI_API_KEY`, backend dung:

```text
text-embedding-3-small
```

Neu khong co key hoac OpenAI loi, backend dung fallback hash embedding de he thong van chay duoc khi dev/test. Fallback nay chi phu hop kiem tra ky thuat, khong nen xem la retrieval chat luong cao.

### 3.7. Search retrieval

File:

```text
phan-mem-quan-ly-cv/app/documents/services/retrieval.py
```

Luong search:

```text
Nhan query
-> Tao embedding cho query
-> Loc chunk theo quyen user va pham vi nha may
-> Tinh cosine similarity
-> Sap xep diem cao nhat
-> Tra ve top results
```

Hien tai search tinh cosine bang Python tren cac chunk lay tu database. Cach nay on cho giai doan dau. Khi so chunk lon, nen chuyen sang:

- PostgreSQL + pgvector neu muon giu trong cung DB.
- Qdrant neu du lieu vector lon, can search nhanh, filter payload tot, scaling doc lap.

## 4. Tich hop voi Tro ly AI

Tool RAG nam tai:

```text
phan-mem-quan-ly-cv/app/documents/ai_tools.py
```

Tool name:

```text
search_internal_documents
```

Tool nay duoc gan vao agent trong:

```text
phan-mem-quan-ly-cv/app/ai_tools/services.py
```

Khi nguoi dung hoi ve noi dung co kha nang nam trong tai lieu noi bo, model GPT-4o co the tu goi tool `search_internal_documents`. Backend tra ve cac chunk lien quan, sau do AI dung noi dung nay de tra loi.

Vi du cau hoi:

```text
Trong quy trinh noi bo, khi muc nuoc ho vuot gioi han tuan thi can lam gi?
```

Agent co the:

```text
Call search_internal_documents(query="khi muc nuoc ho vuot gioi han tuan thi can lam gi")
-> Nhan cac chunk lien quan
-> Tra loi dua tren tai lieu
```

## 5. Phan quyen theo nha may

RAG tai su dung scope quyen cua Tro ly AI:

```text
phan-mem-quan-ly-cv/app/ai_tools/permissions.py
```

Quy tac hien tai:

- Tai lieu `general`: nguoi co quyen AI deu co the tra cuu.
- Tai lieu `songhinh`: user co scope Song Hinh moi tra cuu duoc.
- Tai lieu `thuongkontum`: dang duoc gom theo scope Song Hinh.
- Tai lieu `vinhson`: user co scope Vinh Son moi tra cuu duoc.
- Superuser hoac user co `is_all_factories` co the tra cuu tat ca.

## 6. Cau hinh va lenh van hanh

### 6.1. Rebuild backend sau khi them Docling

Chay tai thu muc co `docker-compose.yml`:

```powershell
docker compose build
docker compose up -d
```

### 6.2. Chay migration

Xac dinh ten service backend:

```powershell
docker compose ps
```

Sau do chay:

```powershell
docker compose exec <ten_service_backend> python manage.py migrate
```

Neu service backend cua ban la `web`:

```powershell
docker compose exec web python manage.py migrate
```

### 6.3. Kiem tra Django

```powershell
docker compose exec <ten_service_backend> python manage.py check
```

## 7. Huong nang cap tiep theo

### 7.1. Chuyen ingest sang background job

Hien tai upload xu ly dong bo. Nen them Celery/RQ khi:

- File PDF/DOCX lon.
- Nhieu nguoi upload cung luc.
- Can retry tu dong khi convert/embedding loi.

Luong moi:

```text
Upload file
-> status = uploaded
-> enqueue process_document
-> worker xu ly
-> frontend polling status
```

### 7.2. Dung pgvector

Phu hop khi:

- Muon giu metadata va vector trong PostgreSQL.
- Du lieu vua phai.
- Van muon query/filter bang Django ORM/Postgres.

Can them:

- Extension `vector`.
- Field vector thay cho JSON embedding.
- Index HNSW/IVFFlat.
- Query nearest neighbor trong database.

### 7.3. Dung Qdrant

Phu hop khi:

- So chunk lon.
- Can vector search nhanh va doc lap voi database nghiep vu.
- Can filter payload theo factory, document_type, permission.
- Muon scale vector database rieng.

PostgreSQL van luu `Document`, `DocumentChunk` metadata. Qdrant luu vector va payload:

```text
chunk_id
document_id
factory
document_type
heading_path
content preview
```

Khi search:

```text
Query embedding
-> Qdrant search voi filter permission
-> Lay chunk_id
-> Join/lay metadata tu PostgreSQL neu can
-> Dua context cho AI
```

## 8. File chinh da lien quan

Backend:

```text
phan-mem-quan-ly-cv/app/documents/models.py
phan-mem-quan-ly-cv/app/documents/views.py
phan-mem-quan-ly-cv/app/documents/serializers.py
phan-mem-quan-ly-cv/app/documents/services/ingest.py
phan-mem-quan-ly-cv/app/documents/services/docling_convert.py
phan-mem-quan-ly-cv/app/documents/services/chunking.py
phan-mem-quan-ly-cv/app/documents/services/embeddings.py
phan-mem-quan-ly-cv/app/documents/services/retrieval.py
phan-mem-quan-ly-cv/app/documents/ai_tools.py
phan-mem-quan-ly-cv/app/ai_tools/services.py
```

Frontend:

```text
VshProject/src/pages/Caidat/AiDocumentsSettings.jsx
VshProject/src/services/apiAiDocuments.js
VshProject/src/App.jsx
VshProject/src/pages/Settings.jsx
```
