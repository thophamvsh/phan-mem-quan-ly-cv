import re

from .production_policy import (
    TODAY_PRODUCTION_MISSING_REPLY,
    is_production_question,
    is_today_request,
)
from .text import normalize_text


MISSING_DATA_REPLY = (
    "Dạ, hiện hệ thống chưa có dữ liệu phù hợp cho ngày/khoảng thời gian hoặc thông số này. "
    "Anh/chị có thể thử kiểm tra một ngày khác, rà lại tên nhà máy/thông số cần xem, "
    "hoặc liên hệ kỹ thuật viên để kiểm tra nguồn dữ liệu."
)
MISSING_DATA_CAUSE_REPLY = (
    "Dạ, hiện hệ thống chưa có đủ dữ liệu phù hợp cho ngày/khoảng thời gian hoặc thông số này, "
    "nên em chưa có cơ sở tin cậy để phân tích nguyên nhân. Anh/chị có thể thử kiểm tra một ngày khác, "
    "rà lại tên nhà máy/thông số cần xem, hoặc liên hệ kỹ thuật viên để kiểm tra nguồn dữ liệu."
)


def is_operational_data_or_cause_question(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    return any(
        keyword in normalized
        for keyword in (
            "san luong",
            "luong mua",
            "mua",
            "thong so",
            "du lieu van hanh",
            "qve",
            "muc nuoc",
            "mnh",
            "dung tich",
            "luu luong",
            "cong suat",
            "nhiet do",
            "dien ap",
            "dong dien",
            "nguyen nhan",
            "tai sao",
            "vi sao",
            "phan tich",
            "bat thuong",
            "canh bao",
        )
    )


def is_operational_report_question(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    has_report_intent = any(
        keyword in normalized
        for keyword in (
            "bao cao",
            "du lieu",
            "du lieu van hanh",
            "van hanh",
            "xem",
            "tra cuu",
        )
    )
    has_plant = any(
        keyword in normalized
        for keyword in (
            "song hinh",
            "songhinh",
            "vinh son",
            "vinhson",
            "thuong kon tum",
            "thuongkontum",
            "kon tum",
            "kontum",
        )
    )
    return has_report_intent and has_plant


def is_cause_or_analysis_question(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    return any(
        keyword in normalized
        for keyword in (
            "nguyen nhan",
            "tai sao",
            "vi sao",
            "phan tich",
            "bat thuong",
            "canh bao",
            "danh gia",
            "nhan dinh",
            "khuyen nghi",
        )
    )


def message_is_missing_data_notice(value):
    text = str(value or "").strip()
    if not text:
        return False

    normalized = normalize_text(text)
    has_missing_data_signal = any(
        pattern in normalized
        for pattern in (
            "khong co du lieu",
            "khong tim thay du lieu",
            "chua co du lieu",
            "khong du so lieu",
            "chua co du so lieu",
            "ket qua rong",
            "du lieu rong",
            "no data",
            "not found data",
            "data not found",
            "empty result",
        )
    )
    if not has_missing_data_signal:
        return False

    has_structured_data = (
        "```chart" in normalized
        or "```json-chart" in normalized
        or "```excel" in normalized
        or bool(re.search(r"^\s*\|.+\|\s*$", text, flags=re.MULTILINE))
    )
    if has_structured_data:
        return False

    # Long reports can contain a small missing-data note while still giving useful facts.
    return len(text) <= 1200


def normalize_missing_data_response(user_text, assistant_message):
    if not is_operational_data_or_cause_question(user_text):
        if not (is_operational_report_question(user_text) and is_today_request(user_text)):
            return assistant_message
    if not message_is_missing_data_notice(assistant_message):
        return assistant_message
    if is_today_request(user_text) and (is_production_question(user_text) or is_operational_report_question(user_text)):
        return TODAY_PRODUCTION_MISSING_REPLY
    if is_cause_or_analysis_question(user_text):
        return MISSING_DATA_CAUSE_REPLY
    return MISSING_DATA_REPLY
