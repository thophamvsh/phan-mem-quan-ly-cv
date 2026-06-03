from django.contrib import admin

from documents.models import Document, DocumentChunk


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0
    readonly_fields = ("chunk_index", "heading_path", "token_count", "created_at")
    fields = ("chunk_index", "heading_path", "token_count", "created_at")
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "factory", "document_type", "status", "version", "updated_at")
    list_filter = ("status", "factory", "document_type")
    search_fields = ("title", "markdown_text")
    readonly_fields = ("processed_at", "created_at", "updated_at", "error_message")
    inlines = (DocumentChunkInline,)


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "heading_path", "token_count", "created_at")
    list_filter = ("document__factory",)
    search_fields = ("document__title", "heading_path", "content")
