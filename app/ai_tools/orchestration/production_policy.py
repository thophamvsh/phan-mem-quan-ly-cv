import re

from django.utils import timezone

from .text import has_phrase, normalized_words


PRODUCTION_PLANT_CLARIFICATION_REPLY = (
    "Dạ, anh/chị muốn xem báo cáo sản lượng của nhà máy nào ạ? "
    "Vui lòng cho em biết Sông Hinh, Vĩnh Sơn, Thượng Kon Tum, hoặc báo cáo tổng hợp 3 nhà máy."
)
TODAY_PRODUCTION_MISSING_REPLY = (
    "Dạ, hiện dữ liệu vận hành/sản lượng ngày hôm nay thường chưa có vì hệ thống chỉ có số liệu đã chốt đến D-1. "
    "Anh/chị vui lòng hỏi báo cáo ngày hôm qua hoặc chọn một ngày đã chốt dữ liệu ạ."
)


def is_production_question(value):
    normalized = normalized_words(value)
    return any(
        phrase in normalized
        for phrase in (
            "san luong",
            "san xuat",
            "dien thuong pham",
            "dien dau cuc",
            "commercial output",
            "production",
        )
    )


def mentions_specific_production_scope(value):
    normalized = normalized_words(value)
    if not normalized:
        return False

    plant_aliases = (
        "song hinh",
        "songhinh",
        "sh",
        "vinh son",
        "vinhson",
        "vs",
        "vsa",
        "vsb",
        "vsc",
        "thuong kon tum",
        "thuongkontum",
        "kon tum",
        "kontum",
        "tkt",
    )
    if any(has_phrase(normalized, alias) for alias in plant_aliases):
        return True

    three_plant_phrases = (
        "3 nha may",
        "ba nha may",
        "tong hop 3 nha may",
        "tong hop ba nha may",
        "tat ca nha may",
        "toan bo nha may",
    )
    return any(phrase in normalized for phrase in three_plant_phrases)


def production_request_needs_plant_clarification(value):
    if not is_production_question(value):
        return False
    return not mentions_specific_production_scope(value)


def production_clarification_was_last_answer(history):
    for item in reversed(history or []):
        if item.get("role") != "assistant":
            continue
        normalized = normalized_words(item.get("content", ""))
        return (
            "muon xem bao cao san luong cua nha may nao" in normalized
            or normalized_words(PRODUCTION_PLANT_CLARIFICATION_REPLY) in normalized
        )
    return False


def last_user_production_question(history):
    for item in reversed(history or []):
        if item.get("role") == "user" and is_production_question(item.get("content", "")):
            return str(item.get("content") or "")
    return ""


def production_scope_from_text(value):
    normalized = normalized_words(value)
    if not normalized:
        return ""
    if any(phrase in normalized for phrase in ("3 nha may", "ba nha may", "tong hop", "tat ca", "toan bo")):
        return "tổng hợp 3 nhà máy"
    if any(has_phrase(normalized, alias) for alias in ("song hinh", "songhinh", "sh")):
        return "Sông Hinh"
    if any(has_phrase(normalized, alias) for alias in ("vinh son", "vinhson", "vs", "vsa", "vsb", "vsc")):
        return "Vĩnh Sơn"
    if any(has_phrase(normalized, alias) for alias in ("thuong kon tum", "thuongkontum", "kon tum", "kontum", "tkt")):
        return "Thượng Kon Tum"
    return ""


def expand_production_clarification_answer(content, history):
    if not production_clarification_was_last_answer(history):
        return content
    if is_production_question(content):
        return content

    scope = production_scope_from_text(content)
    if not scope:
        return content

    previous_question = last_user_production_question(history)
    if not previous_question:
        return content

    if scope == "tổng hợp 3 nhà máy":
        return f"{previous_question} Báo cáo tổng hợp 3 nhà máy."
    return f"{previous_question} Nhà máy: {scope}."


def is_today_request(value):
    normalized = normalized_words(value)
    if "hom nay" in normalized or "ngay hom nay" in normalized:
        return True

    today = timezone.localdate()
    for match in re.finditer(r"(?:ngay\s*)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", normalized):
        day = int(match.group(1))
        month = int(match.group(2))
        year_text = match.group(3)
        year = today.year
        if year_text:
            year = int(year_text)
            if year < 100:
                year += 2000
        if day == today.day and month == today.month and year == today.year:
            return True
    return False
