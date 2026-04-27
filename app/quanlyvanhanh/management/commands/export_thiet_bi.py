import pandas as pd
from django.core.management.base import BaseCommand
from quanlyvanhanh.models import ThietBi

COLS = [
    "ma_day_du","ten","loai","trang_thai","nha_che_tao","nha_cung_cap",
    "nuoc_san_xuat","nha_may","do_uu_tien","so_serial","mo_ta_ky_thuat","thu_tu"
]

class Command(BaseCommand):
    help = "Export THIẾT BỊ ra Excel (lọc theo --subtree prefix)."

    def add_arguments(self, parser):
        parser.add_argument("out_path", help="Đường dẫn file xuất (*.xlsx)")
        parser.add_argument("--subtree", default="", help="Prefix ma_day_du; VD: SH.TB.H1")

    def handle(self, out_path, subtree, **kwargs):
        qs = ThietBi.objects.all().order_by("ma_day_du")
        if subtree:
            qs = qs.filter(ma_day_du__startswith=subtree)

        rows = qs.values(*COLS)
        df = pd.DataFrame(list(rows))
        df.to_excel(out_path, index=False)
        self.stdout.write(self.style.SUCCESS(f"Đã xuất {len(df)} dòng → {out_path}"))
