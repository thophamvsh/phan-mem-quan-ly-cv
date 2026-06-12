import copy
import json
import logging
import os
import re
import time
import unicodedata
import uuid
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.utils import timezone

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
HISTORY_TABLE_MAX_LINES = 10
HISTORY_TABLE_KEEP_ROWS = 4
HISTORY_CONTEXT_MAX_CHARS_WHEN_AMBIGUOUS = 5000
CONTEXT_DEPENDENT_KEYWORDS = (
    "tiep",
    "tie p",
    "cai do",
    "cai nay",
    "thong so do",
    "thiet bi do",
    "may do",
    "to may do",
    "mba do",
    "tram do",
    "tren",
    "neu vay",
    "nhu vay",
    "truong hop nay",
    "truong hop do",
    "vua roi",
    "vua phan tich",
    "cau tren",
    "ket qua tren",
    "so voi",
    "so sanh voi",
    "hom qua",
    "ngay truoc",
    "ca truoc",
    "luc truoc",
    "thi sao",
    "con t",
    "con h",
    "con mba",
    "con may",
    "cung ky",
    "tang hay giam",
    "nguyen nhan",
    "khuyen nghi",
    "tai sao",
    "vi sao",
)
STANDALONE_INTENT_KEYWORDS = (
    "quy trinh",
    "quy dinh",
    "van ban",
    "tai lieu",
    "huong dan",
    "tim kiem",
    "tra cuu",
    "muc nuoc",
    "dung tich",
    "luu luong xa",
    "qve",
    "luong mua",
    "san luong",
    "du bao",
)
ENTITY_CONTEXT_KEYWORDS = (
    "song hinh",
    "vinh son",
    "thuong kon tum",
    "kontum",
    "h1",
    "h2",
    "t1",
    "t2",
    "t3",
    "t4",
    "td91",
    "td92",
    "td94",
    "mba",
    "may bien ap",
    "bien ap",
    "tram",
)
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
Khi nguoi dung hoi ve mot thong so van hanh cua to may (vd: nhiet do o huong tuabin, nhiet do o do, luu luong chen truc, cong suat) hoac thong so tram/MBA (vd: nhiet do may bien ap T1, nac phan ap MBA T1, muc dau MBA T1) hoac hoi ve tinh bat thuong/canh bao, ban can dung cong cu get_unit_state_profile de lay ho so trang thai tich hop cua thiet bi do.
Tuyet doi khong dien device_code to may H1/H2 khi nguoi dung hoi MBA/may bien ap T1/T2/T3/T4. Vi du: "nhiet do may bien ap T1 cua Song Hinh" -> device_code="SH.TB.TPP.110.T1", parameter_code="nhiet_do_mba_t1".
Voi Vinh Son, "nhiet do MBA T1" -> device_code="VS.TB.TPP.T1", parameter_code="nhiet_do_cuon_day_t1".
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


def _is_markdown_table_line(line):
    return "|" in line


def _is_markdown_table_heading(line):
    stripped = line.strip()
    return (
        stripped.startswith("#")
        or (stripped.startswith("**") and stripped.endswith("**"))
    )


def _compact_large_markdown_tables(text):
    lines = str(text or "").splitlines()
    output = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if not _is_markdown_table_line(line):
            output.append(line)
            idx += 1
            continue

        table_lines = []
        while idx < len(lines) and _is_markdown_table_line(lines[idx]):
            table_lines.append(lines[idx])
            idx += 1

        if len(table_lines) <= HISTORY_TABLE_MAX_LINES:
            output.extend(table_lines)
            continue

        heading = None
        if output:
            last_nonempty_idx = None
            for out_idx in range(len(output) - 1, -1, -1):
                if output[out_idx].strip():
                    last_nonempty_idx = out_idx
                    break
            if last_nonempty_idx is not None and _is_markdown_table_heading(output[last_nonempty_idx]):
                heading = output.pop(last_nonempty_idx)

        if heading:
            output.append(heading)
        keep_count = min(len(table_lines), 2 + HISTORY_TABLE_KEEP_ROWS)
        output.extend(table_lines[:keep_count])
        omitted = len(table_lines) - keep_count
        output.append(f"[Đã lược bỏ {omitted} dòng bảng dài từ lượt trước]")

    return "\n".join(output)


def _strip_large_markdown_blocks(value):
    text = str(value or "")
    text = re.sub(r"<!-- NAMI_THERMO_DATA_START.*?NAMI_THERMO_DATA_END -->", "", text, flags=re.DOTALL)
    text = re.sub(
        r"\n*####\s*3\.\s*Bảng diễn biến thông số trong các ngày so sánh.*",
        "\n\n[Đã lược bỏ bảng diễn biến 15 ngày và biểu đồ từ lượt trước]",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"```(?:chart|json-chart|excel|excel-report)\n.*?\n```", "[Đã lược bỏ bảng/biểu đồ lớn từ lượt trước]", text, flags=re.DOTALL)
    text = _compact_large_markdown_tables(text)
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


def _question_seems_context_dependent(message):
    normalized = _normalize_text(message)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return False

    words = normalized.split()
    has_context_keyword = any(keyword in normalized for keyword in CONTEXT_DEPENDENT_KEYWORDS)
    has_entity_keyword = any(keyword in normalized for keyword in ENTITY_CONTEXT_KEYWORDS)
    has_standalone_intent = any(keyword in normalized for keyword in STANDALONE_INTENT_KEYWORDS)

    explicit_factory = any(token in normalized for token in ("song hinh", "vinh son", "thuong kon tum", "kontum"))
    explicit_device = any(
        re.search(pattern, normalized)
        for pattern in (
            r"\bh1\b",
            r"\bh2\b",
            r"\bt1\b",
            r"\bt2\b",
            r"\bt3\b",
            r"\bt4\b",
            r"\btd\s*91\b",
            r"\btd\s*92\b",
            r"\btd\s*94\b",
            r"\bmba\b",
            r"\bmay bien ap\b",
            r"\bbien ap\b",
        )
    )

    if has_context_keyword and not (explicit_factory and explicit_device):
        return True
    if explicit_factory and explicit_device:
        return False
    if len(words) <= 6 and not has_entity_keyword and not has_standalone_intent:
        return True
    if has_entity_keyword and not has_standalone_intent:
        return True
    return False


def _history_for_model(user, session_id, message):
    history = get_conversation(user, session_id, limit=MODEL_HISTORY_LIMIT)
    if not history:
        return []

    if _question_seems_context_dependent(message):
        return _compact_history_for_model(history)
    return []


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


LEADERSHIP_TITLES = {
    "giam doc",
    "gd",
    "pho giam doc",
    "pho gd",
    "pgd",
    "pho tong giam doc",
    "pho tong gd",
    "ptgd",
    "tong giam doc",
    "tong gd",
    "tgd",
}


def _normalize_title(value):
    normalized = unicodedata.normalize("NFD", str(value or "").replace("đ", "d").replace("Đ", "D"))
    without_marks = "".join(character for character in normalized if unicodedata.category(character) != "Mn")
    return " ".join(without_marks.casefold().split())


def _is_leadership_title(title):
    normalized = _normalize_title(title)
    return normalized in LEADERSHIP_TITLES or any(
        normalized.startswith(f"{leadership_title} ")
        for leadership_title in LEADERSHIP_TITLES
    )


def _is_leadership_production_menu_response(value):
    normalized = _normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    words = tuple(word for word in normalized.split() if word)
    return words in {
        ("1",),
        ("01",),
        ("muc", "1"),
        ("lua", "chon", "1"),
        ("bao", "cao", "1"),
    }


def _last_assistant_message(history):
    for item in reversed(history or []):
        if item.get("role") == "assistant":
            return str(item.get("content") or "")
    return ""


def _expand_leadership_menu_choice(content, history):
    if not _is_leadership_production_menu_response(content):
        return content

    last_assistant = _last_assistant_message(history)
    if "Báo cáo tình hình sản xuất của 3 nhà máy ngày hôm qua" not in last_assistant:
        return content

    report_date = timezone.localdate() - timedelta(days=1)
    report_date_str = report_date.strftime("%d/%m/%Y")
    return (
        f"Báo cáo tình hình sản xuất của Sông Hinh, Vĩnh Sơn và Thượng Kon Tum ngày {report_date_str}. "
        "Báo cáo sản lượng ngày, tháng và năm; phần trăm đạt kế hoạch ngày, tháng và năm. "
        "Không lập bảng so sánh ngày và cùng kỳ."
    )


LEADERSHIP_PRODUCTION_PLANTS = (
    ("songhinh", "Sông Hinh"),
    ("vinhson", "Vĩnh Sơn"),
    ("thuongkontum", "Thượng Kon Tum"),
)


def _has_leadership_production_menu_context(content, history):
    if not _is_leadership_production_menu_response(content):
        return False
    last_assistant = _last_assistant_message(history)
    return "Báo cáo tình hình sản xuất của 3 nhà máy ngày hôm qua" in last_assistant


def _is_three_plant_yesterday_production_request(content):
    normalized = _normalize_text(content)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return False

    has_report = "bao cao" in normalized
    has_production = "san xuat" in normalized or "san luong" in normalized
    has_three_plants = (
        "3 nha may" in normalized
        or "ba nha may" in normalized
        or all(name in normalized for name in ("song hinh", "vinh son", "thuong kon tum"))
    )
    has_yesterday = "hom qua" in normalized or "ngay hom qua" in normalized
    return has_report and has_production and has_three_plants and has_yesterday


def _sum_record_field(records, field):
    values = []
    for record in records:
        value = getattr(record, field, None)
        if value is not None:
            values.append(float(value))
    if not values:
        return None
    return sum(values)


def _fmt_report_number(value):
    if value is None:
        return "-"
    if abs(value - round(value)) < 0.000001:
        return f"{round(value):,}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _fmt_report_pct(actual, plan):
    if actual is None or plan is None or plan <= 0:
        return "-"
    return f"{actual / plan * 100:.2f}%"


def _format_production_report_row(plant_name, metrics):
    return (
        "| {plant} | {day} | {qc_day} | {pct_day} | {month} | {qc_month} | {pct_month} | {year} | {plan_year} | {pct_year} |"
    ).format(
        plant=plant_name,
        day=_fmt_report_number(metrics["commercial_day"]),
        qc_day=_fmt_report_number(metrics["qc_day"]),
        pct_day=_fmt_report_pct(metrics["commercial_day"], metrics["qc_day"]),
        month=_fmt_report_number(metrics["commercial_month"]),
        qc_month=_fmt_report_number(metrics["qc_month"]),
        pct_month=_fmt_report_pct(metrics["commercial_month"], metrics["qc_month"]),
        year=_fmt_report_number(metrics["commercial_year"]),
        plan_year=_fmt_report_number(metrics["plan_year"]),
        pct_year=_fmt_report_pct(metrics["commercial_year"], metrics["plan_year"]),
    )


def _add_report_totals(totals, metrics):
    for key, value in metrics.items():
        if value is not None:
            totals[key] = (totals.get(key) or 0.0) + value


def _build_leadership_production_report(report_date):
    from thongsothuyvan.models import ThongSoThuyVanCaiDat, ThongsoSanxuat

    plant_codes = [plant_code for plant_code, _ in LEADERSHIP_PRODUCTION_PLANTS]
    monthly_settings = {
        record.nha_may: record.sanluong_kehoach_thang
        for record in ThongSoThuyVanCaiDat.objects.filter(
            nha_may__in=plant_codes,
            nam=report_date.year,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_THANG,
            thang=report_date.month,
        )
        if record.sanluong_kehoach_thang is not None
    }
    annual_settings = {
        record.nha_may: record.sanluong_kehoach_nam
        for record in ThongSoThuyVanCaiDat.objects.filter(
            nha_may__in=plant_codes,
            nam=report_date.year,
            loai=ThongSoThuyVanCaiDat.LOAI_KE_HOACH_NAM,
        )
        if record.sanluong_kehoach_nam is not None
    }

    rows = []
    totals = {
        "commercial_day": None,
        "qc_day": None,
        "commercial_month": None,
        "qc_month": None,
        "commercial_year": None,
        "plan_year": None,
    }

    for plant_code, plant_name in LEADERSHIP_PRODUCTION_PLANTS:
        records = list(
            ThongsoSanxuat.objects.filter(
                nha_may=plant_code,
                thoi_gian__date=report_date,
            ).order_by("cot_c", "thoi_gian")
        )

        if not records:
            rows.append(f"| {plant_name} | Không có dữ liệu | - | - | - | - | - | - | - | - |")
            continue

        commercial_day = _sum_record_field(records, "cot_n")
        qc_day = _sum_record_field(records, "cot_l")
        commercial_month = _sum_record_field(records, "cot_r")
        qc_month = monthly_settings.get(plant_code)
        if qc_month is None:
            qc_month = _sum_record_field(records, "sanluong_kh_thang")
        if qc_month is None:
            qc_month = _sum_record_field(records, "cot_p")
        commercial_year = _sum_record_field(records, "cot_v")
        plan_year = annual_settings.get(plant_code)
        if plan_year is None:
            plan_year = _sum_record_field(records, "cot_w")
        if plan_year is None:
            plan_year = _sum_record_field(records, "cot_t")

        metrics = {
            "commercial_day": commercial_day,
            "qc_day": qc_day,
            "commercial_month": commercial_month,
            "qc_month": qc_month,
            "commercial_year": commercial_year,
            "plan_year": plan_year,
        }
        _add_report_totals(totals, metrics)
        rows.append(_format_production_report_row(plant_name, metrics))

    rows.append(_format_production_report_row("Tổng cộng", totals))

    return f"""
### Báo cáo tình hình sản xuất 3 nhà máy

**Ngày báo cáo:** {report_date.strftime("%d/%m/%Y")}

| Nhà máy | TP ngày | Qc ngày | Đạt ngày | TP tháng | Qc/KH tháng | Đạt tháng | TP năm | KH năm | Đạt năm |
|---------|---------|---------|----------|----------|-------------|-----------|--------|--------|---------|
{chr(10).join(rows)}

**Ghi chú:** Tỷ lệ ngày = TP ngày/Qc ngày; tỷ lệ tháng = TP tháng/QKH tháng trong thông số cài đặt (nếu có); tỷ lệ năm = TP năm/KH năm.
""".strip()


def _production_report_response(*, user, session_id, content, provider, selected_model, start_time, source):
    report_date = timezone.localdate() - timedelta(days=1)
    assistant_message = _build_leadership_production_report(report_date)
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
            "leadership_menu_choice": "production_report",
            "production_report_source": source,
            "report_date": report_date.isoformat(),
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


def _build_nami_greeting(user):
    profile = _user_profile(user)
    title = _clean_display_text(getattr(profile, "chuc_danh", "") if profile else "")
    name = _user_display_name(user)
    recipient = _clean_display_text(f"{title} {name}")
    if _is_leadership_title(title):
        greeting_name = recipient or "ngài"
        return (
            f"Xin chào {greeting_name}! Hôm nay ngài có khỏe không? "
            "Ngài muốn được báo cáo thông tin gì trước?\n"
            "1. Báo cáo tình hình sản xuất của 3 nhà máy ngày hôm qua."
        )
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


def _copy_tool_call_with_arguments(tool_call, arguments):
    return SimpleNamespace(
        id=getattr(tool_call, "id", ""),
        function=SimpleNamespace(
            name=_tool_name(tool_call),
            arguments=json.dumps(arguments, ensure_ascii=False),
        ),
    )


def _detect_transformer_id(normalized_text):
    match = re.search(r"\btd\s*(91|92|94)\b", normalized_text)
    if match:
        return f"TD{match.group(1)}"

    for number in ("1", "2", "3", "4"):
        if re.search(rf"\bt\s*{number}\b", normalized_text):
            return f"T{number}"
    return None


def _detect_transformer_parameter(normalized_text, transformer_id, factory_code):
    transformer_lower = transformer_id.lower()
    if "nac" in normalized_text or "phan ap" in normalized_text or "npa" in normalized_text:
        if factory_code == "SH":
            return f"nac_phan_ap_mba_{transformer_lower}"
        return f"nac_phan_ap_{transformer_lower}"

    if "muc dau" in normalized_text or "dau" in normalized_text:
        if factory_code == "SH":
            return f"muc_dau_mba_{transformer_lower}"
        return f"muc_dau_{transformer_lower}"

    if factory_code == "SH":
        return f"nhiet_do_mba_{transformer_lower}"
    return f"nhiet_do_cuon_day_{transformer_lower}"


def _detect_transformer_device_code(normalized_text):
    mentions_transformer = any(
        token in normalized_text
        for token in ("may bien ap", "bien ap", "mba", "transformer")
    )
    if not mentions_transformer:
        return None, None

    factory_code = "VS" if any(token in normalized_text for token in ("vinh son", "vinhson", "vs")) else "SH"
    transformer_id = _detect_transformer_id(normalized_text)
    if not transformer_id:
        return None, None

    transformer_lower = transformer_id.lower()
    if factory_code == "SH":
        if transformer_id in {"T1", "T2"}:
            device_code = f"SH.TB.TPP.110.{transformer_id}"
        elif transformer_id in {"T3", "T4"}:
            device_code = f"SH.TB.TPP.22.{transformer_id}"
        elif transformer_id == "TD91":
            device_code = "SH.TB.TD.LV.TD1"
        elif transformer_id == "TD94":
            device_code = "SH.TB.TD.LV.TD2"
        else:
            return None, None
    else:
        if transformer_id in {"T1", "T2"}:
            device_code = f"VS.TB.TPP.{transformer_id}"
        elif transformer_id in {"TD91", "TD92"}:
            device_code = f"VS.TB.TD.LV.TD{1 if transformer_id == 'TD91' else 2}"
        else:
            return None, None

    return device_code, _detect_transformer_parameter(normalized_text, transformer_lower.upper(), factory_code)


def _normalize_analysis_tool_call(user_text, tool_call):
    if _tool_name(tool_call).lower() != "get_unit_state_profile":
        return tool_call

    normalized_text = _normalize_text(user_text)
    device_code, parameter_code = _detect_transformer_device_code(normalized_text)
    if not device_code:
        return tool_call

    args = _tool_arguments(tool_call)
    args["device_code"] = device_code
    if parameter_code:
        args["parameter_code"] = parameter_code
    return _copy_tool_call_with_arguments(tool_call, args)


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
        tool_calls = [_normalize_analysis_tool_call(content["text"], tool_call) for tool_call in tool_calls]
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
    tool_calls = [_normalize_analysis_tool_call(content["text"], tool_call) for tool_call in tool_calls]
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

    menu_history = get_conversation(user, session_id, limit=MODEL_HISTORY_LIMIT)
    if _has_leadership_production_menu_context(content, menu_history):
        return _production_report_response(
            user=user,
            session_id=session_id,
            content=content,
            provider=provider,
            selected_model=selected_model,
            start_time=start_time,
            source="menu_choice",
        )
    if _is_three_plant_yesterday_production_request(content):
        return _production_report_response(
            user=user,
            session_id=session_id,
            content=content,
            provider=provider,
            selected_model=selected_model,
            start_time=start_time,
            source="direct_request",
        )

    content_for_model = _expand_leadership_menu_choice(content, menu_history)

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

    chat_content = {
        "text": content_for_model,
        "history": _history_for_model(user, session_id, content_for_model),
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
