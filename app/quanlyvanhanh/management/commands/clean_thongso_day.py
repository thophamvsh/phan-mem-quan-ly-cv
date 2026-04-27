from datetime import datetime, time
import re
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from quanlyvanhanh.models import ThongSoVanHanh


NUM_RE = re.compile(r"[-+]?\d+(?:[.,\s]\d+)*([.,]\d+)?")


def parse_vi_number(s):
    if s is None:
        return None
    if isinstance(s, (int, float, Decimal)):
        try:
            return Decimal(str(s))
        except InvalidOperation:
            return None
    s = str(s).strip()
    if not s:
        return None
    m = NUM_RE.search(s)
    if not m:
        return None
    s = m.group(0)
    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
    elif has_comma:
        dec = ","
    elif has_dot:
        dec = "."
    else:
        dec = None
    s = s.replace(" ", "")
    if dec:
        other = "," if dec == "." else "."
        s = s.replace(other, "")
        s = s.replace(dec, ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


class Command(BaseCommand):
    help = "Clean 'gia_tri' to numeric for a day within a time window (e.g., 00:00-10:00)."

    def add_arguments(self, parser):
        parser.add_argument("--date", required=True, help="YYYY-MM-DD")
        parser.add_argument("--start", default="00:00", help="HH:MM, default 00:00")
        parser.add_argument("--end", default="10:00", help="HH:MM, default 10:00")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        ngay = datetime.fromisoformat(opts["date"]).date()
        start_h, start_m = map(int, opts["start"].split(":"))
        end_h, end_m = map(int, opts["end"].split(":"))
        tz = timezone.get_current_timezone()
        start_dt = timezone.make_aware(datetime.combine(ngay, time(start_h, start_m)), tz)
        end_dt = timezone.make_aware(datetime.combine(ngay, time(end_h, end_m)), tz)

        # Lấy theo ngày (ngay_nhap hoặc thoi_diem_nhap__date) và trong khoảng thời gian chỉ định
        qs = (
            ThongSoVanHanh.objects.filter(Q(ngay_nhap=ngay) | Q(thoi_diem_nhap__date=ngay))
            .filter(thoi_diem_nhap__gte=start_dt, thoi_diem_nhap__lt=end_dt)
            .only("id", "gia_tri")
        )

        total = qs.count()
        fixed = 0
        nulled = 0
        for ts in qs.iterator():
            num = parse_vi_number(ts.gia_tri)
            if num is None:
                new_val = None
                nulled += 1
            else:
                # chuẩn hóa dạng số (decimal -> string) để tránh lệch schema
                new_val = str(num)
                fixed += 1
            if not opts["dry_run"]:
                ThongSoVanHanh.objects.filter(pk=ts.id).update(gia_tri=new_val)

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleaned date={ngay} window={opts['start']}-{opts['end']}: total={total}, numeric_set={fixed}, nulled={nulled}"
            )
        )


