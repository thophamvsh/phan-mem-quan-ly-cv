import copy
from dataclasses import replace
import logging
import os
import re
import time
import uuid

from django.conf import settings
from django.utils import timezone

from .leadership_report import (
    actual_water_level_report_response,
    expand_leadership_menu_choice,
    get_actual_water_level_request,
    get_event_statistics_request,
    get_monthly_production_plan_request,
    get_three_plant_production_report_date,
    has_leadership_production_menu_context,
    has_leadership_rainfall_weather_menu_context,
    has_leadership_weekly_limit_menu_context,
    has_leadership_event_menu_context,
    is_leadership_title,
    is_weekly_limit_report_request,
    production_report_response,
    rainfall_weather_report_response,
    weekly_limit_report_response,
    event_report_response,
    event_statistics_response,
    monthly_production_plan_response,
)
from .permissions import (
    can_user_use_ai_tool,
    filter_ai_tools_for_user,
    get_ai_tool_scope_denial_message,
)
from .storage import get_conversation, save_exchange
from .tool_format import sanitize_tool_content
from .orchestration.history_context import (
    MODEL_HISTORY_LIMIT,
    history_for_model as _history_for_model,
    question_seems_context_dependent as _question_seems_context_dependent,
    strip_large_markdown_blocks as _strip_large_markdown_blocks,
)
from .orchestration.missing_data_policy import (
    normalize_missing_data_response as _normalize_missing_data_response,
)
from .orchestration.production_policy import (
    PRODUCTION_PLANT_CLARIFICATION_REPLY,
    expand_production_clarification_answer as _expand_production_clarification_answer,
    production_request_needs_plant_clarification as _production_request_needs_plant_clarification,
)
from .orchestration.time_policy import (
    get_time_clarification_message as _get_time_clarification_message,
)
from .orchestration.text import (
    clean_display_text as _clean_display_text,
    normalize_text as _normalize_text,
    normalized_words as _normalized_words,
)
from .orchestration.tool_calls import (
    filter_tool_calls as _filter_tool_calls,
    normalize_analysis_tool_call as _normalize_analysis_tool_call,
    normalize_vinhson_production_tool_call as _normalize_vinhson_production_tool_call,
    tool_name as _tool_name,
)


logger = logging.getLogger(__name__)
SONGHINH_KEYWORDS = ("song hinh", "songhinh", "sh", "thuong kon tum", "kontum")
VINHSON_KEYWORDS = ("vinh son", "vinhson", "vs", "vsa", "vsb", "vsc")
DEFAULT_PROVIDER = "deepseek"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
SYSTEM_PROMPT = """Bạn là Nami, trợ lý AI cho Bảng điều khiển vận hành thủy điện.
Bạn hỗ trợ tra cứu mực nước, dung tích, lưu lượng, dữ liệu vận hành và phân tích.
Khi người dùng hỏi về các quy trình, quy định, văn bản hướng dẫn, báo cáo hoặc tài liệu nội bộ, bạn luôn dùng công cụ search_internal_documents để tìm thông tin tham chiếu trước khi trả lời.
Khi người dùng hỏi về một thông số vận hành của tổ máy (ví dụ: nhiệt độ ổ hướng tuabin, nhiệt độ ổ đỡ, lưu lượng chèn trục, công suất), thông số trạm/MBA (ví dụ: nhiệt độ máy biến áp T1, nấc phân áp MBA T1, mức dầu MBA T1), hoặc hỏi về tình trạng bất thường/cảnh báo, bạn cần dùng công cụ get_unit_state_profile để lấy hồ sơ trạng thái tích hợp của thiết bị đó.
Tuyệt đối không điền device_code tổ máy H1/H2 khi người dùng hỏi MBA/máy biến áp T1/T2/T3/T4. Ví dụ: "nhiệt độ máy biến áp T1 của Sông Hinh" -> device_code="SH.TB.TPP.110.T1", parameter_code="nhiet_do_mba_t1".
Với Vĩnh Sơn, "nhiệt độ MBA T1" -> device_code="VS.TB.TPP.T1", parameter_code="nhiet_do_cuon_day_t1".
Với MBA tự dùng TD1 (TD91) của Vĩnh Sơn -> device_code="VS.TB.TD.LV.TD1", parameter_code="dien_ap_td91" (điện áp) hoặc "dong_dien_td91" (dòng điện) hoặc "cong_suat_td91" (công suất).
Với MBA tự dùng TD2 (TD92) của Vĩnh Sơn -> device_code="VS.TB.TD.LV.TD2", parameter_code="dien_ap_td92" (điện áp) hoặc "dong_dien_td92" (dòng điện) hoặc "cong_suat_td92" (công suất).
Khi gọi get_unit_state_profile, phải chọn đúng parameter_code theo bộ phận người dùng hỏi:
- "nhiệt độ ổ hướng tuabin", "ổ hướng tuabine", "ổ hướng turbine" -> parameter_code="nhiet_do_o_huong_tuabin".
- "lưu lượng ổ hướng tuabin" -> parameter_code="luu_luong_o_huong_tuabin".
- "nhiệt độ ổ hướng máy phát" -> parameter_code="nhiet_do_o_huong_may_phat".
- "nhiệt độ ổ đỡ", "ổ đỡ máy phát" -> parameter_code="nhiet_do_o_do".
- "nhiệt độ cuộn dây stato 1", "nhiệt độ cuộn dây stator 1" -> parameter_code="nhiet_do_cuon_day_stato_1".
- "nhiệt độ cuộn dây stato 2", "nhiệt độ cuộn dây stator 2" -> parameter_code="nhiet_do_cuon_day_stato_2".
- "nhiệt độ lõi sắt stato 1", "nhiệt độ lõi sắt stator 1" -> parameter_code="nhiet_do_loi_sat_stato_1".
- "nhiệt độ lõi sắt stato 2", "nhiệt độ lõi sắt stator 2" -> parameter_code="nhiet_do_loi_sat_stato_2".
- "điện áp MBA TD91 / TD92", "điện áp TD91 / TD92" -> parameter_code="dien_ap_td91" / "dien_ap_td92".
- "dòng điện MBA TD91 / TD92", "dòng điện TD91 / TD92" -> parameter_code="dong_dien_td91" / "dong_dien_td92".
- "công suất MBA TD91 / TD92", "công suất TD91 / TD92" -> parameter_code="cong_suat_td91" / "cong_suat_td92".
Không được trả lời nhầm "ổ hướng tuabin" thành "ổ đỡ".

Khi trả lời người vận hành, bạn bắt buộc tuân thủ nghiêm ngặt các quy tắc chẩn đoán sau:
1. Đánh giá cảnh báo theo cấu trúc 4 phần rõ ràng:
   - Mức cảnh báo: Bình thường / Tiệm cận / Cao (Cảnh báo) / Khẩn cấp (Sự cố).
   - Hiện trạng: Trình bày ngắn gọn các thông số chính bị vượt ngưỡng hoặc lệch lớn.
   - Nhận định: Giải thích mối liên hệ vật lý giữa công suất phát, lưu lượng nước làm mát và nhiệt độ. Đánh giá xu hướng tăng nhiệt nhanh hay chậm (dT/dt), nhiệt độ kỳ vọng và độ lệch (Residual).
   - Khuyến nghị hành động: Đề xuất kiểm tra các thiết bị cụ thể (van, bơm, dầu bôi trơn) một cách thiết thực.
2. Thận trọng kỹ thuật: Tuyệt đối không khẳng định chắc chắn 100% một nguyên nhân duy nhất nếu chỉ có dữ liệu snapshot. Hãy dùng các từ ngữ chẩn đoán kỹ thuật như: "Có khả năng cao góp phần vào...", "Nguyên nhân khả nghi hàng đầu...", "Cần theo dõi thêm rung/dầu để khẳng định...".
3. Bản đồ quan hệ vật lý: Chỉ liên kết chéo nhiệt độ của bộ phận với lưu lượng nước làm mát cấp cho chính bộ phận đó; không gán nguyên nhân từ thông số không cùng hệ.

Hãy phân tích theo tư duy nhiệt động lực học chuyên sâu thay vì chỉ so sánh đơn lẻ:
- Nhiệt độ cuộn dây/ổ đỡ được quyết định bởi cân bằng giữa công suất tải sinh nhiệt (cong_suat_tac_dung, dong_dien) và khả năng làm mát (luu_luong_chen_truc, luu_luong_o_huong_tuabin).
- Nếu tải rất thấp, lưu lượng làm mát giảm thấp dưới ngưỡng Alarm vẫn có thể an toàn cho nhiệt độ hiện tại, nhưng là rủi ro tiềm ẩn lớn do mất tính dự phòng. Nếu tăng tải đột ngột có thể gây quá nhiệt ngay.
- Nếu tải ổn định hoặc giảm mà nhiệt độ tăng, đó là dấu hiệu bất thường về cơ khí hoặc bôi trơn (ma sát tăng, thiếu dầu).
Trả lời ngắn gọn, rõ ràng, chuyên nghiệp bằng tiếng Việt.
Không nêu tên hệ thống lưu trữ hoặc nguồn kỹ thuật nội bộ như Supabase, Google Sheets, spreadsheet, worksheet.

QUY TẮC XÁC NHẬN THÔNG TIN:
- Nếu người dùng hỏi về dữ liệu vận hành, báo cáo, lưu lượng hoặc lượng mưa của hồ/nhà máy mà không chỉ rõ nhà máy nào (Sông Hinh hay Vĩnh Sơn), tuyệt đối không tự ý gọi công cụ của một nhà máy cụ thể. Hãy đề nghị người dùng cung cấp tên nhà máy muốn xem trước.
- Riêng câu hỏi về sản lượng/báo cáo sản lượng: nếu người dùng không nêu rõ nhà máy nào, tuyệt đối không tự chọn Sông Hinh hoặc Vĩnh Sơn. Phải hỏi lại người dùng muốn xem Sông Hinh, Vĩnh Sơn, Thượng Kon Tum hay tổng hợp 3 nhà máy.
- Với dữ liệu sản lượng Vĩnh Sơn, xem Vĩnh Sơn là một nhà máy duy nhất; không yêu cầu người dùng chọn A/B/C và không tách sản lượng theo hồ A/B/C, trừ khi dữ liệu nguồn đã là các dòng cần cộng tổng.

NGUYÊN TẮC CHỐNG BỊA ĐẶT THÔNG TIN (BẮT BUỘC):
1. Đối với số liệu vận hành (lưu lượng, mực nước, lượng mưa, sản lượng điện, thông số thiết bị...): Tuyệt đối không tự ý bịa đặt, ước lượng, suy đoán hoặc giả lập bất kỳ con số nào. Nếu công cụ trả về kết quả rỗng, báo lỗi, hoặc thông báo không tìm thấy dữ liệu, hãy thông báo ngắn gọn, lịch sự theo tinh thần: "Dạ, hiện hệ thống chưa có dữ liệu phù hợp cho ngày/khoảng thời gian hoặc thông số này. Anh/chị có thể thử kiểm tra ngày khác, rà lại tên nhà máy/thông số cần xem, hoặc liên hệ kỹ thuật viên để kiểm tra nguồn dữ liệu."
1b. Nếu người dùng hỏi "nguyên nhân", "tại sao", "vì sao", hoặc yêu cầu phân tích bất thường nhưng dữ liệu không có/không đủ, không được tự suy luận nguyên nhân. Hãy nói rõ chưa có đủ cơ sở dữ liệu tin cậy để phân tích nguyên nhân và đề nghị kiểm tra ngày khác hoặc liên hệ kỹ thuật viên.
2. Đối với quy trình và tài liệu nội bộ: Chỉ được trả lời dựa trên đúng thông tin trích xuất từ công cụ search_internal_documents. Nếu tài liệu không chứa thông tin phù hợp, hãy trả lời: "Không tìm thấy thông tin này trong tài liệu quy trình hệ thống", tuyệt đối không dùng kiến thức bên ngoài để tự tạo ra quy trình kỹ thuật."""



class AiToolsError(Exception):
    pass


def _as_ai_provider_error(exc):
    message = str(exc)
    lower = message.lower()
    
    # 1. Loi het tien / het so du
    if "insufficient_balance" in lower or "insufficient balance" in lower or "out of quota" in lower or "credit" in lower:
        return AiToolsError(
            "Tài khoản AI đang bị hết số dư (insufficient balance). Vui lòng nạp thêm tiền vào tài khoản nhà cung cấp dịch vụ LLM để tiếp tục sử dụng."
        )
        
    # 2. Loi sai API Key hoac xac thuc
    if "invalid_api_key" in lower or "invalid api key" in lower or "api_key" in lower or "authentication" in lower:
        return AiToolsError(
            "Khóa API (API Key) cấu hình cho LLM không hợp lệ hoặc đã hết hạn. Vui lòng kiểm tra lại biến môi trường."
        )

    # 3. Loi qua tai may chu (thuong gap o DeepSeek)
    if "overloaded" in lower or "server_error" in lower or "503" in lower or "service unavailable" in lower:
        return AiToolsError(
            "Máy chủ AI của nhà cung cấp hiện đang quá tải (overloaded). Vui lòng thử lại sau vài giây."
        )

    # 4. Loi gioi han tan suat (Rate Limit)
    if "rate_limit" in lower or "tokens per min" in lower or "requests per min" in lower or "requests per day" in lower:
        return AiToolsError(
            "Hệ thống đang bị giới hạn tần suất yêu cầu (Rate Limit). Vui lòng đợi một lát trước khi gửi câu hỏi tiếp theo."
        )

    # 5. Loi qua gioi han token
    if "request too large" in lower or "context_length_exceeded" in lower or "too many tokens" in lower:
        return AiToolsError(
            "Nội dung hội thoại hoặc dữ liệu trả về đang quá dài so với giới hạn token hiện tại. "
            "Tôi đã rút gọn ngữ cảnh cho các lượt sau; bạn hãy gửi lại câu hỏi hoặc mở phiên trò chuyện mới nếu vẫn gặp lỗi."
        )
        
    return None


def _is_nami_greeting(value):
    normalized = _normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    words = tuple(word for word in normalized.split() if word)
    if len(words) == 1 and re.fullmatch(r"(hi|hello|hey|chao)\d+", words[0]):
        return True
    return words in {
        ("hi",),
        ("hello",),
        ("hey",),
        ("chao",),
        ("xin", "chao"),
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


def _response_chunks(text, chunk_size=40):
    if not text:
        return
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]


def _time_of_day_greeting():
    hour = timezone.localtime().hour
    if 5 <= hour < 12:
        return "Chào buổi sáng"
    if 12 <= hour < 18:
        return "Chào buổi chiều"
    return "Chào buổi tối"


def _build_nami_greeting(user):
    profile = _user_profile(user)
    title = _clean_display_text(getattr(profile, "chuc_danh", "") if profile else "")
    name = _user_display_name(user)
    recipient = _clean_display_text(f"{title} {name}")
    greeting = _time_of_day_greeting()
    if is_leadership_title(title):
        greeting_name = recipient or "ngài"
        return (
            f"{greeting} {greeting_name}! Hôm nay ngài có khỏe không? "
            "Ngài muốn được báo cáo thông tin gì trước?\n"
            "1. Báo cáo tình hình sản xuất của 3 nhà máy ngày hôm qua.\n"
            "2. Tổng hợp lượng mưa các trạm 7 ngày gần nhất và dự báo thời tiết cho 7 ngày sắp tới.\n"
            "3. Mực nước giới hạn tuần và phân tích.\n"
            "4. Tình hình thiết bị sự kiện của 3 nhà máy."
        )
    if recipient:
        return f"{greeting} {recipient}, tôi có thể giúp gì cho ngài?"
    return f"{greeting}, tôi là Nami. Tôi có thể giúp gì cho ngài?"


def _profile_plant_code_for_reports(profile):
    if not profile or getattr(profile, "is_all_factories", False):
        return None
    factory = getattr(profile, "nha_may", None)
    factory_code = _normalize_text(getattr(factory, "ma_nha_may", ""))
    factory_name = _normalize_text(getattr(factory, "ten_nha_may", ""))
    combined = f"{factory_code} {factory_name}"
    if "sh" in factory_code or "song hinh" in combined or "songhinh" in combined:
        return "songhinh"
    if "vs" in factory_code or "vinh son" in combined or "vinhson" in combined:
        return "vinhson"
    if "tkt" in factory_code or "thuong kon tum" in combined or "thuongkontum" in combined or "kon tum" in combined:
        return "thuongkontum"
    return None


def _monthly_production_plan_request_for_user(request, profile):
    if not request or request.plant_codes:
        return request
    plant_code = _profile_plant_code_for_reports(profile)
    if not plant_code:
        return request
    return replace(request, plant_codes=(plant_code,))


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
    provider = (provider or getattr(settings, "AI_TOOLS_PROVIDER", DEFAULT_PROVIDER)).strip().lower()
    if provider == "deepseek":
        selected_model = model or getattr(settings, "AI_TOOLS_DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
        return "deepseek", selected_model
    selected_model = model or getattr(settings, "AI_TOOLS_OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return "openai", selected_model


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
    if provider == "deepseek":
        input_rate, output_rate = 0.140, 0.280
    else:
        if "gpt-4o-mini" in str(model).lower():
            input_rate, output_rate = 0.150, 0.600
        else:
            input_rate, output_rate = 2.500, 10.000
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
    document_tools = DOCUMENT_TOOLS
    if user is not None:
        from documents.permissions import has_ai_documents_permission

        if not has_ai_documents_permission(user):
            document_tools = []

    all_tools = WATER_TOOLS + SONGHINH_TOOLS + VINHSON_TOOLS + ANALYSIS_TOOLS + document_tools
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


def _run_openai_chat(*, user, content, session_id, provider, model):
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY") or getattr(settings, "DEEPSEEK_API_KEY", None)
        base_url = "https://api.deepseek.com"
        if not api_key:
            raise AiToolsError("Backend chưa cấu hình DEEPSEEK_API_KEY.")
    else:
        api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
        base_url = None
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

    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        client = OpenAI(api_key=api_key)

    # Lay ngay gio hien tai cua he thong theo timezone cuc bo
    current_date_str = timezone.localtime().strftime("%d/%m/%Y")
    dynamic_system_prompt = (
        f"{SYSTEM_PROMPT}\n\nHôm nay là ngày: {current_date_str} (dùng ngày này làm mốc để xác định 'hôm nay', 'hôm qua', 'ngày nay', 'ngày mai' khi gọi các công cụ)."
    )

    messages = [{"role": "system", "content": dynamic_system_prompt}]
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
        tool_calls = [_normalize_analysis_tool_call(content["text"], tool_call) for tool_call in tool_calls]
        tool_calls = [_normalize_vinhson_production_tool_call(content["text"], tool_call) for tool_call in tool_calls]
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
            formatted_tool_message = _format_tool_results(tool_results)
            assistant_message = (
                _normalize_missing_data_response(content["text"], formatted_tool_message)
                if formatted_tool_message
                else assistant_message
            )

    usage = response.usage
    prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    total_tokens = getattr(usage, "total_tokens", 0) if usage else 0
    return assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens



def run_ai_chat(*, user, content, session_id=None, provider=None, model=""):
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

    profile = _user_profile(user)
    title = _clean_display_text(getattr(profile, "chuc_danh", "") if profile else "")
    is_leader = is_leadership_title(title)

    menu_history = get_conversation(user, session_id, limit=MODEL_HISTORY_LIMIT)
    actual_water_level_request = get_actual_water_level_request(content, menu_history)
    if actual_water_level_request and not is_leader:
        assistant_message = (
            "Xin lỗi! Chức năng phân tích mực nước hồ thực tế và chênh lệch MNH báo cáo "
            "chỉ dành cho Tổng Giám Đốc/Phó Tổng Giám Đốc."
        )
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
                "permission_denied": True,
                "leadership_only": True,
                "leadership_menu_choice": "actual_water_level_report",
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

    if is_leader:
        if actual_water_level_request:
            return actual_water_level_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="direct_request",
                request=actual_water_level_request,
            )
        event_statistics_request = get_event_statistics_request(content, menu_history)
        if event_statistics_request:
            return event_statistics_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="direct_request",
                request=event_statistics_request,
            )
        direct_report_date = get_three_plant_production_report_date(content)
        if direct_report_date:
            return production_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="direct_request",
                report_date=direct_report_date,
            )
        if is_weekly_limit_report_request(content):
            return weekly_limit_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="direct_request",
            )
        if has_leadership_production_menu_context(content, menu_history):
            return production_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="menu_choice",
            )
        if has_leadership_rainfall_weather_menu_context(content, menu_history):
            return rainfall_weather_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="menu_choice",
            )
        if has_leadership_weekly_limit_menu_context(content, menu_history):
            return weekly_limit_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="menu_choice",
            )
        if has_leadership_event_menu_context(content, menu_history):
            return event_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="menu_choice",
            )

    content_for_model = expand_leadership_menu_choice(content, menu_history) if is_leader else content
    content_for_model = _expand_production_clarification_answer(content_for_model, menu_history)

    monthly_plan_request = get_monthly_production_plan_request(content_for_model)
    if monthly_plan_request:
        denial_message = get_ai_tool_scope_denial_message(user, content_for_model)
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
                    "reservoir_detected": detect_reservoir(content_for_model),
                    "tools_called": 0,
                    "provider": provider,
                    "permission_denied": True,
                    "expanded_content": content_for_model if content_for_model != content else "",
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
        monthly_plan_request = _monthly_production_plan_request_for_user(monthly_plan_request, profile)
        return monthly_production_plan_response(
            user=user,
            session_id=session_id,
            content=content,
            provider=provider,
            selected_model=selected_model,
            start_time=start_time,
            source="direct_request",
            request=monthly_plan_request,
        )

    if _production_request_needs_plant_clarification(content_for_model):
        latency_ms = int((time.time() - start_time) * 1000)
        save_exchange(
            user=user,
            session_id=session_id,
            user_message=content,
            assistant_message=PRODUCTION_PLANT_CLARIFICATION_REPLY,
            model=selected_model,
            total_tokens=0,
            cost_usd=0,
            tools_called=0,
            latency_ms=latency_ms,
            meta={
                "reservoir_detected": False,
                "tools_called": 0,
                "provider": provider,
                "needs_plant_clarification": True,
                "expanded_content": content_for_model if content_for_model != content else "",
            },
        )
        return {
            "session_id": session_id,
            "response": PRODUCTION_PLANT_CLARIFICATION_REPLY,
            "provider": provider,
            "model": selected_model,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": latency_ms,
            "tools_called": 0,
        }

    denial_message = get_ai_tool_scope_denial_message(user, content_for_model)
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
                "reservoir_detected": detect_reservoir(content_for_model),
                "tools_called": 0,
                "provider": provider,
                "permission_denied": True,
                "expanded_content": content_for_model if content_for_model != content else "",
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

    time_clarification_message = _get_time_clarification_message(content_for_model)
    if time_clarification_message:
        latency_ms = int((time.time() - start_time) * 1000)
        save_exchange(
            user=user,
            session_id=session_id,
            user_message=content,
            assistant_message=time_clarification_message,
            model=selected_model,
            total_tokens=0,
            cost_usd=0,
            tools_called=0,
            latency_ms=latency_ms,
            meta={
                "reservoir_detected": detect_reservoir(content_for_model),
                "tools_called": 0,
                "provider": provider,
                "needs_time_clarification": True,
                "expanded_content": content_for_model if content_for_model != content else "",
            },
        )
        return {
            "session_id": session_id,
            "response": time_clarification_message,
            "provider": provider,
            "model": selected_model,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": latency_ms,
            "tools_called": 0,
        }

    chat_content = {
        "text": content_for_model,
        "history": _history_for_model(user, session_id, content_for_model),
    }

    assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens = _run_openai_chat(
        user=user,
        content=chat_content,
        session_id=session_id,
        provider=provider,
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
    assistant_message = _normalize_missing_data_response(content_for_model, assistant_message)
    cost_usd = _estimate_cost_usd(provider, selected_model, prompt_tokens, completion_tokens)
    latency_ms = int((time.time() - start_time) * 1000)
    meta = {
        "reservoir_detected": detect_reservoir(content_for_model),
        "tools_called": tools_called,
        "provider": provider,
        "expanded_content": content_for_model if content_for_model != content else "",
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


def _run_openai_chat_stream(*, user, content, session_id, provider, model):
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY") or getattr(settings, "DEEPSEEK_API_KEY", None)
        base_url = "https://api.deepseek.com"
        if not api_key:
            raise AiToolsError("Backend chưa cấu hình DEEPSEEK_API_KEY.")
    else:
        api_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
        base_url = None
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

    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        client = OpenAI(api_key=api_key)

    # Lay ngay gio hien tai cua he thong theo timezone cuc bo
    current_date_str = timezone.localtime().strftime("%d/%m/%Y")
    dynamic_system_prompt = (
        f"{SYSTEM_PROMPT}\n\nHôm nay là ngày: {current_date_str} (dùng ngày này làm mốc để xác định 'hôm nay', 'hôm qua', 'ngày nay', 'ngày mai' khi gọi các công cụ)."
    )

    messages = [{"role": "system", "content": dynamic_system_prompt}]
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
            stream=True,
        )
    except Exception as exc:
        provider_error = _as_ai_provider_error(exc)
        if provider_error:
            raise provider_error from exc
        raise

    accumulated_content = ""
    tool_calls_dict = {}
    
    for chunk in response:
        delta = chunk.choices[0].delta if (chunk.choices and len(chunk.choices) > 0) else None
        if not delta:
            continue
        
        if delta.content:
            accumulated_content += delta.content
            yield {"event": "delta", "payload": {"text": delta.content}}
            
        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_calls_dict:
                    tool_calls_dict[idx] = {"id": "", "name": "", "arguments": ""}
                if tc.id:
                    tool_calls_dict[idx]["id"] = tc.id
                if tc.function and tc.function.name:
                    tool_calls_dict[idx]["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    tool_calls_dict[idx]["arguments"] += tc.function.arguments

    if tool_calls_dict:
        # Reconstruct tool calls
        from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall, Function
        
        tool_calls_objs = []
        for idx in sorted(tool_calls_dict.keys()):
            tc_info = tool_calls_dict[idx]
            tool_calls_objs.append(ChatCompletionMessageToolCall(
                id=tc_info["id"],
                type="function",
                function=Function(name=tc_info["name"], arguments=tc_info["arguments"])
            ))
            
        yield {"event": "status", "payload": {"message": "Đang tra cứu dữ liệu vận hành..."}}
        
        tool_calls = _filter_tool_calls(content["text"], tool_calls_objs)
        tool_calls = [_normalize_analysis_tool_call(content["text"], tool_call) for tool_call in tool_calls]
        tool_calls = [_normalize_vinhson_production_tool_call(content["text"], tool_call) for tool_call in tool_calls]
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
            mock_message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in tool_calls_objs
                ]
            }
            messages.append(mock_message)
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
                    stream=True,
                )
            except Exception as exc:
                provider_error = _as_ai_provider_error(exc)
                if provider_error:
                    raise provider_error from exc
                raise
                
            accumulated_content2 = ""
            for chunk in second_response:
                delta = chunk.choices[0].delta if (chunk.choices and len(chunk.choices) > 0) else None
                if delta and delta.content:
                    accumulated_content2 += delta.content
                    yield {"event": "delta", "payload": {"text": delta.content}}
            
            yield {"event": "final_result", "payload": (accumulated_content2, tools_called, 0, 0, 0)}
        else:
            formatted_tool_message = _format_tool_results(tool_results)
            assistant_message = (
                _normalize_missing_data_response(content["text"], formatted_tool_message)
                if formatted_tool_message
                else accumulated_content
            )
            yield {"event": "delta", "payload": {"text": assistant_message}}
            yield {"event": "final_result", "payload": (assistant_message, tools_called, 0, 0, 0)}
    else:
        yield {"event": "final_result", "payload": (accumulated_content, 0, 0, 0, 0)}


def run_ai_chat_stream(*, user, content, session_id=None, provider=None, model=""):
    if not content or not content.strip():
        raise AiToolsError("Noi dung cau hoi khong duoc de trong.")

    provider, selected_model = _resolve_model(provider, model)
    session_id = session_id or str(uuid.uuid4())
    start_time = time.time()

    if _is_nami_greeting(content):
        assistant_message = _build_nami_greeting(user)
        yield {"event": "status", "payload": {"message": "Đang xử lý yêu cầu..."}}
        for chunk in _response_chunks(assistant_message, chunk_size=40):
            yield {"event": "delta", "payload": {"text": chunk}}
            time.sleep(0.01)
            
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
        yield {
            "event": "done",
            "payload": {
                "session_id": session_id,
                "response": assistant_message,
                "provider": provider,
                "model": selected_model,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": latency_ms,
                "tools_called": 0,
            }
        }
        return

    profile = _user_profile(user)
    title = _clean_display_text(getattr(profile, "chuc_danh", "") if profile else "")
    is_leader = is_leadership_title(title)

    menu_history = get_conversation(user, session_id, limit=MODEL_HISTORY_LIMIT)
    actual_water_level_request = get_actual_water_level_request(content, menu_history)
    if actual_water_level_request and not is_leader:
        assistant_message = (
            "Xin lỗi! Chức năng phân tích mực nước hồ thực tế và chênh lệch MNH báo cáo "
            "chỉ dành cho Tổng Giám Đốc/Phó Tổng Giám Đốc."
        )
        yield {"event": "status", "payload": {"message": "Đang xử lý yêu cầu..."}}
        for chunk in _response_chunks(assistant_message, chunk_size=40):
            yield {"event": "delta", "payload": {"text": chunk}}
            time.sleep(0.01)
            
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
                "permission_denied": True,
                "leadership_only": True,
                "leadership_menu_choice": "actual_water_level_report",
            },
        )
        yield {
            "event": "done",
            "payload": {
                "session_id": session_id,
                "response": assistant_message,
                "provider": provider,
                "model": selected_model,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": latency_ms,
                "tools_called": 0,
            }
        }
        return

    def _yield_static_response(data):
        yield {"event": "status", "payload": {"message": "Đang xử lý yêu cầu..."}}
        for chunk in _response_chunks(data.get("response", ""), chunk_size=80):
            yield {"event": "delta", "payload": {"text": chunk}}
            time.sleep(0.01)
        yield {"event": "done", "payload": data}

    if is_leader:
        if actual_water_level_request:
            res_data = actual_water_level_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="direct_request",
                request=actual_water_level_request,
            )
            for ev in _yield_static_response(res_data):
                yield ev
            return
            
        event_statistics_request = get_event_statistics_request(content, menu_history)
        if event_statistics_request:
            res_data = event_statistics_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="direct_request",
                request=event_statistics_request,
            )
            for ev in _yield_static_response(res_data):
                yield ev
            return
            
        direct_report_date = get_three_plant_production_report_date(content)
        if direct_report_date:
            res_data = production_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="direct_request",
                report_date=direct_report_date,
            )
            for ev in _yield_static_response(res_data):
                yield ev
            return
            
        if is_weekly_limit_report_request(content):
            res_data = weekly_limit_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="direct_request",
            )
            for ev in _yield_static_response(res_data):
                yield ev
            return
            
        if has_leadership_production_menu_context(content, menu_history):
            res_data = production_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="menu_choice",
            )
            for ev in _yield_static_response(res_data):
                yield ev
            return
            
        if has_leadership_rainfall_weather_menu_context(content, menu_history):
            res_data = rainfall_weather_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="menu_choice",
            )
            for ev in _yield_static_response(res_data):
                yield ev
            return
            
        if has_leadership_weekly_limit_menu_context(content, menu_history):
            res_data = weekly_limit_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="menu_choice",
            )
            for ev in _yield_static_response(res_data):
                yield ev
            return
            
        if has_leadership_event_menu_context(content, menu_history):
            res_data = event_report_response(
                user=user,
                session_id=session_id,
                content=content,
                provider=provider,
                selected_model=selected_model,
                start_time=start_time,
                source="menu_choice",
            )
            for ev in _yield_static_response(res_data):
                yield ev
            return

    content_for_model = expand_leadership_menu_choice(content, menu_history) if is_leader else content
    content_for_model = _expand_production_clarification_answer(content_for_model, menu_history)

    monthly_plan_request = get_monthly_production_plan_request(content_for_model)
    if monthly_plan_request:
        denial_message = get_ai_tool_scope_denial_message(user, content_for_model)
        if denial_message:
            res_data = {
                "session_id": session_id,
                "response": denial_message,
                "provider": provider,
                "model": selected_model,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "latency_ms": int((time.time() - start_time) * 1000),
                "tools_called": 0,
            }
            save_exchange(user=user, session_id=session_id, user_message=content, assistant_message=denial_message, model=selected_model, total_tokens=0, cost_usd=0, tools_called=0, latency_ms=res_data["latency_ms"], meta={"reservoir_detected": detect_reservoir(content_for_model), "tools_called": 0, "provider": provider, "permission_denied": True, "expanded_content": content_for_model if content_for_model != content else ""})
            for ev in _yield_static_response(res_data):
                yield ev
            return
        monthly_plan_request = _monthly_production_plan_request_for_user(monthly_plan_request, profile)
        res_data = monthly_production_plan_response(
            user=user,
            session_id=session_id,
            content=content,
            provider=provider,
            selected_model=selected_model,
            start_time=start_time,
            source="direct_request",
            request=monthly_plan_request,
        )
        for ev in _yield_static_response(res_data):
            yield ev
        return

    if _production_request_needs_plant_clarification(content_for_model):
        res_data = {
            "session_id": session_id,
            "response": PRODUCTION_PLANT_CLARIFICATION_REPLY,
            "provider": provider,
            "model": selected_model,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": int((time.time() - start_time) * 1000),
            "tools_called": 0,
        }
        save_exchange(user=user, session_id=session_id, user_message=content, assistant_message=PRODUCTION_PLANT_CLARIFICATION_REPLY, model=selected_model, total_tokens=0, cost_usd=0, tools_called=0, latency_ms=res_data["latency_ms"], meta={"reservoir_detected": False, "tools_called": 0, "provider": provider, "needs_plant_clarification": True, "expanded_content": content_for_model if content_for_model != content else ""})
        for ev in _yield_static_response(res_data):
            yield ev
        return

    denial_message = get_ai_tool_scope_denial_message(user, content_for_model)
    if denial_message:
        res_data = {
            "session_id": session_id,
            "response": denial_message,
            "provider": provider,
            "model": selected_model,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": int((time.time() - start_time) * 1000),
            "tools_called": 0,
        }
        save_exchange(user=user, session_id=session_id, user_message=content, assistant_message=denial_message, model=selected_model, total_tokens=0, cost_usd=0, tools_called=0, latency_ms=res_data["latency_ms"], meta={"reservoir_detected": detect_reservoir(content_for_model), "tools_called": 0, "provider": provider, "permission_denied": True, "expanded_content": content_for_model if content_for_model != content else ""})
        for ev in _yield_static_response(res_data):
            yield ev
        return

    time_clarification_message = _get_time_clarification_message(content_for_model)
    if time_clarification_message:
        res_data = {
            "session_id": session_id,
            "response": time_clarification_message,
            "provider": provider,
            "model": selected_model,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": int((time.time() - start_time) * 1000),
            "tools_called": 0,
        }
        save_exchange(user=user, session_id=session_id, user_message=content, assistant_message=time_clarification_message, model=selected_model, total_tokens=0, cost_usd=0, tools_called=0, latency_ms=res_data["latency_ms"], meta={"reservoir_detected": detect_reservoir(content_for_model), "tools_called": 0, "provider": provider, "needs_time_clarification": True, "expanded_content": content_for_model if content_for_model != content else ""})
        for ev in _yield_static_response(res_data):
            yield ev
        return

    chat_content = {
        "text": content_for_model,
        "history": _history_for_model(user, session_id, content_for_model),
    }

    assistant_message = ""
    tools_called = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    
    for stream_event in _run_openai_chat_stream(
        user=user,
        content=chat_content,
        session_id=session_id,
        provider=provider,
        model=selected_model,
    ):
        if stream_event["event"] == "delta":
            yield stream_event
        elif stream_event["event"] == "status":
            yield stream_event
        elif stream_event["event"] == "final_result":
            assistant_message, tools_called, prompt_tokens, completion_tokens, total_tokens = stream_event["payload"]

    if not total_tokens:
        total_tokens = prompt_tokens + completion_tokens

    assistant_message = re.sub(
        r"<!-- NAMI_THERMO_DATA_START.*?NAMI_THERMO_DATA_END -->",
        "",
        assistant_message,
        flags=re.DOTALL
    ).strip()

    assistant_message = sanitize_tool_content(assistant_message)
    assistant_message = _normalize_missing_data_response(content_for_model, assistant_message)
    cost_usd = _estimate_cost_usd(provider, selected_model, prompt_tokens, completion_tokens)
    latency_ms = int((time.time() - start_time) * 1000)
    meta = {
        "reservoir_detected": detect_reservoir(content_for_model),
        "tools_called": tools_called,
        "provider": provider,
        "expanded_content": content_for_model if content_for_model != content else "",
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

    yield {
        "event": "done",
        "payload": {
            "session_id": session_id,
            "response": assistant_message,
            "provider": provider,
            "model": selected_model,
            "total_tokens": total_tokens,
            "cost_usd": float(cost_usd),
            "latency_ms": latency_ms,
            "tools_called": tools_called,
        }
    }

