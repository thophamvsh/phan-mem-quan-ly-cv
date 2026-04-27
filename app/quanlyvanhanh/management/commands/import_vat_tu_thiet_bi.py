import pandas as pd
from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from quanlyvanhanh.models import ThietBi, VatTu, ThietBiVatTu

MANDATORY = ["thiet_bi_ma_day_du", "ma_vat_tu", "ten_vat_tu"]

class Command(BaseCommand):
    help = "Import VẬT TƯ gắn với THIẾT BỊ từ Excel."

    def add_arguments(self, parser):
        parser.add_argument("file_path")
        parser.add_argument("--sheet", default=0)
        parser.add_argument("--update", action="store_true")

    @transaction.atomic
    def handle(self, file_path, sheet, update, **kwargs):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet, dtype=str).fillna("")
        except Exception as e:
            raise CommandError(f"Không đọc được file: {e}")

        for c in MANDATORY:
            if c not in df.columns:
                raise CommandError(f"Thiếu cột: {c}")

        created_link = updated_link = created_mt = skipped = 0

        for _, r in df.iterrows():
            tb_code = r["thiet_bi_ma_day_du"].strip()
            ma_vt = r["ma_vat_tu"].strip()
            ten_vt = r["ten_vat_tu"].strip()
            if not tb_code or not ma_vt or not ten_vt:
                skipped += 1
                continue

            tb = ThietBi.objects.filter(ma_day_du=tb_code).first()
            if not tb:
                skipped += 1
                continue

            vt, created = VatTu.objects.update_or_create(
                ma_vat_tu=ma_vt,
                defaults={
                    "ten_vat_tu": ten_vt,
                    "don_vi_tinh": r.get("don_vi_tinh", "").strip(),
                    "quy_cach": r.get("quy_cach", "").strip(),
                    "nha_che_tao": r.get("nha_che_tao", "").strip(),
                    "nha_cung_cap": r.get("nha_cung_cap", "").strip(),
                }
            )
            if created:
                created_mt += 1

            so_luong = r.get("so_luong", "").strip()
            try:
                so_luong = Decimal(so_luong) if so_luong else Decimal("1")
            except:
                so_luong = Decimal("1")

            link = ThietBiVatTu.objects.filter(thiet_bi=tb, vat_tu=vt).first()
            if link:
                if update:
                    link.so_luong = so_luong
                    link.ghi_chu = r.get("ghi_chu", "").strip()
                    link.save()
                    updated_link += 1
                else:
                    skipped += 1
                continue

            ThietBiVatTu.objects.create(
                thiet_bi=tb, vat_tu=vt, so_luong=so_luong,
                ghi_chu=r.get("ghi_chu", "").strip()
            )
            created_link += 1

        self.stdout.write(self.style.SUCCESS(
            f"OK: tạo vật tư {created_mt}, tạo liên kết {created_link}, cập nhật {updated_link}, bỏ qua {skipped}"
        ))
