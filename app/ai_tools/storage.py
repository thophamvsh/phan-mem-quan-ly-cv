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
    rows = (
        AiConversationMessage.objects.filter(user=user)
        .order_by("-created_at")
        .values("session_id", "role", "content", "created_at")
    )
    sessions = []
    seen = set()
    for row in rows:
        session_id = row["session_id"]
        if session_id in seen:
            continue
        seen.add(session_id)
        sessions.append(
            {
                "session_id": session_id,
                "last_message": row["content"],
                "last_role": row["role"],
                "updated_at": row["created_at"],
            }
        )
        if len(sessions) >= limit:
            break
    return sessions


def delete_session(user, session_id):
    deleted, _ = AiConversationMessage.objects.filter(
        user=user,
        session_id=session_id,
    ).delete()
    return deleted
