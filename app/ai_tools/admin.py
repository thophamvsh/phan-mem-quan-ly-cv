from django.contrib import admin

from .models import AiConversationMessage


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
