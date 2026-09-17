from django.conf import settings
from django.db import models


class AiConversationMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = (
        (ROLE_USER, "Nguoi dung"),
        (ROLE_ASSISTANT, "Tro ly"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_conversation_messages",
    )
    session_id = models.CharField(max_length=100, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    model = models.CharField(max_length=100, blank=True, default="")
    total_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    tools_called = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Tin nhan tro ly AI"
        verbose_name_plural = "Tin nhan tro ly AI"
        indexes = [
            models.Index(fields=["user", "session_id", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user} {self.session_id} {self.role}"


class AuditAiQuery(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audited_ai_queries",
    )
    query = models.TextField()
    answer = models.TextField(blank=True)
    module_code = models.CharField(max_length=50, blank=True, db_index=True)
    document_ids = models.JSONField(default=list, blank=True)
    guide_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "Nhật ký truy vấn AI tài liệu"
        verbose_name_plural = "Nhật ký truy vấn AI tài liệu"

    def __str__(self):
        return f"{self.user_id or '-'} - {self.module_code or 'all'} - {self.created_at}"
