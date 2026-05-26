from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, Iterable, List, Optional

from django.utils import timezone


class DbBackedWorksheet:
    def __init__(self, title: str, rows_factory: Callable[[], List[List[str]]]):
        self.title = title
        self._rows_factory = rows_factory

    def get_all_values(self) -> List[List[str]]:
        return self._rows_factory()


class DbBackedSpreadsheet:
    def __init__(self, title: str, worksheets: Iterable[DbBackedWorksheet]):
        self.title = title
        self._worksheets = list(worksheets)

    def worksheets(self) -> List[DbBackedWorksheet]:
        return list(self._worksheets)

    def worksheet(self, title: str) -> DbBackedWorksheet:
        for worksheet in self._worksheets:
            if worksheet.title == title:
                return worksheet
        raise KeyError(title)


def _fmt(value) -> str:
    if value is None:
        return ""
    return str(value)


def _date_key(value):
    if not value:
        return None
    if hasattr(value, "date"):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.date()
    return value


def _latest_by_created_at(model) -> Dict[object, object]:
    rows: Dict[object, object] = {}
    for item in model.objects.all().order_by("created_at"):
        key = _date_key(getattr(item, "created_at", None))
        if key:
            rows[key] = item
    return rows


def _reservoir_code(value: Optional[str]) -> str:
    text = (value or "").upper()
    if "B" in text:
        return "B"
    if "C" in text:
        return "C"
    return "A"


def _stats_header() -> List[List[str]]:
    return [
        ["Ngay", "MNH A/SH", "MNH B", "MNH C", "Qve A/SH", "Qve B", "Qve C"],
        ["Date", "Water A/SH", "Water B", "Water C", "Qve A/SH", "Qve B", "Qve C"],
    ]


def build_songhinh_stats_rows() -> List[List[str]]:
    from thongsothuyvan.models import SonghinhMnh, ThongsoSanxuat

    mnh_by_date = _latest_by_created_at(SonghinhMnh)
    rows = _stats_header()

    records = ThongsoSanxuat.objects.filter(nha_may="songhinh").order_by("thoi_gian")
    for record in records:
        day = _date_key(record.thoi_gian)
        if not day:
            continue
        mnh_record = mnh_by_date.get(day)
        water_level = getattr(mnh_record, "Mucnuoc", None) if mnh_record else record.cot_g

        row = [""] * 7
        row[0] = day.strftime("%d/%m/%Y")
        row[1] = _fmt(water_level)
        row[5] = _fmt(record.cot_i)
        rows.append(row)

    return rows


def build_vinhson_stats_rows() -> List[List[str]]:
    from thongsothuyvan.models import (
        ThongsoSanxuat,
        Vinhson_HoA,
        Vinhson_HoB,
        Vinhson_Hoc,
    )

    mnh_maps = {
        "A": _latest_by_created_at(Vinhson_HoA),
        "B": _latest_by_created_at(Vinhson_HoB),
        "C": _latest_by_created_at(Vinhson_Hoc),
    }
    by_date = defaultdict(lambda: [""] * 7)

    records = ThongsoSanxuat.objects.filter(nha_may="vinhson").order_by("thoi_gian", "cot_c")
    for record in records:
        day = _date_key(record.thoi_gian)
        if not day:
            continue

        row = by_date[day]
        row[0] = day.strftime("%d/%m/%Y")

        code = _reservoir_code(record.cot_c)
        idx = {"A": 0, "B": 1, "C": 2}[code]
        mnh_record = mnh_maps[code].get(day)
        water_level = getattr(mnh_record, "Mucnuoc", None) if mnh_record else record.cot_g
        row[1 + idx] = _fmt(water_level)
        row[4 + idx] = _fmt(record.cot_i)

        if record.mucnuoc_thuongluu_ho_b is not None:
            row[2] = _fmt(record.mucnuoc_thuongluu_ho_b)
        if record.mucnuoc_thuongluu_ho_c is not None:
            row[3] = _fmt(record.mucnuoc_thuongluu_ho_c)
        if record.luuluong_ve_ho_b is not None:
            row[5] = _fmt(record.luuluong_ve_ho_b)
        if record.luuluong_ve_ho_c is not None:
            row[6] = _fmt(record.luuluong_ve_ho_c)

    rows = _stats_header()
    for day in sorted(by_date):
        rows.append(by_date[day])
    return rows


def make_songhinh_stats_spreadsheet() -> DbBackedSpreadsheet:
    return DbBackedSpreadsheet(
        title="DB Stats - Song Hinh",
        worksheets=[DbBackedWorksheet("Thong ke", build_songhinh_stats_rows)],
    )


def make_vinhson_stats_spreadsheet() -> DbBackedSpreadsheet:
    return DbBackedSpreadsheet(
        title="DB Stats - Vinh Son",
        worksheets=[DbBackedWorksheet("Thong ke", build_vinhson_stats_rows)],
    )
