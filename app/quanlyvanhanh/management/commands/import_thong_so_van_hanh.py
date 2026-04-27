import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from quanlyvanhanh.models import ThietBi, ThongSoVanHanh

MANDATORY = ["thiet_bi_ma_day_du", "ten_thong_so"]

class Command(BaseCommand):
    help = "Import THÔNG SỐ VẬN HÀNH từ Excel."

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

        created = updated = skipped = 0

        for _, r in df.iterrows():
            tb_code = r["thiet_bi_ma_day_du"].strip()
            key = r["ten_thong_so"].strip()
            if not tb_code or not key:
                skipped += 1
                continue

            tb = ThietBi.objects.filter(ma_day_du=tb_code).first()
            if not tb:
                skipped += 1
                continue

            defaults = dict(
                gia_tri=r.get("gia_tri", "").strip(),
                don_vi=r.get("don_vi", "").strip(),
                gia_tri_toi_thieu=r.get("gia_tri_toi_thieu", "").strip(),
                gia_tri_toi_da=r.get("gia_tri_toi_da", "").strip(),
                ghi_chu=r.get("ghi_chu", "").strip(),
            )
            obj = ThongSoVanHanh.objects.filter(thiet_bi=tb, ten_thong_so=key).first()
            if obj:
                if update:
                    for k, v in defaults.items():
                        setattr(obj, k, v)
                    obj.save()
                    updated += 1
                else:
                    skipped += 1
                continue

            ThongSoVanHanh.objects.create(thiet_bi=tb, ten_thong_so=key, **defaults)
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"OK: tạo {created}, cập nhật {updated}, bỏ qua {skipped}"
        ))
