import re

from .text import has_phrase, normalize_text, normalized_words


TIME_CLARIFICATION_REPLY = (
    "Dạ, anh/chị muốn xem dữ liệu cho thời gian nào ạ? "
    "Vui lòng cho em biết ngày cụ thể, hoặc phạm vi theo tháng/năm/khoảng thời gian "
    "để em tra cứu đúng dữ liệu."
)


PLANT_ALIASES = (
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

OPERATIONAL_INTENT_PHRASES = (
    "bao cao",
    "du lieu",
    "so lieu",
    "du lieu van hanh",
    "van hanh",
    "thong so",
    "thuy van",
    "san luong",
    "san xuat",
    "dien thuong pham",
    "dien dau cuc",
    "muc nuoc",
    "mnh",
    "qve",
    "luu luong",
    "luong mua",
    "mua",
    "dung tich",
    "cong suat",
    "nhiet do",
    "dien ap",
    "dong dien",
    "tan so",
    "do rung",
    "ap luc",
    "muc dau",
    "nac phan ap",
    "mba",
    "may bien ap",
    "tram",
    "to may",
    "h1",
    "h2",
    "t1",
    "t2",
    "t3",
    "t4",
    "canh bao",
    "bat thuong",
    "nguyen nhan",
    "tai sao",
    "vi sao",
    "phan tich",
)

DOCUMENT_INTENT_PHRASES = (
    "quy trinh",
    "quy dinh",
    "tai lieu",
    "van ban",
    "huong dan",
    "noi quy",
)

RELATIVE_TIME_PHRASES = (
    "hom nay",
    "ngay hom nay",
    "hom qua",
    "ngay hom qua",
    "ngay mai",
    "sang nay",
    "chieu nay",
    "toi nay",
    "dem nay",
    "hien tai",
    "luc nay",
    "bay gio",
    "moi nhat",
    "gan day",
    "vua roi",
    "thang nay",
    "thang truoc",
    "thang sau",
    "nam nay",
    "nam truoc",
    "nam sau",
    "tuan nay",
    "tuan truoc",
    "tuan sau",
    "quy nay",
    "quy truoc",
    "quy sau",
    "7 ngay gan nhat",
    "30 ngay gan nhat",
)


def _contains_any_phrase(normalized, phrases):
    return any(has_phrase(normalized, phrase) for phrase in phrases)


def mentions_plant(value):
    normalized = normalized_words(value)
    return _contains_any_phrase(normalized, PLANT_ALIASES)


def has_operational_data_intent(value):
    normalized = normalized_words(value)
    if not normalized:
        return False

    if _contains_any_phrase(normalized, DOCUMENT_INTENT_PHRASES) and not any(
        has_phrase(normalized, phrase)
        for phrase in (
            "bao cao",
            "du lieu",
            "so lieu",
            "thong so",
            "san luong",
            "muc nuoc",
            "qve",
            "luong mua",
            "nhiet do",
            "dien ap",
            "dong dien",
            "cong suat",
        )
    ):
        return False

    return _contains_any_phrase(normalized, OPERATIONAL_INTENT_PHRASES)


def has_explicit_time_reference(value):
    normalized = normalized_words(value)
    raw_normalized = normalize_text(value)

    if _contains_any_phrase(normalized, RELATIVE_TIME_PHRASES):
        return True

    date_patterns = (
        r"\b\d{1,2}\s*[/-]\s*\d{1,2}(?:\s*[/-]\s*\d{2,4})?\b",
        r"\b\d{4}\s*[/-]\s*\d{1,2}\s*[/-]\s*\d{1,2}\b",
    )
    if any(re.search(pattern, raw_normalized) for pattern in date_patterns):
        return True

    word_patterns = (
        r"\bngay\s+\d{1,2}\s+thang\s+\d{1,2}(?:\s+nam\s+\d{2,4})?\b",
        r"\bthang\s+\d{1,2}(?:\s+nam\s+\d{2,4}|\s+\d{2,4})?\b",
        r"\bnam\s+\d{4}\b",
        r"\bquy\s+[1-4](?:\s+nam\s+\d{4})?\b",
        r"\b\d+\s+ngay\s+(?:gan\s+nhat|qua|truoc|toi|sap\s+toi)\b",
        r"\b\d+\s+tuan\s+(?:gan\s+nhat|qua|truoc|toi|sap\s+toi)\b",
        r"\btu\s+ngay\b",
        r"\bden\s+ngay\b",
        r"\btu\s+thang\b",
        r"\bden\s+thang\b",
        r"\bgiai\s+doan\b",
        r"\bkhoang\s+thoi\s+gian\b",
    )
    return any(re.search(pattern, normalized) for pattern in word_patterns)


def plant_data_request_needs_time_clarification(value):
    return (
        mentions_plant(value)
        and has_operational_data_intent(value)
        and not has_explicit_time_reference(value)
    )


def get_time_clarification_message(value):
    if not plant_data_request_needs_time_clarification(value):
        return ""
    return TIME_CLARIFICATION_REPLY
