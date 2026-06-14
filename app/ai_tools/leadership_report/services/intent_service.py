import re
from datetime import date, timedelta

from django.utils import timezone

from ..config import LEADERSHIP_TITLES
from ..utils.text import normalize_text, normalize_title


def is_leadership_title(title):
    normalized = normalize_title(title)
    return normalized in LEADERSHIP_TITLES or any(
        normalized.startswith(f"{leadership_title} ")
        for leadership_title in LEADERSHIP_TITLES
    )


def _is_leadership_production_menu_response(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    words = tuple(word for word in normalized.split() if word)
    return words in {
        ("1",),
        ("01",),
        ("muc", "1"),
        ("lua", "chon", "1"),
        ("bao", "cao", "1"),
    }


def _is_leadership_rainfall_weather_menu_response(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    words = tuple(word for word in normalized.split() if word)
    return words in {
        ("2",),
        ("02",),
        ("muc", "2"),
        ("lua", "chon", "2"),
        ("bao", "cao", "2"),
    }


def _is_leadership_weekly_limit_menu_response(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    words = tuple(word for word in normalized.split() if word)
    return words in {
        ("3",),
        ("03",),
        ("muc", "3"),
        ("lua", "chon", "3"),
        ("bao", "cao", "3"),
    }


def _last_assistant_message(history):
    for item in reversed(history or []):
        if item.get("role") == "assistant":
            return str(item.get("content") or "")
    return ""


LEADERSHIP_REPORT_INDICATORS = [
    "Báo cáo tình hình sản xuất của 3 nhà máy ngày hôm qua",
    "Báo cáo tình hình sản xuất 3 nhà máy",
    "Tổng hợp lượng mưa các trạm 7 ngày gần nhất",
    "Tổng hợp lượng mưa và dự báo thời tiết",
    "Mực nước giới hạn tuần và phân tích",
    "Tình hình thiết bị sự kiện của 3 nhà máy",
    "Tình hình thiết bị sự kiên của 3 nhà may",
    "Chào",
]


def _has_leadership_context(history):
    last_assistant = _last_assistant_message(history)
    return any(indicator in last_assistant for indicator in LEADERSHIP_REPORT_INDICATORS)


def expand_leadership_menu_choice(content, history):
    if not _is_leadership_production_menu_response(content):
        return content

    if not _has_leadership_context(history):
        return content

    report_date = timezone.localdate() - timedelta(days=1)
    report_date_str = report_date.strftime("%d/%m/%Y")
    return (
        f"Báo cáo tình hình sản xuất của Sông Hinh, Vĩnh Sơn và Thượng Kon Tum ngày {report_date_str}. "
        "Báo cáo sản lượng ngày, tháng và năm; phần trăm đạt kế hoạch ngày, tháng và năm. "
        "Không lập bảng so sánh ngày và cùng kỳ."
    )


def has_leadership_production_menu_context(content, history):
    if not _is_leadership_production_menu_response(content):
        return False
    return _has_leadership_context(history)


def has_leadership_rainfall_weather_menu_context(content, history):
    if not _is_leadership_rainfall_weather_menu_response(content):
        return False
    return _has_leadership_context(history)


def has_leadership_weekly_limit_menu_context(content, history):
    if not _is_leadership_weekly_limit_menu_response(content):
        return False
    return _has_leadership_context(history)


def is_three_plant_yesterday_production_request(content):
    return get_three_plant_production_report_date(content) is not None


def _extract_report_date(content):
    normalized = normalize_text(content)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    if "hom qua" in normalized or "ngay hom qua" in normalized:
        return timezone.localdate() - timedelta(days=1)

    match = re.search(
        r"(?:ngay\s*)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?",
        normalize_text(content),
    )
    if not match:
        return None

    day = int(match.group(1))
    month = int(match.group(2))
    year_text = match.group(3)
    if year_text:
        year = int(year_text)
        if year < 100:
            year += 2000
    else:
        year = timezone.localdate().year

    try:
        return date(year, month, day)
    except ValueError:
        return None


def get_three_plant_production_report_date(content):
    normalized = normalize_text(content)
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
    if not (has_report and has_production and has_three_plants):
        return None
    return _extract_report_date(content)


def is_weekly_limit_report_request(content):
    normalized = normalize_text(content)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return False

    has_report_intent = "bao cao" in normalized or "phan tich" in normalized or "danh gia" in normalized
    has_weekly_limit = (
        "muc nuoc gioi han tuan" in normalized
        or "mngh tuan" in normalized
        or ("gioi han tuan" in normalized and "muc nuoc" in normalized)
    )
    return has_report_intent and has_weekly_limit


def _is_leadership_event_menu_response(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    words = tuple(word for word in normalized.split() if word)
    return words in {
        ("4",),
        ("04",),
        ("muc", "4"),
        ("lua", "chon", "4"),
        ("bao", "cao", "4"),
        ("thiet", "bi", "su", "kien"),
        ("su", "kien", "thiet", "bi"),
        ("tinh", "hinh", "thiet", "bi"),
    }


def has_leadership_event_menu_context(content, history):
    if not _is_leadership_event_menu_response(content):
        return False
    return _has_leadership_context(history)
