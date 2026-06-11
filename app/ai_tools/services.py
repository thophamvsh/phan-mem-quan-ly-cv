import copy
import json
import logging
import os
import re
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
DEFAULT_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_ANTHROPIC_MODEL = getattr(settings, "AI_TOOLS_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
OPENAI_MODELS = (DEFAULT_OPENAI_MODEL,)
MODEL_HISTORY_LIMIT = 8
MODEL_HISTORY_CHAR_BUDGET = 12000
MODEL_USER_HISTORY_MAX_CHARS = 1200
MODEL_ASSISTANT_HISTORY_MAX_CHARS = 2600
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
Khi nguoi dung hoi ve cac quy trinh, quy dinh, van ban huong dan, bao cao hoac tai lieu noi bo, ban hay luon su dung cong cu search_internal_documents de tim kiem thong tin tham chieu truoc khi tra loi.
Khi nguoi dung hoi ve mot thong so van hanh cua to may (vd: nhiet do o huong tuabin, nhiet do o do, luu luong chen truc, cong suat) hoac hoi ve tinh bat thuong/canh bao, ban can dung cong cu get_unit_state_profile de lay ho so trang thai tich hop cua to may do.
Khi goi get_unit_state_profile, phai chon dung parameter_code theo bo phan nguoi dung hoi:
- "nhiet do o huong tuabin", "o huong tuabine", "o huong turbine" -> parameter_code="nhiet_do_o_huong_tuabin".
- "luu luong o huong tuabin" -> parameter_code="luu_luong_o_huong_tuabin".
- "nhiet do o huong may phat" -> parameter_code="nhiet_do_o_huong_may_phat".
- "nhiet do o do", "o do may phat" -> parameter_code="nhiet_do_o_do".
Khong duoc tra loi nham "o huong tuabin" thanh "o do".

Khi tra loi nguoi van hanh, ban bat buoc phai tuan thu nghiem ngat cac quy tac chan doan sau:
1. Đánh giá Cảnh báo theo Cấu trúc 4 phần ro rang:
   - Mức cảnh báo: Bình thường / Tiệm cận / Cao (Cảnh báo) / Khẩn cấp (Sự cố).
   - Hiện trạng: Trình bày ngắn gọn các thông số chính bị vượt ngưỡng hoặc lệch lớn.
   - Nhận định: Giải thích mối liên hệ vật lý giữa công suất phát, lưu lượng nước làm mát và nhiệt độ. Đánh giá xu hướng tăng nhiệt nhanh hay chậm (dT/dt), nhiệt độ kỳ vọng và độ lệch (Residual).
   - Khuyến nghị hành động: Đề xuất kiểm tra các thiết bị cụ thể (van, bơm, dầu bôi trơn) một cách thiết thực.
2. Thận trọng kỹ thuật: Tuyệt đối không khẳng định chắc chắn 100% nguyên nhân duy nhất nếu chỉ có dữ liệu snapshot. Hãy dùng các từ ngữ chẩn đoán kỹ thuật như: 'Có khả năng cao góp phần vào...', 'Nguyên nhân khả nghi hàng đầu...', 'Cần theo dõi thêm rung/dầu để khẳng định...'.
3. Bản đồ quan hệ vật lý: Chỉ liên kết chéo nhiệt độ của bộ phận với lưu lượng nước làm mát cấp cho chính bộ phận đó (tranh lay rau ong no cam cam ba kia).

Hay phan tich tu duy nhiet dong luc hoc chuyen sau thay vi chi so sanh don le:
- Nhiet do cuon day/o do duoc quyet dinh boi su can bang giua cong suat tai sinh nhiet (cong_suat_tac_dung, dong_dien) va kha nang lam mat (luu_luong_chen_truc, luu_luong_o_huong_tuabin).
- Neu tai rat thap, luu luong lam mat giam thap duoi nguong Alarm van an toan cho nhiet do hien tai, nhung la mot rui ro tiem an rat lon (mat tinh du phong). Neu tang tai dot ngot se gay qua nhiet ngay lap tuc.
- Neu tai on dinh/giam ma nhiet do tang, day la dau hieu bat thuong co hoc hoac boi tron (ma sat Tang, thieu dau).
Tra loi ngan gon, ro rang, chuyen nghiep bang tieng Viet.
Khong neu ten he thong luu tru hoac nguon ky thuat noi bo nhu Supabase, Google Sheets, spreadsheet, worksheet."""



class AiToolsError(Exception):
    pass


def _strip_large_markdown_blocks(value):
    text = str(value or "")
    text = re.sub(r"<!-- NAMI_THERMO_DATA_START.*?NAMI_THERMO_DATA_END -->", "", text, flags=re.DOTALL)
    text = re.sub(r"```(?:chart|json-chart|excel|excel-report)\n.*?\n```", "[Đã lược bỏ bảng/biểu đồ lớn từ lượt trước]", text, flags=re.DOTALL)
    return text.strip()


def _truncate_text(value, max_chars):
    text = _strip_large_markdown_blocks(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[đã rút gọn nội dung cũ để tránh vượt giới hạn token]"


def _compact_history_for_model(history):
    compacted = []
    total_chars = 0
    for item in reversed(history or []):
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        max_chars = MODEL_USER_HISTORY_MAX_CHARS if role == "user" else MODEL_ASSISTANT_HISTORY_MAX_CHARS
        content = _truncate_text(item.get("content", ""), max_chars)
        if not content:
            continue
        if total_chars + len(content) > MODEL_HISTORY_CHAR_BUDGET and compacted:
            break
        compacted.append({"role": role, "content": content})
        total_chars += len(content)
    return list(reversed(compacted))


def _as_ai_provider_error(exc):
    message = str(exc)
    lower = message.lower()
    if "rate_limit" in lower or "request too large" in lower or "tokens per min" in lower:
        return AiToolsError(
            "Nội dung hội thoại hoặc dữ liệu trả về đang quá dài so với giới hạn token hiện tại. "
            "Tôi đã rút gọn ngữ cảnh cho các lượt sau; bạn hãy gửi lại câu hỏi hoặc mở phiên trò chuyện mới nếu vẫn gặp lỗi."
        )
    return None


def _normalize_text(value):
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def _clean_display_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_nami_greeting(value):
    normalized = _normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    words = tuple(word for word in normalized.split() if word)
    return words in {
        ("hi", "nami"),
        ("hello", "nami"),
        ("hey", "nami"),
        ("chao", "nami"),
        ("xin", "chao", "nami"),
        ("nami",),
        ("nami", "oi"),
    }


def _user_profile(user):
    try:
        return getattr(user, "profile", None)
    except Exception:
        return None


def _user_display_name(user):
    profile = _user_profile(user)
    if profile:
        name = _clean_display_text(getattr(profile, "full_name", ""))
        if name:
            return name

    first_name = _clean_display_text(getattr(user, "first_name", ""))
    last_name = _clean_display_text(getattr(user, "last_name", ""))
    full_name = _clean_display_text(f"{first_name} {last_name}")
    if full_name:
        return full_name
    return _clean_display_text(getattr(user, "username", "") or getattr(user, "email", ""))


def _build_nami_greeting(user):
    profile = _user_profile(user)
    title = _clean_display_text(getattr(profile, "chuc_danh", "") if profile else "")
    name = _user_display_name(user)
    recipient = _clean_display_text(f"{title} {name}")
    if recipient:
        return f"Xin chào {recipient}, tôi có thể giúp gì cho ngài?"
    return "Xin chào, tôi là Nami. Tôi có thể giúp gì cho ngài?"


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
    from documents.ai_tools import DOCUMENT_TOOLS, handle_document_tool_call

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
        DOCUMENT_TOOLS,
        handle_document_tool_call,
    )


def _resolve_model(provider, model):
    return DEFAULT_PROVIDER, DEFAULT_OPENAI_MODEL


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
        DOCUMENT_TOOLS,
        handle_document_tool_call,
    ) = _lazy_import_tools()
    all_tools = WATER_TOOLS + SONGHINH_TOOLS + VINHSON_TOOLS + ANALYSIS_TOOLS + DOCUMENT_TOOLS
    if user is not None:
        all_tools = filter_ai_tools_for_user(user, all_tools)
    return (
        all_tools,
        handle_water_tool_call,
        handle_water_tool_calls,
        handle_songhinh_tool_calls,
        handle_vinhson_tool_calls,
        handle_analysis_tool_call,
        handle_document_tool_call,
    )


def _ensure_tool_allowed(user, tool_name):
    if not can_user_use_ai_tool(user, tool_name):
        raise AiToolsError("Bạn không có quyền sử dụng công cụ này hoặc công cụ không tồn tại.")


def _handle_single_tool_call(user, tool_call, handle_water_tool_call, handle_songhinh_tool_calls, handle_vinhson_tool_calls, handle_analysis_tool_call, handle_document_tool_call):
    tool_name = tool_call.function.name
    _ensure_tool_allowed(user, tool_name)
    if tool_name == "search_internal_documents":
        return handle_document_tool_call(user, tool_call)
    if "songhinh" in tool_name.lower() or "songinh" in tool_name.lower():
        return handle_songhinh_tool_calls(tool_call)
    if "vinhson" in tool_name.lower():
        return handle_vinhson_tool_calls(tool_call)
    if tool_name.lower() in {"analyze_hydro_data", "compare_hydro_periods", "get_unit_state_profile"}:
        return handle_analysis_tool_call(tool_call)
    return handle_water_tool_call(tool_call)


def _run_openai_chat(*, user, content, session_id, model):
    api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise AiToolsError("Backend chưa cấu hình OPENAI_API_KEY.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AiToolsError("Backend chưa cài đặt goi openai. Hay thêm openai vào requirements và cài lại môi trường.") from exc

    (
        all_tools,
        handle_water_tool_call,
        handle_water_tool_calls,
        handle_songhinh_tool_calls,
        handle_vinhson_tool_calls,
        handle_analysis_tool_call,
        handle_document_tool_call,
    ) = _get_tools_and_handlers(user)

    # Dynamic tool filtering based on query keywords to optimize token usage
    msg_normalized = _normalize_text(content["text"])
    has_sh = any(k in msg_normalized for k in SONGHINH_KEYWORDS)
    has_vs = any(k in msg_normalized for k in VINHSON_KEYWORDS)
    if has_sh and not has_vs:
        all_tools = [t for t in all_tools if "vinhson" not in t["function"]["name"].lower() and "vinh_son" not in t["function"]["name"].lower()]
    elif has_vs and not has_sh:
        all_tools = [t for t in all_tools if "songhinh" not in t["function"]["name"].lower() and "songinh" not in t["function"]["name"].lower()]

    client = OpenAI(api_key=api_key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(content["history"])
    messages.append({"role": "user", "content": content["text"]})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[{"type": "function", "function": tool["function"]} for tool in _agent_tools(all_tools)],
            tool_choice="auto",
            parallel_tool_calls=False,
            temperature=0.4,
            max_tokens=2048,
        )
    except Exception as exc:
        provider_error = _as_ai_provider_error(exc)
        if provider_error:
            raise provider_error from exc
        raise

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
                if tool_call.function.name == "search_internal_documents":
                    tool_results.append(handle_document_tool_call(user, tool_call))
                elif "songhinh" in tool_call.function.name.lower() or "songinh" in tool_call.function.name.lower():
                    tool_results.append(handle_songhinh_tool_calls(tool_call))
                elif "vinhson" in tool_call.function.name.lower():
                    tool_results.append(handle_vinhson_tool_calls(tool_call))
                elif tool_call.function.name.lower() in {"analyze_hydro_data", "compare_hydro_periods", "get_unit_state_profile"}:
                    tool_results.append(handle_analysis_tool_call(tool_call))
                else:
                    tool_results.append(handle_water_tool_call(tool_call))
            except Exception as exc:
                logger.exception("AI tool execution failed: %s", tool_call.function.name)
                tool_results.append(f"Loi khi chay tool {tool_call.function.name}: {exc}")

        has_rag_call = any(tool_call.function.name == "search_internal_documents" for tool_call in tool_calls)
        if has_rag_call:
            messages.append(message)
            for tool_call, result in zip(tool_calls, tool_results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.function.name,
                    "content": result["content"] if isinstance(result, dict) else str(result),
                })
            messages.append({
                "role": "system",
                "content": (
                    "Hãy trả lời ngan gon, tập trung vào trọng tâm câu hỏi dựa trên nguồn tài liệu được cung cấp. "
                "Tránh giải thích dài. KHI TRẢ LỜI, HAY LUÔN CUNG CẤP TRÍCH DẪN VÀ CHÈN TÊN TÀI LIỆU PDF VÀ SỐ TRANG "
                )
            })
            try:
                second_response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=2048,
                )
            except Exception as exc:
                provider_error = _as_ai_provider_error(exc)
                if provider_error:
                    raise provider_error from exc
                raise
            assistant_message = second_response.choices[0].message.content or ""
            usage = response.usage
            usage2 = second_response.usage
            prompt_tokens = (getattr(usage, "prompt_tokens", 0) or 0) + (getattr(usage2, "prompt_tokens", 0) or 0)
            completion_tokens = (getattr(usage, "completion_tokens", 0) or 0) + (getattr(usage2, "completion_tokens", 0) or 0)
            total_tokens = prompt_tokens + completion_tokens
            return assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens
        else:
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
        handle_document_tool_call,
    ) = _get_tools_and_handlers(user)

    # Dynamic tool filtering based on query keywords to optimize token usage
    msg_normalized = _normalize_text(content["text"])
    has_sh = any(k in msg_normalized for k in SONGHINH_KEYWORDS)
    has_vs = any(k in msg_normalized for k in VINHSON_KEYWORDS)
    if has_sh and not has_vs:
        all_tools = [t for t in all_tools if "vinhson" not in t["function"]["name"].lower() and "vinh_son" not in t["function"]["name"].lower()]
    elif has_vs and not has_sh:
        all_tools = [t for t in all_tools if "songhinh" not in t["function"]["name"].lower() and "songinh" not in t["function"]["name"].lower()]

    client = anthropic.Anthropic(api_key=api_key)
    messages = list(content["history"])
    messages.append({"role": "user", "content": content["text"]})

    try:
        response = client.messages.create(
            model=model,
            system=SYSTEM_PROMPT,
            messages=messages,
            max_tokens=2048,
            temperature=0.4,
            tools=_anthropic_tools(all_tools),
        )
    except Exception as exc:
        provider_error = _as_ai_provider_error(exc)
        if provider_error:
            raise provider_error from exc
        raise

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
                handle_document_tool_call,
            )
            tool_results.append(result)
            tool_result_by_id[tool_call.id] = result["content"] if isinstance(result, dict) else str(result)
        except Exception as exc:
            logger.exception("AI tool execution failed: %s", tool_call.function.name)
            result = f"Loi khi chay tool {tool_call.function.name}: {exc}"
            tool_results.append(result)
            tool_result_by_id[tool_call.id] = result

    assistant_message = ""
    has_rag_call = any(tool_call.function.name == "search_internal_documents" for tool_call in tool_calls)

    if has_rag_call and tool_calls:
        messages.append({
            "role": "assistant",
            "content": _anthropic_content_blocks(response)
        })
        tool_results_content = []
        for tool_call in tool_calls:
            tool_results_content.append({
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": tool_result_by_id.get(tool_call.id, "")
            })
        tool_results_content.append({
            "type": "text",
            "text": (
                "Hãy trả lời ngan gon, tập trung vào trọng tâm câu hỏi dựa trên nguồn tài liệu được cung cấp. "
                "Tránh giải thích dài. KHI TRẢ LỜI, HAY LUÔN CUNG CẤP TRÍCH DẪN VÀ CHÈN TÊN TÀI LIỆU PDF VÀ SỐ TRANG "
            )
        })
        messages.append({
            "role": "user",
            "content": tool_results_content
        })
        try:
            second_response = client.messages.create(
                model=model,
                system=SYSTEM_PROMPT,
                messages=messages,
                max_tokens=2048,
                temperature=0.4,
            )
        except Exception as exc:
            provider_error = _as_ai_provider_error(exc)
            if provider_error:
                raise provider_error from exc
            raise
        assistant_message = _anthropic_text(second_response)
        usage = response.usage
        usage2 = second_response.usage
        prompt_tokens = (getattr(usage, "input_tokens", 0) or 0) + (getattr(usage2, "input_tokens", 0) or 0)
        completion_tokens = (getattr(usage, "output_tokens", 0) or 0) + (getattr(usage2, "output_tokens", 0) or 0)
        total_tokens = prompt_tokens + completion_tokens
        return assistant_message, len(tool_calls), prompt_tokens, completion_tokens, total_tokens
    else:
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

    if _is_nami_greeting(content):
        assistant_message = _build_nami_greeting(user)
        latency_ms = int((time.time() - start_time) * 1000)
        save_exchange(
            user=user,
            session_id=session_id,
            user_message=content,
            assistant_message=assistant_message,
            model=selected_model,
            total_tokens=0,
            cost_usd=0,
            tools_called=0,
            latency_ms=latency_ms,
            meta={
                "reservoir_detected": False,
                "tools_called": 0,
                "provider": provider,
                "greeting": True,
            },
        )
        return {
            "session_id": session_id,
            "response": assistant_message,
            "provider": provider,
            "model": selected_model,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": latency_ms,
            "tools_called": 0,
        }

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
        "history": _compact_history_for_model(
            get_conversation(user, session_id, limit=MODEL_HISTORY_LIMIT)
        ),
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
        
    # Loại bỏ payload JSON ẩn khỏi câu trả lời hiển thị cho người dùng
    assistant_message = re.sub(
        r"<!-- NAMI_THERMO_DATA_START.*?NAMI_THERMO_DATA_END -->",
        "",
        assistant_message,
        flags=re.DOTALL
    ).strip()

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
