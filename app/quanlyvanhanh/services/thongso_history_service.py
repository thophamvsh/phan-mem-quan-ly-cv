import re
from collections import OrderedDict
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from core.factory_scope import filter_queryset_by_factory
from quanlyvanhanh.models import ThietBi, ThongSoToMay, ThongSoTram110KV, ThongSoVanHanh, NguongThongSo


NUM_RE = re.compile(r"[-+]?\d+(?:[.,\s]\d+)*([.,]\d+)?")
MAX_RANGE_DAYS = 366

SOURCE_CONFIG = {
    "dien": {
        "model": ThongSoVanHanh,
        "value_field": "gia_tri",
        "device_mode": "children",
    },
    "tomay": {
        "model": ThongSoToMay,
        "value_field": "gia_tri",
        "device_mode": "unit_prefix",
    },
    "tram": {
        "model": ThongSoTram110KV,
        "value_field": "gia_tri",
        "device_mode": "children",
    },
}


class HistoryQueryError(ValueError):
    pass


def parse_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return float(Decimal(str(value)))
        except (InvalidOperation, ValueError):
            return None

    raw = str(value).strip()
    if not raw or raw == "-":
        return None

    match = NUM_RE.search(raw)
    if not match:
        return None

    number = match.group(0).replace(" ", "")
    has_dot = "." in number
    has_comma = "," in number

    if has_dot and has_comma:
        decimal_separator = "." if number.rfind(".") > number.rfind(",") else ","
    elif has_comma:
        decimal_separator = ","
    elif has_dot:
        decimal_separator = "."
    else:
        decimal_separator = None

    if decimal_separator:
        thousands_separator = "," if decimal_separator == "." else "."
        number = number.replace(thousands_separator, "")
        number = number.replace(decimal_separator, ".")

    try:
        return float(Decimal(number))
    except (InvalidOperation, ValueError):
        return None


def parse_interval(value):
    if not value:
        return timedelta(hours=1), "1h"

    raw = str(value).strip().lower()
    match = re.fullmatch(r"(\d+)(m|h|d)", raw)
    if not match:
        raise HistoryQueryError("interval khong hop le. Vi du: 30m, 1h, 1d.")

    amount = int(match.group(1))
    unit = match.group(2)
    if amount <= 0:
        raise HistoryQueryError("interval phai lon hon 0.")

    if unit == "m":
        delta = timedelta(minutes=amount)
    elif unit == "h":
        delta = timedelta(hours=amount)
    else:
        delta = timedelta(days=amount)

    if delta < timedelta(minutes=1):
        raise HistoryQueryError("interval toi thieu la 1 phut.")

    return delta, raw


def parse_bound(value, *, is_end=False):
    if not value:
        return None

    raw = str(value).strip()
    dt = parse_datetime(raw)
    if dt:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    day = parse_date(raw)
    if not day:
        raise HistoryQueryError("from/to phai co dinh dang ngay hoac datetime hop le.")

    if is_end:
        dt = datetime.combine(day + timedelta(days=1), time.min)
    else:
        dt = datetime.combine(day, time.min)
    return timezone.make_aware(dt, timezone.get_current_timezone())


def default_range():
    end = timezone.now()
    start = end - timedelta(days=7)
    return start, end


def normalize_range(from_value, to_value):
    start = parse_bound(from_value)
    end = parse_bound(to_value, is_end=True)

    if not start and not end:
        start, end = default_range()
    elif start and not end:
        end = start + timedelta(days=7)
    elif end and not start:
        start = end - timedelta(days=7)

    if start >= end:
        raise HistoryQueryError("from phai nho hon to.")

    if (end - start).days > MAX_RANGE_DAYS:
        raise HistoryQueryError(f"Khoang thoi gian truy van toi da la {MAX_RANGE_DAYS} ngay.")

    return start, end


def resolve_device(user, device_id=None, device_code=None):
    if not (device_id or device_code):
        return None

    queryset = filter_queryset_by_factory(
        ThietBi.objects.all(),
        user,
        "nha_may",
        "string",
    )
    try:
        if device_id:
            return queryset.get(pk=device_id)
        return queryset.get(ma_day_du=device_code)
    except ThietBi.DoesNotExist:
        raise HistoryQueryError("Khong tim thay thiet bi hoac ban khong co quyen xem.")


def apply_device_filter(queryset, source, device):
    if not device:
        return queryset

    mode = SOURCE_CONFIG[source]["device_mode"]
    if mode == "unit_prefix":
        prefix = ".".join(device.ma_day_du.split(".")[:3])
        return queryset.filter(thiet_bi__ma_day_du__startswith=prefix)

    if device.ma_day_du:
        return queryset.filter(
            Q(thiet_bi=device) | Q(thiet_bi__ma_day_du__startswith=f"{device.ma_day_du}.")
        )
    return queryset.filter(thiet_bi=device)


def base_queryset(user, source, start, end, device):
    config = SOURCE_CONFIG.get(source)
    if not config:
        raise HistoryQueryError("source khong hop le. Gia tri hop le: dien, tomay, tram.")

    queryset = config["model"].objects.select_related("thiet_bi")
    queryset = filter_queryset_by_factory(queryset, user, "nha_may", "string")
    queryset = apply_device_filter(queryset, source, device)
    return queryset.filter(thoi_diem_nhap__gte=start, thoi_diem_nhap__lt=end)


def build_metrics(queryset):
    rows = (
        queryset.values(
            "ma_thong_so",
            "ten_thong_so",
            "don_vi",
            "thiet_bi_id",
            "thiet_bi__ten",
            "thiet_bi__ma_day_du",
        )
        .order_by("ma_thong_so", "thiet_bi__ma_day_du")
        .distinct()
    )
    metrics = []
    seen = set()
    for row in rows:
        key = (row["ma_thong_so"], row["thiet_bi_id"])
        if key in seen:
            continue
        seen.add(key)
        metrics.append(
            {
                "metric": row["ma_thong_so"],
                "name": row["ten_thong_so"],
                "unit": row["don_vi"] or "",
                "device": {
                    "id": row["thiet_bi_id"],
                    "ten": row["thiet_bi__ten"],
                    "ma_day_du": row["thiet_bi__ma_day_du"],
                },
            }
        )
    return metrics


def bucket_start(timestamp, start, interval):
    elapsed = timestamp - start
    bucket_index = int(elapsed.total_seconds() // interval.total_seconds())
    return start + (interval * bucket_index)


def format_dt(value):
    if not value:
        return None
    return timezone.localtime(value).isoformat()


def get_metric_thresholds(user, source, metric, device=None, queryset=None):
    # Cấu hình ngưỡng mặc định trả về
    thresholds = {"alarm": None, "trip": None, "rated": None, "min_value": None, "max_value": None}
    if not metric:
        return thresholds

    # 1. Tìm kiếm ngưỡng cấu hình riêng cho thiết bị cụ thể
    if device:
        record = NguongThongSo.objects.filter(thiet_bi=device, ma_thong_so=metric).first()
        if record:
            return {
                "alarm": record.alarm,
                "trip": record.trip,
                "rated": record.rated,
                "min_value": record.min_value,
                "max_value": record.max_value,
            }

    # 2. Tìm kiếm ngưỡng cấu hình chung cấp nhà máy
    # Lấy tên nhà máy thực tế của thiết bị hoặc của user
    from core.factory_scope import get_user_factory_name
    factory_name = None
    if device and device.nha_may:
        factory_name = device.nha_may
    else:
        factory_name = get_user_factory_name(user)

    if factory_name:
        record = NguongThongSo.objects.filter(
            thiet_bi__isnull=True, 
            nha_may__iexact=factory_name, 
            ma_thong_so=metric
        ).first()
        if record:
            return {
                "alarm": record.alarm,
                "trip": record.trip,
                "rated": record.rated,
                "min_value": record.min_value,
                "max_value": record.max_value,
            }

    # Fallback cho trường hợp cũ tìm theo source ("tomay", "dien", "tram")
    record = NguongThongSo.objects.filter(thiet_bi__isnull=True, nha_may=source, ma_thong_so=metric).first()
    if record:
        return {
            "alarm": record.alarm,
            "trip": record.trip,
            "rated": record.rated,
            "min_value": record.min_value,
            "max_value": record.max_value,
        }

    # 3. Tìm kiếm ngưỡng cấu hình chung hệ thống
    record = NguongThongSo.objects.filter(thiet_bi__isnull=True, nha_may="", ma_thong_so=metric).first()
    if record:
        return {
            "alarm": record.alarm,
            "trip": record.trip,
            "rated": record.rated,
            "min_value": record.min_value,
            "max_value": record.max_value,
        }

    # 4. Fallback đặc thù cho nguồn vận hành điện lấy từ dữ liệu thực tế
    if source == "dien" and queryset:
        first_row = queryset.filter(ma_thong_so=metric).exclude(
            Q(gia_tri_toi_da__isnull=True) | Q(gia_tri_toi_da="")
        ).first()
        if first_row:
            try:
                thresholds["trip"] = parse_number(first_row.gia_tri_toi_da)
                thresholds["alarm"] = parse_number(first_row.gia_tri_toi_thieu)
                thresholds["rated"] = parse_number(first_row.gia_tri_thiet_ke)
            except Exception:
                pass

    return thresholds


def calculate_history(user, params):
    source = (params.get("source") or "tomay").strip().lower()
    metric = (params.get("metric") or "").strip()
    device_id = params.get("thiet_bi_id") or params.get("device_id")
    device_code = params.get("thiet_bi_ma") or params.get("device_code")
    interval, interval_label = parse_interval(params.get("interval"))
    start, end = normalize_range(params.get("from"), params.get("to"))
    device = resolve_device(user, device_id, device_code)

    queryset = base_queryset(user, source, start, end, device)
    metrics = build_metrics(queryset)

    if not metric:
        return {
            "source": source,
            "metric": None,
            "unit": "",
            "from": format_dt(start),
            "to": format_dt(end),
            "interval": interval_label,
            "device": (
                {"id": device.id, "ten": device.ten, "ma_day_du": device.ma_day_du}
                if device
                else None
            ),
            "metrics": metrics,
            "thresholds": {"alarm": None, "trip": None, "rated": None},
            "stats": {"min": None, "minAt": None, "max": None, "maxAt": None, "average": None, "count": 0},
            "points": [],
        }

    value_field = SOURCE_CONFIG[source]["value_field"]
    rows = (
        queryset.filter(ma_thong_so=metric)
        .values_list(
            "thoi_diem_nhap",
            value_field,
            "ten_thong_so",
            "don_vi",
            "thiet_bi_id",
            "thiet_bi__ten",
            "thiet_bi__ma_day_du",
        )
        .order_by("thoi_diem_nhap")
    )

    numeric_rows = []
    metric_name = metric
    unit = ""
    metric_device = None

    for timestamp, raw_value, name, row_unit, tb_id, tb_name, tb_code in rows:
        numeric_value = parse_number(raw_value)
        if name:
            metric_name = name
        if row_unit:
            unit = row_unit
        if metric_device is None:
            metric_device = {"id": tb_id, "ten": tb_name, "ma_day_du": tb_code}
        if numeric_value is None or timestamp is None:
            continue
        numeric_rows.append((timestamp, numeric_value))

    stats = {"min": None, "minAt": None, "max": None, "maxAt": None, "average": None, "count": 0}
    if numeric_rows:
        min_timestamp, min_value = min(numeric_rows, key=lambda item: item[1])
        max_timestamp, max_value = max(numeric_rows, key=lambda item: item[1])
        total = sum(value for _, value in numeric_rows)
        stats = {
            "min": min_value,
            "minAt": format_dt(min_timestamp),
            "max": max_value,
            "maxAt": format_dt(max_timestamp),
            "average": total / len(numeric_rows),
            "count": len(numeric_rows),
        }

    buckets = OrderedDict()
    for timestamp, value in numeric_rows:
        local_timestamp = timezone.localtime(timestamp)
        local_start = timezone.localtime(start)
        key = bucket_start(local_timestamp, local_start, interval)
        bucket = buckets.setdefault(key, [])
        bucket.append(value)

    points = [
        {
            "timestamp": bucket_time.isoformat(),
            "value": sum(values) / len(values),
            "count": len(values),
        }
        for bucket_time, values in buckets.items()
    ]

    return {
        "source": source,
        "metric": metric,
        "metricName": metric_name,
        "unit": unit,
        "from": format_dt(start),
        "to": format_dt(end),
        "interval": interval_label,
        "device": metric_device
        or (
            {"id": device.id, "ten": device.ten, "ma_day_du": device.ma_day_du}
            if device
            else None
        ),
        "metrics": metrics,
        "thresholds": get_metric_thresholds(user, source, metric, device, queryset),
        "stats": stats,
        "points": points,
    }
