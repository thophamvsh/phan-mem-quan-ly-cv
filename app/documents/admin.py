from django.contrib import admin

from documents.models import Document, DocumentChunk, ModuleGuide


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0
    readonly_fields = ("chunk_index", "heading_path", "token_count", "created_at")
    fields = ("chunk_index", "heading_path", "token_count", "created_at")
    can_delete = False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "factory",
        "document_type",
        "status",
        "is_active",
        "module_guide",
        "version",
        "updated_at",
    )
    list_filter = ("status", "is_active", "factory", "document_type")
    search_fields = ("title", "markdown_text")
    readonly_fields = ("processed_at", "created_at", "updated_at", "error_message")
    inlines = (DocumentChunkInline,)


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "heading_path", "token_count", "created_at")
    list_filter = ("document__factory",)
    search_fields = ("document__title", "heading_path", "content")


@admin.register(ModuleGuide)
class ModuleGuideAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "module_code",
        "nha_may",
        "version_label",
        "status",
        "is_primary",
        "updated_at",
    )
    list_filter = ("status", "module_code", "nha_may", "document_kind", "is_primary")
    search_fields = ("title", "version_label", "original_filename", "checksum")
    readonly_fields = (
        "status",
        "original_filename",
        "mime_type",
        "file_size",
        "checksum",
        "approved_by",
        "published_at",
        "retired_by",
        "retired_at",
        "created_at",
        "updated_at",
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != ModuleGuide.STATUS_DRAFT:
            return False
        return super().has_delete_permission(request, obj)
