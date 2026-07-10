import re

from ..storage import get_conversation
from .text import normalize_text


MODEL_HISTORY_LIMIT = 8
MODEL_HISTORY_CHAR_BUDGET = 12000
MODEL_USER_HISTORY_MAX_CHARS = 1200
MODEL_ASSISTANT_HISTORY_MAX_CHARS = 2600
HISTORY_TABLE_MAX_LINES = 10
HISTORY_TABLE_KEEP_ROWS = 4

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


def is_markdown_table_line(line):
    return "|" in line


def is_markdown_table_heading(line):
    stripped = line.strip()
    return (
        stripped.startswith("#")
        or (stripped.startswith("**") and stripped.endswith("**"))
    )


def compact_large_markdown_tables(text):
    lines = str(text or "").splitlines()
    output = []
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if not is_markdown_table_line(line):
            output.append(line)
            idx += 1
            continue

        table_lines = []
        while idx < len(lines) and is_markdown_table_line(lines[idx]):
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
            if last_nonempty_idx is not None and is_markdown_table_heading(output[last_nonempty_idx]):
                heading = output.pop(last_nonempty_idx)

        if heading:
            output.append(heading)
        keep_count = min(len(table_lines), 2 + HISTORY_TABLE_KEEP_ROWS)
        output.extend(table_lines[:keep_count])
        omitted = len(table_lines) - keep_count
        output.append(f"[Đã lược bỏ {omitted} dòng bảng dài từ lượt trước]")

    return "\n".join(output)


def strip_large_markdown_blocks(value):
    text = str(value or "")
    text = re.sub(r"<!-- NAMI_THERMO_DATA_START.*?NAMI_THERMO_DATA_END -->", "", text, flags=re.DOTALL)
    text = re.sub(
        r"\n*####\s*3\.\s*Bảng diễn biến thông số trong các ngày so sánh.*",
        "\n\n[Đã lược bỏ bảng diễn biến 15 ngày và biểu đồ từ lượt trước]",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"```(?:chart|json-chart|excel|excel-report)\n.*?\n```", "[Đã lược bỏ bảng/biểu đồ lớn từ lượt trước]", text, flags=re.DOTALL)
    text = compact_large_markdown_tables(text)
    return text.strip()


def truncate_text(value, max_chars):
    text = strip_large_markdown_blocks(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[đã rút gọn nội dung cũ để tránh vượt giới hạn token]"


def compact_history_for_model(history):
    compacted = []
    total_chars = 0
    for item in reversed(history or []):
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        max_chars = MODEL_USER_HISTORY_MAX_CHARS if role == "user" else MODEL_ASSISTANT_HISTORY_MAX_CHARS
        content = truncate_text(item.get("content", ""), max_chars)
        if not content:
            continue
        if total_chars + len(content) > MODEL_HISTORY_CHAR_BUDGET and compacted:
            break
        compacted.append({"role": role, "content": content})
        total_chars += len(content)
    return list(reversed(compacted))


def question_seems_context_dependent(message):
    normalized = normalize_text(message)
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


def history_for_model(user, session_id, message):
    history = get_conversation(user, session_id, limit=MODEL_HISTORY_LIMIT)
    if not history:
        return []

    if question_seems_context_dependent(message):
        return compact_history_for_model(history)
    return []
