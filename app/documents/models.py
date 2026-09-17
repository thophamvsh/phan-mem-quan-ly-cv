import hashlib
import os
import zipfile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import magic
from pgvector.django import VectorField


ALLOWED_MODULE_GUIDE_MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "application/octet-stream",
    },
}


def inspect_module_guide_file(file_obj):
    """Validate a guide file fail-closed and return MIME, SHA-256 and size."""
    max_size = 50 * 1024 * 1024
    try:
        file_size = file_obj.size
        if file_size <= 0:
            raise ValidationError("File tải lên bị rỗng (0 bytes).")
        if file_size > max_size:
            raise ValidationError("Dung lượng file không được vượt quá 50 MB.")

        extension = os.path.splitext(file_obj.name or "")[1].lower()
        if extension not in ALLOWED_MODULE_GUIDE_MIME_TYPES:
            raise ValidationError("Hệ thống chỉ chấp nhận file .pdf hoặc .docx.")

        file_obj.seek(0)
        header = file_obj.read(2048)
        file_obj.seek(0)
        if extension == ".pdf":
            if not header.startswith(b"%PDF"):
                raise ValidationError("Nội dung file không phải định dạng PDF hợp lệ.")
            detected_mime = magic.from_buffer(header, mime=True)
        else:
            if not header.startswith(b"PK\x03\x04"):
                raise ValidationError("Nội dung file không phải định dạng DOCX hợp lệ.")
            detected_mime = magic.from_buffer(header, mime=True)
            try:
                with zipfile.ZipFile(file_obj) as archive:
                    names = set(archive.namelist())
                    required = {"[Content_Types].xml", "word/document.xml"}
                    if not required.issubset(names):
                        raise ValidationError("Cấu trúc DOCX không hợp lệ.")
            except zipfile.BadZipFile as exc:
                raise ValidationError("Tập tin DOCX bị hỏng.") from exc
            finally:
                file_obj.seek(0)

        if detected_mime not in ALLOWED_MODULE_GUIDE_MIME_TYPES[extension]:
            raise ValidationError(
                f"MIME type '{detected_mime}' không phù hợp với file {extension}."
            )

        digest = hashlib.sha256()
        if hasattr(file_obj, "chunks"):
            for chunk in file_obj.chunks():
                digest.update(chunk)
        else:
            digest.update(file_obj.read())
        file_obj.seek(0)
        return detected_mime, digest.hexdigest(), file_size
    except ValidationError:
        raise
    except Exception as exc:
        try:
            file_obj.seek(0)
        except Exception:
            pass
        raise ValidationError(f"Không thể xác thực file tải lên: {exc}") from exc


def validate_module_guide_file(file_obj):
    inspect_module_guide_file(file_obj)


class DocumentFolder(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            if not self.slug:
                import uuid
                self.slug = uuid.uuid4().hex[:8]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Document(models.Model):
    STATUS_UPLOADED = "uploaded"
    STATUS_PROCESSING = "processing"
    STATUS_READY = "ready"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_UPLOADED, "Uploaded"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_READY, "Ready"),
        (STATUS_FAILED, "Failed"),
    )

    FACTORY_GENERAL = "general"
    FACTORY_SONGHINH = "songhinh"
    FACTORY_VINHSON = "vinhson"
    FACTORY_THUONGKONTUM = "thuongkontum"
    FACTORY_TCKT = "tckt"
    FACTORY_KHDT = "khdt"
    FACTORY_TH = "th"
    FACTORY_KT = "kt"
    FACTORY_CHOICES = (
        (FACTORY_GENERAL, "Chung"),
        (FACTORY_SONGHINH, "Song Hinh"),
        (FACTORY_VINHSON, "Vinh Son"),
        (FACTORY_THUONGKONTUM, "Thuong Kon Tum"),
        (FACTORY_TCKT, "Phong TCKT"),
        (FACTORY_KHDT, "Phong KHDT"),
        (FACTORY_TH, "Phong TH"),
        (FACTORY_KT, "Phong KT"),
    )

    title = models.CharField(max_length=255)
    original_file = models.FileField(upload_to="ai_documents/%Y/%m/")
    markdown_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UPLOADED)
    document_type = models.CharField(max_length=80, blank=True, default="")
    factory = models.CharField(max_length=40, choices=FACTORY_CHOICES, default=FACTORY_GENERAL)
    visibility = models.CharField(max_length=30, default="internal")
    folders = models.ManyToManyField(DocumentFolder, related_name="documents", blank=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_documents",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    module_guide = models.OneToOneField(
        "ModuleGuide",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="rag_document",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "-id")
        indexes = [
            models.Index(fields=("status", "factory")),
            models.Index(fields=("document_type", "factory")),
            models.Index(fields=("created_at",)),
        ]

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, related_name="chunks", on_delete=models.CASCADE)
    chunk_index = models.PositiveIntegerField()
    heading_path = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    page_from = models.PositiveIntegerField(null=True, blank=True)
    page_to = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("document_id", "chunk_index")
        unique_together = (("document", "chunk_index"),)
        indexes = [
            models.Index(fields=("document", "chunk_index")),
            models.Index(fields=("token_count",)),
        ]

    def __str__(self):
        return f"{self.document_id}#{self.chunk_index}"


class ModuleGuide(models.Model):
    MODULE_CHOICES = (
        ("so_giao_nhan_ca_vh", "Sổ giao nhận ca vận hành"),
        ("so_giao_nhan_ca_hc", "Sổ giao nhận ca hành chính"),
        ("so_chuyen_doi_tuan", "Sổ chuyển đổi thiết bị tuần"),
        ("so_chuyen_doi_thang", "Sổ chuyển đổi thiết bị đầu tháng"),
        ("so_an_toan_dau_gio", "Sổ theo dõi an toàn đầu giờ"),
        ("so_bchc_song_hinh", "Sổ báo cáo hồ chứa Sông Hinh"),
        ("so_nhat_ky_diesel", "Sổ nhật ký vận hành Diesel"),
        ("so_nhat_ky_van_hanh", "Sổ nhật ký vận hành chung"),
        ("nhat_ky_su_kien", "Nhật ký sự kiện"),
        ("quan_ly_thiet_bi", "Quản lý thiết bị"),
        ("thong_so_van_hanh", "Thông số vận hành"),
    )
    KIND_CHOICES = (
        ("procedure", "Quy trình tiêu chuẩn (SOP)"),
        ("instruction", "Hướng dẫn thao tác"),
        ("form", "Biểu mẫu / Bảng kiểm"),
        ("drawing", "Bản vẽ / Sơ đồ nguyên lý"),
    )
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = (
        (STATUS_DRAFT, "Dự thảo / Nháp"),
        (STATUS_PUBLISHED, "Đang áp dụng"),
        (STATUS_RETIRED, "Đã thu hồi / Lưu trữ"),
    )

    module_code = models.CharField(max_length=50, choices=MODULE_CHOICES, db_index=True)
    nha_may = models.ForeignKey(
        "tochuc.NhaMay",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="module_guides",
    )
    title = models.CharField(max_length=255, verbose_name="Tên quy trình / hướng dẫn")
    document_kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="procedure")
    is_primary = models.BooleanField(default=False, db_index=True)
    order = models.PositiveIntegerField(default=0)
    version_label = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    quick_guide = models.TextField(blank=True)
    file = models.FileField(
        upload_to="module_guides/%Y/%m/", validators=[validate_module_guide_file]
    )
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, default="application/pdf")
    file_size = models.BigIntegerField(default=0)
    checksum = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_module_guides"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_module_guides",
    )
    published_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retired_module_guides",
    )
    retired_at = models.DateTimeField(null=True, blank=True)
    retire_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vanhanh_module_guide"
        ordering = ("-is_primary", "order", "-published_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("module_code", "nha_may"),
                condition=models.Q(status="published", is_primary=True, nha_may__isnull=False),
                name="unique_published_plant_primary_guide",
            ),
            models.UniqueConstraint(
                fields=("module_code",),
                condition=models.Q(status="published", is_primary=True, nha_may__isnull=True),
                name="unique_published_global_primary_guide",
            ),
            models.UniqueConstraint(
                fields=("module_code", "nha_may", "document_kind", "order"),
                condition=models.Q(status="published", is_primary=False, nha_may__isnull=False),
                name="unique_published_plant_supp_guide",
            ),
            models.UniqueConstraint(
                fields=("module_code", "document_kind", "order"),
                condition=models.Q(status="published", is_primary=False, nha_may__isnull=True),
                name="unique_published_global_supp_guide",
            ),
            models.UniqueConstraint(
                fields=("module_code", "nha_may", "is_primary", "document_kind", "order", "version_label"),
                condition=models.Q(nha_may__isnull=False),
                name="unique_plant_module_guide_version",
            ),
            models.UniqueConstraint(
                fields=("module_code", "is_primary", "document_kind", "order", "version_label"),
                condition=models.Q(nha_may__isnull=True),
                name="unique_global_module_guide_version",
            ),
        ]

    def __str__(self):
        return f"{self.get_module_code_display()} - {self.title} ({self.version_label})"

    @property
    def is_expired(self):
        return bool(
            self.status == self.STATUS_PUBLISHED
            and self.effective_to
            and self.effective_to < timezone.localdate()
        )

    def clean(self):
        super().clean()
        if self.effective_from and self.effective_to and self.effective_from > self.effective_to:
            raise ValidationError("Ngày bắt đầu hiệu lực không được lớn hơn ngày hết hiệu lực.")
        if self.status == self.STATUS_PUBLISHED and self.effective_to:
            if self.effective_to < timezone.localdate():
                raise ValidationError("Không thể phát hành tài liệu đã hết hiệu lực.")

    def save(self, *args, **kwargs):
        if self.file:
            is_new_file = not self.pk or not getattr(self.file, "_committed", True)
            if is_new_file or not self.checksum:
                self.original_filename = os.path.basename(self.file.name)
                self.mime_type, self.checksum, self.file_size = inspect_module_guide_file(self.file)
        self.full_clean()
        return super().save(*args, **kwargs)
