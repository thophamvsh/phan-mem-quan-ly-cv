import re
from dataclasses import dataclass
from datetime import date, timedelta

from django.utils import timezone

from ..config import LEADERSHIP_TITLES
from ..utils.text import normalize_text, normalize_title


@dataclass(frozen=True)
class EventStatisticsRequest:
    plant_code: str
    plant_name: str
    start_date: date | None = None
    end_date: date | None = None
    all_time: bool = False
    include_details: bool = False
    needs_time_clarification: bool = False


@dataclass(frozen=True)
class ActualWaterLevelRequest:
    start_date: date | None = None
    end_date: date | None = None
    plant_codes: tuple[str, ...] | None = None
    compare_reported: bool = False
    needs_time_clarification: bool = False


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


def _date_from_match(match):
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


def _date_from_parts(day_text, month_text, year_text=None):
    day = int(day_text)
    month = int(month_text)
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


def _extract_event_statistics_period(content):
    normalized = normalize_text(content)
    normalized = re.sub(r"[^a-z0-9\s/-]", " ", normalized)
    normalized = " ".join(normalized.split())
    today = timezone.localdate()

    if any(phrase in normalized for phrase in ("tat ca", "toan bo", "khong gioi han")):
        return None, None, True
    if "hom nay" in normalized or "ngay hom nay" in normalized:
        return today, today, False
    if "hom qua" in normalized or "ngay hom qua" in normalized:
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday, False
    if "thang nay" in normalized:
        start = date(today.year, today.month, 1)
        next_month = date(today.year + int(today.month == 12), 1 if today.month == 12 else today.month + 1, 1)
        return start, next_month - timedelta(days=1), False
    if "nam nay" in normalized:
        return date(today.year, 1, 1), date(today.year, 12, 31), False

    days_match = re.search(r"(\d{1,3})\s*ngay\s*(?:qua|gan nhat)", normalized)
    if days_match:
        days_count = max(int(days_match.group(1)), 1)
        return today - timedelta(days=days_count - 1), today, False

    range_match = re.search(
        r"tu\s+(?:ngay\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\s+"
        r"(?:den|toi|-)\s+(?:ngay\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?",
        normalize_text(content),
    )
    if range_match:
        start = _date_from_parts(range_match.group(1), range_match.group(2), range_match.group(3))
        end = _date_from_parts(range_match.group(4), range_match.group(5), range_match.group(6))
        if start and end:
            return (end, start, False) if start > end else (start, end, False)

    month_match = re.search(r"thang\s+(\d{1,2})(?:[/-](\d{2,4}))?", normalized)
    if month_match:
        month = int(month_match.group(1))
        year = int(month_match.group(2)) if month_match.group(2) else today.year
        if year < 100:
            year += 2000
        if 1 <= month <= 12:
            start = date(year, month, 1)
            next_month = date(year + int(month == 12), 1 if month == 12 else month + 1, 1)
            return start, next_month - timedelta(days=1), False

    year_match = re.search(r"nam\s+(\d{4})", normalized)
    if year_match:
        year = int(year_match.group(1))
        return date(year, 1, 1), date(year, 12, 31), False

    date_match = re.search(
        r"(?:ngay\s*)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?",
        normalize_text(content),
    )
    if date_match:
        target = _date_from_match(date_match)
        if target:
            return target, target, False

    return None, None, False


def _event_statistics_context_from_history(history):
    last_assistant = normalize_text(_last_assistant_message(history))
    if "muon thong ke su kien cua" not in last_assistant:
        return None

    plant_patterns = (
        ("SH", "Sông Hinh", ("song hinh", "songhinh")),
        ("VS", "Vĩnh Sơn", ("vinh son", "vinhson")),
        ("TKT", "Thượng Kon Tum", ("thuong kon tum", "thuongkontum", "kon tum")),
    )
    for plant_code, plant_name, aliases in plant_patterns:
        if any(alias in last_assistant for alias in aliases):
            return plant_code, plant_name
    return None


def get_event_statistics_request(content, history=None):
    normalized = normalize_text(content)
    normalized = re.sub(r"[^a-z0-9\s/-]", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return None

    has_event = "su kien" in normalized or "thiet bi su kien" in normalized
    has_statistics = any(
        keyword in normalized
        for keyword in ("thong ke", "bao cao", "tong hop", "tinh hinh", "dem")
    )
    context_plant = _event_statistics_context_from_history(history)
    if not (has_event and has_statistics) and not context_plant:
        return None

    plant_match = None
    plant_patterns = (
        ("SH", "Sông Hinh", ("song hinh", "songhinh", "sh")),
        ("VS", "Vĩnh Sơn", ("vinh son", "vinhson", "vs")),
        ("TKT", "Thượng Kon Tum", ("thuong kon tum", "thuongkontum", "kon tum", "kontum", "tkt")),
    )
    for plant_code, plant_name, aliases in plant_patterns:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized) for alias in aliases):
            plant_match = (plant_code, plant_name)
            break

    if not plant_match:
        plant_match = context_plant

    if not plant_match:
        return None

    start_date, end_date, all_time = _extract_event_statistics_period(content)
    include_details = any(keyword in normalized for keyword in ("chi tiet", "xem", "link", "duong dan"))
    return EventStatisticsRequest(
        plant_code=plant_match[0],
        plant_name=plant_match[1],
        start_date=start_date,
        end_date=end_date,
        all_time=all_time,
        include_details=include_details,
        needs_time_clarification=not all_time and not (start_date and end_date),
    )


def _actual_water_level_context_from_history(history):
    last_assistant = normalize_text(_last_assistant_message(history))
    has_context = "muc nuoc ho thuc te" in last_assistant or "mnh thuc te" in last_assistant
    asks_time = "thoi gian nao" in last_assistant or "ngay nao" in last_assistant
    return has_context and asks_time


def _actual_water_compare_reported(normalized, history=None):
    has_compare = any(keyword in normalized for keyword in ("so sanh", "chenh lech", "sai lech", "doi chieu"))
    has_reported = "bao cao" in normalized
    if has_compare and has_reported:
        return True

    last_assistant = normalize_text(_last_assistant_message(history))
    return any(
        keyword in last_assistant
        for keyword in ("so sanh", "chenh lech", "mnh bao cao", "qve bao cao")
    )


def _extract_actual_water_plant_codes(normalized):
    matches = []
    plant_patterns = (
        ("songhinh", ("song hinh", "songhinh", "sh")),
        ("vinhson", ("vinh son", "vinhson", "vs", "vsa", "vsb", "vsc")),
        ("thuongkontum", ("thuong kon tum", "thuongkontum", "kon tum", "kontum", "tkt")),
    )
    for plant_code, aliases in plant_patterns:
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized) for alias in aliases):
            matches.append(plant_code)
    return tuple(matches) or None


def get_actual_water_level_request(content, history=None):
    normalized = normalize_text(content)
    normalized = re.sub(r"[^a-z0-9\s/-]", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return None

    has_context = _actual_water_level_context_from_history(history)
    has_water_level = "muc nuoc" in normalized or "mnh" in normalized
    has_qve = "qve" in normalized or "luu luong ve" in normalized or "luu luong nuoc ve" in normalized
    has_actual = "thuc te" in normalized

    # The word "thuc te" is the routing keyword for ThongSoThuyVanThucTe.
    # Without it, let the normal AI/tool flow handle the request.
    is_direct_request = has_actual and (has_water_level or has_qve)
    if not is_direct_request and not has_context:
        return None

    start_date, end_date, all_time = _extract_event_statistics_period(content)
    needs_time_clarification = all_time or not (start_date and end_date)
    return ActualWaterLevelRequest(
        start_date=start_date,
        end_date=end_date,
        plant_codes=_extract_actual_water_plant_codes(normalized),
        compare_reported=_actual_water_compare_reported(normalized, history),
        needs_time_clarification=needs_time_clarification,
    )


def get_three_plant_production_report_date(content):
    normalized = normalize_text(content)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return None

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
