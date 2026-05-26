import json
import os
import time
import uuid
from types import SimpleNamespace

from django.conf import settings

from .storage import get_conversation, save_exchange


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
Tra loi ngan gon, ro rang, chuyen nghiep bang tieng Viet."""


class AiToolsError(Exception):
    pass


def _lazy_import_tools():
    from ai_tools.water_tools.tooldefs.schemas import TOOLS
    from ai_tools.water_tools.runtime.handler import handle_water_tool_call, handle_tool_calls
    from ai_tools.songhinh_tools import SONGHINH_TOOLS, handle_songhinh_tool_calls
    from ai_tools.vinhson_tools import VINHSON_TOOLS, handle_vinhson_tool_calls

    return TOOLS, handle_water_tool_call, handle_tool_calls, SONGHINH_TOOLS, handle_songhinh_tool_calls, VINHSON_TOOLS, handle_vinhson_tool_calls


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
    return "\n\n".join(item for item in formatted if item)


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


def _get_tools_and_handlers():
    (
        WATER_TOOLS,
        handle_water_tool_call,
        handle_water_tool_calls,
        SONGHINH_TOOLS,
        handle_songhinh_tool_calls,
        VINHSON_TOOLS,
        handle_vinhson_tool_calls,
    ) = _lazy_import_tools()
    all_tools = WATER_TOOLS + SONGHINH_TOOLS + VINHSON_TOOLS
    return (
        all_tools,
        handle_water_tool_call,
        handle_water_tool_calls,
        handle_songhinh_tool_calls,
        handle_vinhson_tool_calls,
    )


def _handle_single_tool_call(tool_call, handle_water_tool_call, handle_songhinh_tool_calls, handle_vinhson_tool_calls):
    tool_name = tool_call.function.name
    if "songhinh" in tool_name.lower() or "songinh" in tool_name.lower():
        return handle_songhinh_tool_calls(tool_call)
    if "vinhson" in tool_name.lower():
        return handle_vinhson_tool_calls(tool_call)
    return handle_water_tool_call(tool_call)


def _run_openai_chat(*, content, session_id, model):
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise AiToolsError("Backend chua cau hinh OPENAI_API_KEY.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AiToolsError("Backend chua cai goi openai. Hay them openai vao requirements va cai lai moi truong.") from exc

    (
        all_tools,
        _handle_water_tool_call,
        handle_water_tool_calls,
        handle_songhinh_tool_calls,
        handle_vinhson_tool_calls,
    ) = _get_tools_and_handlers()

    client = OpenAI(api_key=api_key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(content["history"])
    messages.append({"role": "user", "content": content["text"]})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[{"type": "function", "function": tool["function"]} for tool in all_tools],
        tool_choice="auto",
        temperature=0.4,
        max_tokens=2048,
    )

    assistant_message = response.choices[0].message.content or ""
    tools_called = 0

    if response.choices[0].message.tool_calls:
        message = response.choices[0].message
        tool_calls = list(message.tool_calls or [])
        tools_called = len(tool_calls)
        tool_results = []

        for tool_call in tool_calls:
            try:
                if "songhinh" in tool_call.function.name.lower() or "songinh" in tool_call.function.name.lower():
                    tool_results.append(handle_songhinh_tool_calls(tool_call))
                elif "vinhson" in tool_call.function.name.lower():
                    tool_results.append(handle_vinhson_tool_calls(tool_call))
                else:
                    tool_results.extend(handle_water_tool_calls(message))
                    break
            except Exception as exc:
                tool_results.append(f"Loi khi chay tool {tool_call.function.name}: {exc}")

        assistant_message = _format_tool_results(tool_results) or assistant_message

    usage = response.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
    return assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens


def _anthropic_tools(openai_tools):
    tools = []
    for tool in openai_tools:
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


def _run_anthropic_chat(*, content, session_id, model):
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
    ) = _get_tools_and_handlers()

    client = anthropic.Anthropic(api_key=api_key)
    messages = list(content["history"])
    messages.append({"role": "user", "content": content["text"]})

    response = client.messages.create(
        model=model,
        system=SYSTEM_PROMPT,
        messages=messages,
        max_tokens=2048,
        temperature=0.4,
        tools=_anthropic_tools(all_tools),
    )

    tool_uses = [
        block
        for block in getattr(response, "content", []) or []
        if getattr(block, "type", "") == "tool_use"
    ]
    tool_results = []

    for tool_use in tool_uses:
        arguments = json.dumps(getattr(tool_use, "input", {}) or {}, ensure_ascii=False)
        tool_call = SimpleNamespace(
            id=getattr(tool_use, "id", ""),
            function=SimpleNamespace(name=getattr(tool_use, "name", ""), arguments=arguments),
        )
        try:
            tool_results.append(
                _handle_single_tool_call(
                    tool_call,
                    handle_water_tool_call,
                    handle_songhinh_tool_calls,
                    handle_vinhson_tool_calls,
                )
            )
        except Exception as exc:
            tool_results.append(f"Loi khi chay tool {tool_call.function.name}: {exc}")

    assistant_message = _format_tool_results(tool_results) if tool_results else _anthropic_text(response)

    usage = response.usage
    prompt_tokens = getattr(usage, "input_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "output_tokens", 0) if usage else 0
    total_tokens = prompt_tokens + completion_tokens
    return assistant_message, len(tool_uses), prompt_tokens, completion_tokens, total_tokens


def run_ai_chat(*, user, content, session_id=None, provider="openai", model=""):
    if not content or not content.strip():
        raise AiToolsError("Noi dung cau hoi khong duoc de trong.")

    provider, selected_model = _resolve_model(provider, model)
    session_id = session_id or str(uuid.uuid4())
    start_time = time.time()
    chat_content = {
        "text": content,
        "history": get_conversation(user, session_id, limit=20),
    }

    if provider == "anthropic":
        assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens = _run_anthropic_chat(
            content=chat_content,
            session_id=session_id,
            model=selected_model,
        )
    else:
        assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens = _run_openai_chat(
            content=chat_content,
            session_id=session_id,
            model=selected_model,
        )

    if not total_tokens:
        total_tokens = prompt_tokens + completion_tokens
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
