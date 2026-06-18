# Hướng dẫn chi tiết về App `documents` (Kho tài liệu AI / RAG)

App `documents` là một module quan trọng trong hệ thống backend Django, chịu trách nhiệm lưu trữ, xử lý (ingest), cắt nhỏ (chunk), lập chỉ mục (index) và thực hiện tìm kiếm ngữ nghĩa (RAG - Retrieval-Augmented Generation) trên các tài liệu PDF, DOCX, TXT phục vụ cho trợ lý AI.

---

## 1. Cấu trúc thư mục của App

```text
app/documents/
├── admin.py            # Đăng ký admin cho các Model Document, DocumentChunk
├── apps.py             # Cấu hình Django app
├── models.py           # Định nghĩa cấu trúc bảng CSDL (Document & DocumentChunk)
├── permissions.py      # Phân quyền sử dụng Kho tài liệu AI (CanUseAiDocuments)
├── serializers.py      # Chuyển đổi dữ liệu (nhập/xuất file, tham số tìm kiếm)
├── tasks.py            # Celery task chạy bất đồng bộ quá trình nạp tài liệu
├── urls.py             # Định nghĩa các endpoint API
├── views.py            # Các API Controller xử lý nghiệp vụ chính
└── services/           # Chứa toàn bộ logic xử lý lõi của app
    ├── chunking.py       # Thuật toán cắt văn bản Markdown thành các đoạn nhỏ hơn
    ├── docling_convert.py # Trích xuất và chuyển đổi các định dạng file sang Markdown
    ├── embeddings.py     # Tạo vector nhúng (embeddings) thông qua OpenAI API hoặc thuật toán Hash
    ├── ingest.py         # Quản lý quy trình nạp tài liệu (Convert -> Chunk -> Embed -> Save)
    ├── normalization.py  # Chuẩn hóa văn bản, ngày tháng và loại tài liệu
    ├── query_parser.py   # Phân tích cú pháp câu truy vấn (tách ngày, điều khoản, nhà máy...)
    ├── ranker.py         # Chứa luật chấm điểm và xếp hạng sự trùng khớp của các chunks
    └── retrieval.py      # Logic truy xuất kết hợp (Hybrid Search: Vector + Keyword)
```

---

## 2. Cấu trúc Cơ sơ Dữ liệu (`models.py`)

Bao gồm 2 bảng CSDL chính được liên kết 1-nhiều với nhau:

### 2.1 Model `Document` (Bản ghi tài liệu gốc)
- **`title`**: Tiêu đề tài liệu.
- **`original_file`**: File gốc được lưu trên máy chủ (đường dẫn lưu: `ai_documents/%Y/%m/`).
- **`markdown_text`**: Nội dung văn bản sau khi chuyển đổi sang định dạng Markdown.
- **`status`**: Trạng thái xử lý file (`uploaded`, `processing`, `ready`, `failed`).
- **`factory`**: Lọc theo nhà máy liên kết (`general` - Chung, `songhinh`, `vinhson`, `thuongkontum`).
- **`document_type`**: Loại tài liệu (ví dụ: Quy trình, Quy chuẩn, Thiết kế...).
- **`created_by`**: User tải tài liệu lên.

### 2.2 Model `DocumentChunk` (Đoạn tài liệu sau khi cắt nhỏ)
- **`document`**: Liên kết khóa ngoại (Foreign Key) trỏ đến `Document`.
- **`chunk_index`**: Chỉ mục sắp xếp của đoạn đó trong toàn bộ tài liệu.
- **`heading_path`**: Đường dẫn tiêu đề chứa đoạn đó (ví dụ: `Chương I > Điều 1`).
- **`content`**: Nội dung văn bản của đoạn (giới hạn ký tự tối đa khoảng 2600 ký tự).
- **`page_from` / `page_to`**: Số trang tương ứng trong file PDF gốc.
- **`metadata`**: Trường JSON lưu thông tin cấu trúc (date_ranges, article_refs, numbers...).
- **`embedding`**: Vector nhúng **1536 chiều** sử dụng module `pgvector.django.VectorField` hỗ trợ tìm kiếm không gian vector trực tiếp bằng SQL.

---

## 3. Quy trình nạp tài liệu (Ingestion Pipeline)

Được điều phối bởi hàm `process_document(document)` trong `services/ingest.py`, bao gồm các bước:

1. **Trích xuất và chuyển đổi (`services/docling_convert.py`)**:
   - Sử dụng công cụ **Docling** (`DocumentConverter`) để trích xuất file PDF, DOCX, TXT sang Markdown.
   - Nếu không cài được Docling hoặc Docling lỗi, hệ thống sẽ fallback sang dùng **`pypdf`** để đọc text trực tiếp từ PDF.
   - Nếu text lấy ra quá ngắn hoặc bị lỗi font (phát hiện file PDF dạng scan/ảnh chụp), hệ thống sẽ sử dụng **OCR Tesseract** (thông qua `pytesseract` và `pdf2image`) với cấu hình hỗ trợ ngôn ngữ tiếng Việt + tiếng Anh (`vie+eng`).
2. **Cắt nhỏ tài liệu (`services/chunking.py`)**:
   - Trước tiên loại bỏ các dòng lặp (như header/footer tiêu đề trang) bằng thuật toán tần suất dòng lặp.
   - Cắt văn bản dựa trên cấu trúc các tiêu đề Markdown (`#`, `##`, `**Điều...**`) tạo thành các đoạn nhỏ logic.
   - Nếu đoạn nào dài vượt quá `max_chars=2600`, nó sẽ được chia nhỏ tiếp với độ gối đầu trùng lặp (`overlap_chars=180`) để tránh đứt gãy thông tin ngữ cảnh.
   - Trích xuất tự động siêu dữ liệu (metadata) của từng đoạn: các mốc ngày tháng (`date_ranges`), số điều luật (`article_refs`), số liệu số (`numbers`) và trang (`page_from`, `page_to`).
3. **Tính toán vector nhúng (`services/embeddings.py`)**:
   - Dùng model `text-embedding-3-small` của **OpenAI** để tạo vector 1536 chiều.
   - Nếu không cấu hình `OPENAI_API_KEY`, hệ thống sẽ tự động fallback sang thuật toán nội bộ **Hash Embedding** (`_hash_embedding`) băm các từ và chuẩn hóa vector 1536 chiều, đảm bảo hệ thống luôn hoạt động độc lập không phụ thuộc Internet khi cần thiết.
4. **Lưu vào CSDL an toàn (`services/ingest.py`)**:
   - Toàn bộ quá trình lưu được đặt trong một `transaction.atomic()`.
   - Đầu tiên **xóa sạch** các chunks cũ liên kết với tài liệu (`DocumentChunk.objects.filter(document=document).delete()`).
   - Sau đó lưu hàng loạt các chunks mới được tạo.
   - Cập nhật trạng thái tài liệu sang `ready`.

---

## 4. Quy trình tìm kiếm và truy xuất (Hybrid Search & Retrieval)

Quá trình tìm kiếm ngữ nghĩa được điều phối bởi hàm `search_documents(...)` trong `services/retrieval.py`:

1. **Phân tích câu truy vấn (`services/query_parser.py`)**:
   - Sử dụng Regex để trích xuất từ câu hỏi của người dùng các bộ lọc động như: các mốc ngày tháng, số hiệu điều luật (`Điều 12`, `dieu 5`), số liệu và nhà máy được nhắc tới (ví dụ: "Sông Hinh").
2. **Xác định phạm vi dữ liệu (`_resolve_allowed_factories`)**:
   - Dựa trên quyền của User đăng nhập (chỉ được xem tài liệu thuộc nhà máy mình quản lý hoặc tài liệu chung) để tạo bộ lọc `factory__in` thích hợp.
3. **Thu thập ứng viên (Hybrid Search)**:
   - **Semantic Search (Tìm kiếm ngữ nghĩa)**: Tính toán vector nhúng của câu truy vấn, sau đó truy vấn CSDL PostgreSQL tính khoảng cách cosine (`CosineDistance`) giữa các chunks và câu hỏi để lấy các ứng viên có khoảng cách gần nhất.
   - **Keyword Search (Tìm kiếm từ khóa)**: Tìm kiếm gần đúng dạng chứa ký tự (`icontains`) các cụm từ quan trọng, số điều khoản, số mốc thời gian để bổ sung các ứng viên bị trượt do khoảng cách vector nhưng trùng khít từ khóa.
4. **Xếp hạng và chấm điểm hỗn hợp (`services/ranker.py`)**:
   - Chấm điểm từng ứng viên dựa trên công thức nhân/cộng trọng số.
   - Lọc bỏ các kết quả có điểm tổng hợp thấp hơn ngưỡng `MIN_FINAL_SCORE = 0.30`.
   - Loại bỏ các kết quả trùng lặp nằm quá gần nhau cùng một mục văn bản (`_dedupe_nearby_chunks`).
5. **Định dạng kết quả trả về**:
   - Tô màu nổi bật (`highlightText`) từ khóa tìm kiếm.
   - Mở rộng ngữ cảnh đọc xung quanh đoạn nếu truy vấn yêu cầu xem chi tiết.
   - Trả về đường dẫn xem tài liệu kèm chỉ số trang cụ thể để hiển thị lên frontend iframe.

---

## 5. API Endpoints của App (`views.py` & `urls.py`)

App cung cấp các endpoint sau dưới định dạng REST API:

- **`GET /api/v1/documents/`**: Danh sách tài liệu (hỗ trợ phân trang và lọc theo nhà máy, trạng thái).
- **`POST /api/v1/documents/`**: Upload tài liệu mới (nhận multipart form file dữ liệu).
- **`GET /api/v1/documents/<id>/`**: Chi tiết thông tin xử lý của tài liệu.
- **`DELETE /api/v1/documents/<id>/`**: Xóa tài liệu và toàn bộ chunks liên quan.
- **`POST /api/v1/documents/<id>/reprocess/`**: Kích hoạt xử lý lại tài liệu (khi cần cập nhật lại chỉ mục).
- **`POST /api/v1/documents/search/`**: Thực hiện truy vấn tìm kiếm RAG (yêu cầu gửi body dạng `{ "query": "nội dung tìm kiếm", "factory": "songhinh", "limit": 5 }`).
- **`GET /api/v1/documents/<id>/view/`**: Trả về trực tiếp file tài liệu vật lý để preview. Hỗ trợ xác thực qua token JWT trên URL Query hoặc Header `Authorization`, giúp bảo mật file PDF không bị truy cập trái phép.

---

## 6. Phân quyền và Bảo mật (`permissions.py`)

- Lớp phân quyền **`CanUseAiDocuments`** chặn toàn bộ các API nếu người dùng không được cấu hình quyền `can_use_ai_documents` (hoặc không phải là `superuser`).
- Trong hàm `filter_documents_for_user`, danh sách tài liệu trả về cho mỗi user được lọc nghiêm ngặt dựa theo Scope quản lý nhà máy của họ:
  - User có quyền Sông Hinh được xem tài liệu của: Sông Hinh, Thượng Kon Tum và tài liệu Chung.
  - User có quyền Vĩnh Sơn được xem tài liệu của: Vĩnh Sơn và tài liệu Chung.
  - User không có Scope cụ thể chỉ được xem tài liệu Chung (`general`).
