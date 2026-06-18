from django.conf import settings
from django.db import models
from django.utils.text import slugify
from pgvector.django import VectorField


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
