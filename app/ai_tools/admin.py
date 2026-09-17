from django.contrib import admin

from .models import AiConversationMessage, AuditAiQuery


@admin.register(AiConversationMessage)
class AiConversationMessageAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "session_id",
        "role",
        "model",
        "total_tokens",
        "tools_called",
        "latency_ms",
        "created_at",
    )
    list_filter = ("role", "model", "created_at")
    search_fields = ("user__username", "user__email", "session_id", "content")
    readonly_fields = (
        "user",
        "session_id",
        "role",
        "content",
        "model",
        "total_tokens",
        "cost_usd",
        "tools_called",
        "latency_ms",
        "meta",
        "created_at",
    )


@admin.register(AuditAiQuery)
class AuditAiQueryAdmin(admin.ModelAdmin):
    list_display = ("user", "module_code", "created_at")
    list_filter = ("module_code", "created_at")
    search_fields = ("user__username", "user__email", "query", "answer")
    readonly_fields = (
        "user",
        "query",
        "answer",
        "module_code",
        "document_ids",
        "guide_ids",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
