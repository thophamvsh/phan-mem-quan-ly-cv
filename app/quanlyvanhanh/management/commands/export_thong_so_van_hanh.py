import pandas as pd
from django.core.management.base import BaseCommand
from quanlyvanhanh.models import ThongSoVanHanh

class Command(BaseCommand):
    help = "Export THÔNG SỐ VẬN HÀNH ra Excel."

    def add_arguments(self, parser):
        parser.add_argument("out_path")
        parser.add_argument("--subtree", default="", help="Prefix ma_day_du của thiết bị")

    def handle(self, out_path, subtree, **kwargs):
        qs = ThongSoVanHanh.objects.select_related("thiet_bi")
        if subtree:
            qs = qs.filter(thiet_bi__ma_day_du__startswith=subtree)

        data = []
        for p in qs.order_by("thiet_bi__ma_day_du", "ten_thong_so"):
            data.append({
                "thiet_bi_ma_day_du": p.thiet_bi.ma_day_du,
                "ten_thong_so": p.ten_thong_so,
                "gia_tri": p.gia_tri,
                "don_vi": p.don_vi,
                "gia_tri_toi_thieu": p.gia_tri_toi_thieu,
                "gia_tri_toi_da": p.gia_tri_toi_da,
                "ghi_chu": p.ghi_chu,
            })

        df = pd.DataFrame(data)
        df.to_excel(out_path, index=False)
        self.stdout.write(self.style.SUCCESS(f"Đã xuất {len(df)} dòng → {out_path}"))
