import re
import unicodedata

from rest_framework import permissions


AI_TOOL_SCOPE_WATER = "water"
AI_TOOL_SCOPE_SONGHINH = "songhinh"
AI_TOOL_SCOPE_VINHSON = "vinhson"
ALL_AI_TOOL_SCOPES = frozenset(
    {AI_TOOL_SCOPE_WATER, AI_TOOL_SCOPE_SONGHINH, AI_TOOL_SCOPE_VINHSON}
)
AI_TOOL_SCOPE_DENIAL_MESSAGES = {
    AI_TOOL_SCOPE_SONGHINH: "Xin lỗi! Bạn không được quyền hỏi thông tin nhà máy Sông Hinh, xin bạn hãy hỏi nhà máy của mình.",
    AI_TOOL_SCOPE_VINHSON: "Xin lỗi! Bạn không được quyền hỏi thông tin nhà máy Vĩnh Sơn, xin bạn hãy hỏi nhà máy của mình.",
}


def has_ai_tools_permission(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(getattr(profile, "can_use_ai_tools", False))


class CanUseAiTools(permissions.BasePermission):
    message = "Ban khong co quyen su dung tro ly AI."

    def has_permission(self, request, view):
        return has_ai_tools_permission(request.user)


def _normalize_factory_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.strip().lower()


def _has_keyword(text, keywords):
    return any(re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) for keyword in keywords)


def get_ai_tool_scopes_for_user(user):
    if not user or not user.is_authenticated:
        return frozenset()
    if user.is_superuser:
        return ALL_AI_TOOL_SCOPES

    profile = getattr(user, "profile", None)
    if not profile:
        return frozenset()
    if getattr(profile, "is_all_factories", False):
        return ALL_AI_TOOL_SCOPES

    factory = getattr(profile, "nha_may", None)
    if not factory:
        return frozenset({AI_TOOL_SCOPE_WATER})

    factory_text = " ".join(
        [
            _normalize_factory_text(getattr(factory, "ma_nha_may", "")),
            _normalize_factory_text(getattr(factory, "ten_nha_may", "")),
        ]
    )
    scopes = {AI_TOOL_SCOPE_WATER}
    if any(keyword in factory_text for keyword in ("sh", "song hinh", "songhinh", "tkt", "thuong kon tum", "kon tum")):
        scopes.add(AI_TOOL_SCOPE_SONGHINH)
    if any(keyword in factory_text for keyword in ("vs", "vinh son", "vinhson")):
        scopes.add(AI_TOOL_SCOPE_VINHSON)
    return frozenset(scopes)


def get_ai_tool_scope(tool_name):
    normalized = _normalize_factory_text(tool_name)
    if normalized in {"analyze_hydro_data", "compare_hydro_periods"}:
        return AI_TOOL_SCOPE_WATER
    if "songhinh" in normalized or "songinh" in normalized:
        return AI_TOOL_SCOPE_SONGHINH
    if "vinhson" in normalized:
        return AI_TOOL_SCOPE_VINHSON
    return AI_TOOL_SCOPE_WATER


def get_requested_ai_tool_scope_from_text(text):
    normalized = _normalize_factory_text(text)
    if _has_keyword(normalized, ("vinh son", "vinhson", "vs", "vsa", "vsb", "vsc")):
        return AI_TOOL_SCOPE_VINHSON
    if _has_keyword(normalized, ("song hinh", "songhinh", "songinh", "sh", "thuong kon tum", "kon tum", "kontum", "tkt")):
        return AI_TOOL_SCOPE_SONGHINH
    return None


def get_ai_tool_scope_denial_message(user, text):
    requested_scope = get_requested_ai_tool_scope_from_text(text)
    if not requested_scope:
        return ""
    if requested_scope in get_ai_tool_scopes_for_user(user):
        return ""
    return AI_TOOL_SCOPE_DENIAL_MESSAGES.get(
        requested_scope,
        "Xin lỗi! Bạn không được quyền hỏi thông tin nhà máy này, xin bạn hãy hỏi nhà máy của mình.",
    )


def can_user_use_ai_tool(user, tool_name):
    return get_ai_tool_scope(tool_name) in get_ai_tool_scopes_for_user(user)


def filter_ai_tools_for_user(user, tools):
    allowed_scopes = get_ai_tool_scopes_for_user(user)
    filtered = []
    for tool in tools:
        function = tool.get("function", {})
        if get_ai_tool_scope(function.get("name", "")) in allowed_scopes:
            filtered.append(tool)
    return filtered
