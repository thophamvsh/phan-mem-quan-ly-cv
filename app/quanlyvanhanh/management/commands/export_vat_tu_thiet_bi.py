import pandas as pd
from django.core.management.base import BaseCommand
from quanlyvanhanh.models import ThietBi, ThietBiVatTu

class Command(BaseCommand):
    help = "Export VẬT TƯ gắn thiết bị ra Excel."

    def add_arguments(self, parser):
        parser.add_argument("out_path")
        parser.add_argument("--subtree", default="", help="Prefix ma_day_du của thiết bị")

    def handle(self, out_path, subtree, **kwargs):
        qs = ThietBiVatTu.objects.select_related("thiet_bi", "vat_tu")
        if subtree:
            qs = qs.filter(thiet_bi__ma_day_du__startswith=subtree)

        data = []
        for link in qs.order_by("thiet_bi__ma_day_du", "vat_tu__ma_vat_tu"):
            data.append({
                "thiet_bi_ma_day_du": link.thiet_bi.ma_day_du,
                "ma_vat_tu": link.vat_tu.ma_vat_tu,
                "ten_vat_tu": link.vat_tu.ten_vat_tu,
                "don_vi_tinh": link.vat_tu.don_vi_tinh,
                "quy_cach": link.vat_tu.quy_cach,
                "nha_che_tao": link.vat_tu.nha_che_tao,
                "nha_cung_cap": link.vat_tu.nha_cung_cap,
                "so_luong": link.so_luong,
                "ghi_chu": link.ghi_chu,
            })

        df = pd.DataFrame(data)
        df.to_excel(out_path, index=False)
        self.stdout.write(self.style.SUCCESS(f"Đã xuất {len(df)} dòng → {out_path}"))
