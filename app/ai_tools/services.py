import copy
import json
import logging
import os
import time
import unicodedata
import uuid
from types import SimpleNamespace

from django.conf import settings

from .permissions import (
    can_user_use_ai_tool,
    filter_ai_tools_for_user,
    get_ai_tool_scope_denial_message,
)
from .storage import get_conversation, save_exchange
from .tool_format import sanitize_tool_content


logger = logging.getLogger(__name__)
SONGHINH_KEYWORDS = ("song hinh", "songhinh", "sh", "thuong kon tum", "kontum")
VINHSON_KEYWORDS = ("vinh son", "vinhson", "vs", "vsa", "vsb", "vsc")
DEFAULT_PROVIDER = getattr(settings, "AI_TOOLS_PROVIDER", "openai")
DEFAULT_OPENAI_MODEL = getattr(settings, "AI_TOOLS_OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_ANTHROPIC_MODEL = getattr(settings, "AI_TOOLS_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
OPENAI_MODELS = tuple(getattr(settings, "AI_TOOLS_OPENAI_MODELS", (DEFAULT_OPENAI_MODEL, "gpt-4o-mini", "gpt-4o")))
ANTHROPIC_MODELS = tuple(
    getattr(
        settings,
        "AI_TOOLS_ANTHROPIC_MODELS",
        (
            DEFAULT_ANTHROPIC_MODEL,
            "claude-opus-4-1-20250805",
            "claude-3-7-sonnet-20250219",
        ),
    )
)

SYSTEM_PROMPT = """Ban la Nami, tro ly AI cho Bang dieu khien van hanh thuy dien.
Ban ho tro tra cuu muc nuoc, dung tich, luu luong, du lieu van hanh va phan tich.
Tra loi ngan gon, ro rang, chuyen nghiep bang tieng Viet.
Khong neu ten he thong luu tru hoac nguon ky thuat noi bo nhu Supabase, Google Sheets, spreadsheet, worksheet."""


class AiToolsError(Exception):
    pass


def _normalize_text(value):
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def _tool_name(tool_call):
    return getattr(getattr(tool_call, "function", None), "name", "") or ""


def _tool_arguments(tool_call):
    raw = getattr(getattr(tool_call, "function", None), "arguments", "") or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _dedupe_tool_calls(tool_calls):
    unique = []
    seen = set()
    for tool_call in tool_calls:
        key = (_tool_name(tool_call), json.dumps(_tool_arguments(tool_call), sort_keys=True, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        unique.append(tool_call)
    return unique


def _select_single_songhinh_rainfall_call(user_text, tool_calls):
    normalized = _normalize_text(user_text)
    if "song hinh" not in normalized and "songhinh" not in normalized and "sh" not in normalized:
        return None
    if "mua" not in normalized and "rain" not in normalized:
        return None

    rainfall_calls = [
        tool_call
        for tool_call in tool_calls
        if _tool_name(tool_call).startswith("get_songhinh_rainfall_")
    ]
    if not rainfall_calls:
        return None
    if len(rainfall_calls) == 1:
        return rainfall_calls[0]

    def score(tool_call):
        name = _tool_name(tool_call)
        args = _tool_arguments(tool_call)
        if name == "get_songhinh_rainfall_statistics":
            period_type = args.get("period_type")
            if period_type == "year" and ("nam" in normalized or "year" in normalized):
                return 100
            if period_type == "month" and "thang" in normalized:
                return 95
            if period_type == "week" and "tuan" in normalized:
                return 90
            return 80
        if name == "get_songhinh_rainfall_daily_statistics":
            if "tu ngay" in normalized or "den ngay" in normalized:
                return 75
            return 30
        if name == "get_songhinh_rainfall_range_statistics":
            if "tu thang" in normalized or "den thang" in normalized:
                return 70
            return 25
        return 0

    return max(rainfall_calls, key=score)


def _select_single_vinhson_rainfall_call(user_text, tool_calls):
    normalized = _normalize_text(user_text)
    if "vinh son" not in normalized and "vinhson" not in normalized and "vs" not in normalized:
        return None
    if "mua" not in normalized and "rain" not in normalized:
        return None

    rainfall_calls = [
        tool_call
        for tool_call in tool_calls
        if _tool_name(tool_call).startswith("get_vinhson_rainfall_")
    ]
    if not rainfall_calls:
        return None
    if len(rainfall_calls) == 1:
        return rainfall_calls[0]

    def score(tool_call):
        name = _tool_name(tool_call)
        args = _tool_arguments(tool_call)
        if name == "get_vinhson_rainfall_statistics":
            period_type = args.get("period_type")
            if period_type == "year" and ("nam" in normalized or "year" in normalized):
                return 100
            if period_type == "month" and "thang" in normalized:
                return 95
            if period_type == "week" and "tuan" in normalized:
                return 90
            return 80
        if name == "get_vinhson_rainfall_daily_statistics":
            if "tu ngay" in normalized or "den ngay" in normalized:
                return 75
            return 30
        if name == "get_vinhson_rainfall_range_statistics":
            if "tu thang" in normalized or "den thang" in normalized:
                return 70
            return 25
        return 0

    return max(rainfall_calls, key=score)


def _filter_tool_calls(user_text, tool_calls):
    calls = _dedupe_tool_calls(list(tool_calls or []))
    selected_sh_rainfall = _select_single_songhinh_rainfall_call(user_text, calls)
    selected_vs_rainfall = _select_single_vinhson_rainfall_call(user_text, calls)

    normalized = _normalize_text(user_text)
    needs_non_rainfall_data = any(
        keyword in normalized
        for keyword in ("qve", "luu luong", "muc nuoc", "mnh", "san luong")
    )

    filtered = []
    for call in calls:
        name = _tool_name(call)
        if name.startswith("get_songhinh_rainfall_"):
            if selected_sh_rainfall:
                if call == selected_sh_rainfall:
                    filtered.append(call)
            else:
                filtered.append(call)
        elif name.startswith("get_vinhson_rainfall_"):
            if selected_vs_rainfall:
                if call == selected_vs_rainfall:
                    filtered.append(call)
            else:
                filtered.append(call)
        else:
            # Non-rainfall call
            is_sh_call = "songhinh" in name or "songinh" in name
            is_vs_call = "vinhson" in name or "vinh_son" in name

            if needs_non_rainfall_data:
                filtered.append(call)
            else:
                if is_sh_call and selected_sh_rainfall:
                    continue
                if is_vs_call and selected_vs_rainfall:
                    continue
                filtered.append(call)

    return filtered


def _lazy_import_tools():
    from ai_tools.water_tools.tooldefs.schemas import TOOLS
    from ai_tools.water_tools.runtime.handler import handle_water_tool_call, handle_tool_calls
    from ai_tools.songhinh_tools import SONGHINH_TOOLS, handle_songhinh_tool_calls
    from ai_tools.vinhson_tools import VINHSON_TOOLS, handle_vinhson_tool_calls
    from ai_tools.analysis_tools import ANALYSIS_TOOLS, handle_analysis_tool_call

    return (
        TOOLS,
        handle_water_tool_call,
        handle_tool_calls,
        SONGHINH_TOOLS,
        handle_songhinh_tool_calls,
        VINHSON_TOOLS,
        handle_vinhson_tool_calls,
        ANALYSIS_TOOLS,
        handle_analysis_tool_call,
    )


def _resolve_model(provider, model):
    provider = (provider or DEFAULT_PROVIDER or "openai").lower()
    if provider not in {"openai", "anthropic"}:
        raise AiToolsError(f"Nha cung cap AI khong ho tro: {provider}")

    allowed = OPENAI_MODELS if provider == "openai" else ANTHROPIC_MODELS
    default_model = DEFAULT_OPENAI_MODEL if provider == "openai" else DEFAULT_ANTHROPIC_MODEL
    selected_model = (model or default_model).strip()
    if selected_model not in allowed:
        raise AiToolsError(f"Model {selected_model} khong nam trong danh sach duoc phep.")
    return provider, selected_model


def detect_reservoir(message):
    msg_lower = (message or "").lower()
    if any(keyword in msg_lower for keyword in SONGHINH_KEYWORDS):
        return "songhinh"
    if any(keyword in msg_lower for keyword in VINHSON_KEYWORDS):
        return "vinhson"
    return None


def _format_tool_results(tool_results):
    formatted = []
    for result in tool_results:
        if isinstance(result, dict) and "content" in result:
            formatted.append(result["content"])
        elif isinstance(result, str):
            formatted.append(result)
    return sanitize_tool_content("\n\n".join(item for item in formatted if item))


def _agent_tools(tools):
    sanitized = []
    for tool in tools:
        item = copy.deepcopy(tool)
        function = item.get("function", {})
        for field in ("description",):
            if field in function:
                function[field] = sanitize_tool_content(function[field])
        parameters = function.get("parameters") or {}
        function["parameters"] = sanitize_tool_content(parameters)
        sanitized.append(item)
    return sanitized


def _estimate_cost_usd(provider, model, prompt_tokens, completion_tokens):
    if provider == "anthropic":
        if "opus" in model:
            input_rate, output_rate = 15.0, 75.0
        else:
            input_rate, output_rate = 3.0, 15.0
    else:
        input_rate, output_rate = 0.150, 0.600
    return round(
        (prompt_tokens / 1_000_000) * input_rate
        + (completion_tokens / 1_000_000) * output_rate,
        6,
    )


def _get_tools_and_handlers(user=None):
    (
        WATER_TOOLS,
        handle_water_tool_call,
        handle_water_tool_calls,
        SONGHINH_TOOLS,
        handle_songhinh_tool_calls,
        VINHSON_TOOLS,
        handle_vinhson_tool_calls,
        ANALYSIS_TOOLS,
        handle_analysis_tool_call,
    ) = _lazy_import_tools()
    all_tools = WATER_TOOLS + SONGHINH_TOOLS + VINHSON_TOOLS + ANALYSIS_TOOLS
    if user is not None:
        all_tools = filter_ai_tools_for_user(user, all_tools)
    return (
        all_tools,
        handle_water_tool_call,
        handle_water_tool_calls,
        handle_songhinh_tool_calls,
        handle_vinhson_tool_calls,
        handle_analysis_tool_call,
    )


def _ensure_tool_allowed(user, tool_name):
    if not can_user_use_ai_tool(user, tool_name):
        raise AiToolsError("Ban khong co quyen su dung du lieu nha may nay.")


def _handle_single_tool_call(user, tool_call, handle_water_tool_call, handle_songhinh_tool_calls, handle_vinhson_tool_calls, handle_analysis_tool_call):
    tool_name = tool_call.function.name
    _ensure_tool_allowed(user, tool_name)
    if "songhinh" in tool_name.lower() or "songinh" in tool_name.lower():
        return handle_songhinh_tool_calls(tool_call)
    if "vinhson" in tool_name.lower():
        return handle_vinhson_tool_calls(tool_call)
    if tool_name.lower() in {"analyze_hydro_data", "compare_hydro_periods"}:
        return handle_analysis_tool_call(tool_call)
    return handle_water_tool_call(tool_call)


def _run_openai_chat(*, user, content, session_id, model):
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise AiToolsError("Backend chua cau hinh OPENAI_API_KEY.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AiToolsError("Backend chua cai goi openai. Hay them openai vao requirements va cai lai moi truong.") from exc

    (
        all_tools,
        handle_water_tool_call,
        handle_water_tool_calls,
        handle_songhinh_tool_calls,
        handle_vinhson_tool_calls,
        handle_analysis_tool_call,
    ) = _get_tools_and_handlers(user)

    client = OpenAI(api_key=api_key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(content["history"])
    messages.append({"role": "user", "content": content["text"]})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[{"type": "function", "function": tool["function"]} for tool in _agent_tools(all_tools)],
        tool_choice="auto",
        parallel_tool_calls=False,
        temperature=0.4,
        max_tokens=4096,
    )

    assistant_message = response.choices[0].message.content or ""
    tools_called = 0

    if response.choices[0].message.tool_calls:
        message = response.choices[0].message
        tool_calls = _filter_tool_calls(content["text"], message.tool_calls)
        tools_called = len(tool_calls)
        tool_results = []

        for tool_call in tool_calls:
            try:
                _ensure_tool_allowed(user, tool_call.function.name)
                if "songhinh" in tool_call.function.name.lower() or "songinh" in tool_call.function.name.lower():
                    tool_results.append(handle_songhinh_tool_calls(tool_call))
                elif "vinhson" in tool_call.function.name.lower():
                    tool_results.append(handle_vinhson_tool_calls(tool_call))
                elif tool_call.function.name.lower() in {"analyze_hydro_data", "compare_hydro_periods"}:
                    tool_results.append(handle_analysis_tool_call(tool_call))
                else:
                    tool_results.append(handle_water_tool_call(tool_call))
            except Exception as exc:
                logger.exception("AI tool execution failed: %s", tool_call.function.name)
                tool_results.append(f"Loi khi chay tool {tool_call.function.name}: {exc}")

        assistant_message = _format_tool_results(tool_results) or assistant_message

    usage = response.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
    return assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens


def _anthropic_tools(openai_tools):
    tools = []
    for tool in _agent_tools(openai_tools):
        function = tool.get("function", {})
        tools.append(
            {
                "name": function.get("name"),
                "description": function.get("description", ""),
                "input_schema": function.get("parameters") or {"type": "object"},
            }
        )
    return tools


def _anthropic_text(message):
    parts = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", "") == "text":
            parts.append(getattr(block, "text", ""))
    return "\n".join(part for part in parts if part)


def _anthropic_content_blocks(message):
    blocks = []
    for block in getattr(message, "content", []) or []:
        block_type = getattr(block, "type", "")
        if block_type == "text":
            blocks.append({"type": "text", "text": getattr(block, "text", "")})
        elif block_type == "tool_use":
            blocks.append(
                {
                    "type": "tool_use",
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": getattr(block, "input", {}) or {},
                }
            )
    return blocks


def _run_anthropic_chat(*, user, content, session_id, model):
    api_key = os.getenv("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", None)
    if not api_key:
        raise AiToolsError("Backend chua cau hinh ANTHROPIC_API_KEY.")

    try:
        import anthropic
    except ImportError as exc:
        raise AiToolsError("Backend chua cai goi anthropic. Hay them anthropic vao requirements va cai lai moi truong.") from exc

    (
        all_tools,
        handle_water_tool_call,
        _handle_water_tool_calls,
        handle_songhinh_tool_calls,
        handle_vinhson_tool_calls,
        handle_analysis_tool_call,
    ) = _get_tools_and_handlers(user)

    client = anthropic.Anthropic(api_key=api_key)
    messages = list(content["history"])
    messages.append({"role": "user", "content": content["text"]})

    response = client.messages.create(
        model=model,
        system=SYSTEM_PROMPT,
        messages=messages,
        max_tokens=4096,
        temperature=0.4,
        tools=_anthropic_tools(all_tools),
    )

    tool_uses = [
        block
        for block in getattr(response, "content", []) or []
        if getattr(block, "type", "") == "tool_use"
    ]
    tool_calls = []
    for tool_use in tool_uses:
        arguments = json.dumps(getattr(tool_use, "input", {}) or {}, ensure_ascii=False)
        tool_calls.append(
            SimpleNamespace(
                id=getattr(tool_use, "id", ""),
                function=SimpleNamespace(name=getattr(tool_use, "name", ""), arguments=arguments),
            )
        )

    tool_calls = _filter_tool_calls(content["text"], tool_calls)
    tool_results = []
    tool_result_by_id = {}
    for tool_call in tool_calls:
        try:
            result = _handle_single_tool_call(
                user,
                tool_call,
                handle_water_tool_call,
                handle_songhinh_tool_calls,
                handle_vinhson_tool_calls,
                handle_analysis_tool_call,
            )
            tool_results.append(result)
            tool_result_by_id[tool_call.id] = result["content"] if isinstance(result, dict) else str(result)
        except Exception as exc:
            logger.exception("AI tool execution failed: %s", tool_call.function.name)
            result = f"Loi khi chay tool {tool_call.function.name}: {exc}"
            tool_results.append(result)
            tool_result_by_id[tool_call.id] = result

    assistant_message = _format_tool_results(tool_results) if tool_results else _anthropic_text(response)

    usage = response.usage
    prompt_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "output_tokens", 0) if usage else 0
    total_tokens = prompt_tokens + completion_tokens
    return assistant_message, len(tool_calls), prompt_tokens, completion_tokens, total_tokens


def run_ai_chat(*, user, content, session_id=None, provider="openai", model=""):
    if not content or not content.strip():
        raise AiToolsError("Noi dung cau hoi khong duoc de trong.")

    provider, selected_model = _resolve_model(provider, model)
    session_id = session_id or str(uuid.uuid4())
    start_time = time.time()

    denial_message = get_ai_tool_scope_denial_message(user, content)
    if denial_message:
        latency_ms = int((time.time() - start_time) * 1000)
        save_exchange(
            user=user,
            session_id=session_id,
            user_message=content,
            assistant_message=denial_message,
            model=selected_model,
            total_tokens=0,
            cost_usd=0,
            tools_called=0,
            latency_ms=latency_ms,
            meta={
                "reservoir_detected": detect_reservoir(content),
                "tools_called": 0,
                "provider": provider,
                "permission_denied": True,
            },
        )
        return {
            "session_id": session_id,
            "response": denial_message,
            "provider": provider,
            "model": selected_model,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": latency_ms,
            "tools_called": 0,
        }

    chat_content = {
        "text": content,
        "history": get_conversation(user, session_id, limit=20),
    }

    if provider == "anthropic":
        assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens = _run_anthropic_chat(
            user=user,
            content=chat_content,
            session_id=session_id,
            model=selected_model,
        )
    else:
        assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens = _run_openai_chat(
            user=user,
            content=chat_content,
            session_id=session_id,
            model=selected_model,
        )

    if not total_tokens:
        total_tokens = prompt_tokens + completion_tokens
    assistant_message = sanitize_tool_content(assistant_message)
    cost_usd = _estimate_cost_usd(provider, selected_model, prompt_tokens, completion_tokens)
    latency_ms = int((time.time() - start_time) * 1000)
    meta = {
        "reservoir_detected": detect_reservoir(content),
        "tools_called": tools_called,
        "provider": provider,
    }

    save_exchange(
        user=user,
        session_id=session_id,
        user_message=content,
        assistant_message=assistant_message,
        model=selected_model,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        tools_called=tools_called,
        latency_ms=latency_ms,
        meta=meta,
    )

    return {
        "session_id": session_id,
        "response": assistant_message,
        "provider": provider,
        "model": selected_model,
        "total_tokens": total_tokens,
        "cost_usd": float(cost_usd),
        "latency_ms": latency_ms,
        "tools_called": tools_called,
    }
