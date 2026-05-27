from django.db.models import Max, OuterRef, Subquery

from .models import AiConversationMessage


def get_conversation(user, session_id, limit=20):
    queryset = (
        AiConversationMessage.objects.filter(user=user, session_id=session_id)
        .order_by("-created_at", "-id")[:limit]
    )
    rows = reversed(list(queryset))
    return [{"role": row.role, "content": row.content} for row in rows]


def save_exchange(
    *,
    user,
    session_id,
    user_message,
    assistant_message,
    model="",
    total_tokens=0,
    cost_usd=0,
    tools_called=0,
    latency_ms=0,
    meta=None,
):
    AiConversationMessage.objects.create(
        user=user,
        session_id=session_id,
        role=AiConversationMessage.ROLE_USER,
        content=user_message,
        model=model,
        meta=meta or {},
    )
    AiConversationMessage.objects.create(
        user=user,
        session_id=session_id,
        role=AiConversationMessage.ROLE_ASSISTANT,
        content=assistant_message,
        model=model,
        total_tokens=total_tokens or 0,
        cost_usd=cost_usd or 0,
        tools_called=tools_called or 0,
        latency_ms=int(latency_ms or 0),
        meta=meta or {},
    )


def get_sessions(user, limit=50):
    first_user_message = (
        AiConversationMessage.objects.filter(
            user=user,
            session_id=OuterRef("session_id"),
            role=AiConversationMessage.ROLE_USER,
        )
        .order_by("created_at", "id")
        .values("content")[:1]
    )
    last_message = (
        AiConversationMessage.objects.filter(
            user=user,
            session_id=OuterRef("session_id"),
        )
        .order_by("-created_at", "-id")
    )
    rows = (
        AiConversationMessage.objects.filter(user=user)
        .values("session_id")
        .annotate(
            updated_at=Max("created_at"),
            title=Subquery(first_user_message),
            last_message=Subquery(last_message.values("content")[:1]),
            last_role=Subquery(last_message.values("role")[:1]),
        )
        .order_by("-updated_at")[:limit]
    )
    return [
        {
            "session_id": row["session_id"],
            "title": row["title"] or row["last_message"],
            "content": row["title"],
            "last_message": row["last_message"],
            "last_role": row["last_role"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def delete_session(user, session_id):
    deleted, _ = AiConversationMessage.objects.filter(
        user=user,
        session_id=session_id,
    ).delete()
    return deleted
