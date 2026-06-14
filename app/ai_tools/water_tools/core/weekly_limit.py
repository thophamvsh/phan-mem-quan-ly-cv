from datetime import date, timedelta

from django.utils import timezone


WEEKLY_LIMIT_RESERVOIRS = (
    {
        "key": "songhinh",
        "aliases": ("song hinh", "songhinh", "sh", "sông hinh"),
        "plant_code": "songhinh",
        "name": "Sông Hinh",
        "field": "mucnuoc_gioihan_tuan",
    },
    {
        "key": "vinhson_a",
        "aliases": ("vinh son a", "vinhson a", "vs a", "vsa", "hồ a", "ho a", "vĩnh sơn a"),
        "plant_code": "vinhson",
        "name": "Vĩnh Sơn A",
        "field": "mucnuoc_gioihan_tuan_ho_a",
    },
    {
        "key": "vinhson_b",
        "aliases": ("vinh son b", "vinhson b", "vs b", "vsb", "hồ b", "ho b", "vĩnh sơn b"),
        "plant_code": "vinhson",
        "name": "Vĩnh Sơn B",
        "field": "mucnuoc_gioihan_tuan_ho_b",
    },
    {
        "key": "thuongkontum",
        "aliases": ("thuong kon tum", "thuongkontum", "tkt", "kon tum", "thượng kon tum"),
        "plant_code": "thuongkontum",
        "name": "Thượng Kon Tum",
        "field": "mucnuoc_gioihan_tuan",
    },
)


def _fmt_date(value):
    return value.strftime("%d/%m/%Y") if value else "-"


def _fmt_number(value):
    if value is None:
        return "-"
    return f"{float(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _normalize_text(value):
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _selected_reservoirs(reservoir):
    normalized = _normalize_text(reservoir)
    if not normalized or normalized in {"all", "tat ca", "tất cả"}:
        return list(WEEKLY_LIMIT_RESERVOIRS)
    if normalized in {"vinh son", "vinhson", "vs", "vĩnh sơn"}:
        return [item for item in WEEKLY_LIMIT_RESERVOIRS if item["plant_code"] == "vinhson"]

    selected = []
    for item in WEEKLY_LIMIT_RESERVOIRS:
        if normalized == item["key"] or normalized in {_normalize_text(alias) for alias in item["aliases"]}:
            selected.append(item)
    return selected


def _records_for_week(*, target_date=None, year=None, week_number=None):
    from thongsothuyvan.models import ThongSoThuyVanCaiDat

    if target_date:
        records = list(
            ThongSoThuyVanCaiDat.objects.filter(
                loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
                tuan_bat_dau__lte=target_date,
                tuan_ket_thuc__gte=target_date,
            )
        )
        if records:
            return records

    return list(
        ThongSoThuyVanCaiDat.objects.filter(
            nam=year,
            loai=ThongSoThuyVanCaiDat.LOAI_MNGH_TUAN,
            thang=0,
            tuan=week_number,
        )
    )


def _resolve_week(week_selector, week_number, year, target_date):
    from thongsothuyvan.hydrology_services import get_settings_week_number

    selector = (week_selector or "current").strip().lower()
    resolved_date = _parse_date(target_date)
    if resolved_date is None:
        resolved_date = timezone.localdate()
    if selector == "next":
        resolved_date = resolved_date + timedelta(days=7)

    if selector == "specific":
        resolved_week = int(week_number or 0)
        if resolved_week <= 0:
            raise ValueError("Khi week_selector='specific', cần truyền week_number.")
        resolved_year = int(year or resolved_date.isocalendar()[0])
        return resolved_year, resolved_week, None

    week_start = resolved_date - timedelta(days=resolved_date.weekday())
    resolved_year = week_start.isocalendar()[0]
    resolved_week = get_settings_week_number(resolved_date)
    return resolved_year, resolved_week, resolved_date


def get_weekly_limit_levels(week_selector="current", reservoir="", week_number=None, year=None, target_date=None):
    """
    Return configured weekly limit water levels (MNGH tuần).
    """
    selected = _selected_reservoirs(reservoir)
    if not selected:
        return "Không nhận diện được hồ cần tra MNGH. Có thể hỏi: Sông Hinh, Vĩnh Sơn A, Vĩnh Sơn B, Thượng Kon Tum."

    resolved_year, resolved_week, resolved_date = _resolve_week(week_selector, week_number, year, target_date)
    records = _records_for_week(target_date=resolved_date, year=resolved_year, week_number=resolved_week)
    records_by_plant = {record.nha_may: record for record in records}

    week_starts = [record.tuan_bat_dau for record in records if record.tuan_bat_dau]
    week_ends = [record.tuan_ket_thuc for record in records if record.tuan_ket_thuc]
    week_start = min(week_starts) if week_starts else None
    week_end = max(week_ends) if week_ends else None

    rows = []
    for config in selected:
        record = records_by_plant.get(config["plant_code"])
        value = getattr(record, config["field"], None) if record else None
        rows.append(
            "| {reservoir} | {week} | {period} | {value} |".format(
                reservoir=config["name"],
                week=f"{resolved_week}/{resolved_year}",
                period=f"{_fmt_date(week_start)} - {_fmt_date(week_end)}",
                value=_fmt_number(value),
            )
        )

    title = "### Mực nước giới hạn tuần"
    selector_text = {
        "current": "tuần này",
        "next": "tuần sau",
        "specific": "tuần được hỏi",
    }.get((week_selector or "current").strip().lower(), "tuần này")

    return f"""
{title}

**Kỳ tra cứu:** {selector_text} - tuần {resolved_week}/{resolved_year}

| Hồ | Tuần | Thời gian áp dụng | MNGH tuần (m) |
|----|------|-------------------|---------------|
{chr(10).join(rows)}

**Ghi chú:** Hồ C Vĩnh Sơn không hiển thị vì hiện chưa cấu hình MNGH tuần.
""".strip()
