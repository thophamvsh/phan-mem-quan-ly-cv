import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from quanlyvanhanh.models import ThietBi

MANDATORY_COLS = ["ma_day_du", "ten"]

def parent_code(full_code: str) -> str | None:
    return full_code.rsplit(".", 1)[0] if "." in full_code else None

def leaf_code(full_code: str, parent_full: str | None) -> str:
    if not parent_full:
        return full_code
    return full_code.split(parent_full + ".", 1)[-1]

class Command(BaseCommand):
    help = "Import danh mục THIẾT BỊ từ Excel (cột tiếng Việt không dấu)."

    def add_arguments(self, parser):
        parser.add_argument("file_path", help="Đường dẫn file Excel (*.xlsx)")
        parser.add_argument("--sheet", default=0, help="Tên sheet hoặc index (mặc định 0)")
        parser.add_argument("--update", action="store_true", help="Cập nhật nếu đã tồn tại")

    @transaction.atomic
    def handle(self, file_path, sheet, update, **kwargs):
        try:
            df = pd.read_excel(file_path, sheet_name=sheet, dtype=str).fillna("")
        except Exception as e:
            raise CommandError(f"Không đọc được file: {e}")

        for c in MANDATORY_COLS:
            if c not in df.columns:
                raise CommandError(f"Thiếu cột bắt buộc: {c}")

        # chuẩn hoá & sắp theo độ sâu
        df["depth"] = df["ma_day_du"].str.count(r"\.")
        df = df.sort_values("depth").reset_index(drop=True)

        created = updated = skipped = 0

        for _, r in df.iterrows():
            ma_day_du = r["ma_day_du"].strip()
            ten = r["ten"].strip()
            if not ma_day_du or not ten:
                skipped += 1
                continue

            ma_cha = parent_code(ma_day_du)
            cha = ThietBi.objects.filter(ma_day_du=ma_cha).first() if ma_cha else None
            ma = leaf_code(ma_day_du, ma_cha)

            defaults = dict(
                ten=ten,
                ma=ma,
                cha=cha,
                loai=r.get("loai", "").strip(),
                trang_thai=r.get("trang_thai", "").strip(),
                nha_che_tao=r.get("nha_che_tao", "").strip(),
                nha_cung_cap=r.get("nha_cung_cap", "").strip(),
                nuoc_san_xuat=r.get("nuoc_san_xuat", "").strip(),
                nha_may=r.get("nha_may", "").strip(),
                do_uu_tien=int(r.get("do_uu_tien", 0) or 0),
                so_serial=r.get("so_serial", "").strip(),
                mo_ta_ky_thuat=r.get("mo_ta_ky_thuat", "").strip(),
                thu_tu=int(r.get("thu_tu", 0) or 0),
            )

            obj = ThietBi.objects.filter(ma_day_du=ma_day_du).first()
            if obj:
                if update:
                    for k, v in defaults.items():
                        setattr(obj, k, v)
                    obj.save()
                    updated += 1
                else:
                    skipped += 1
                continue

            ThietBi.objects.create(ma_day_du=ma_day_du, **defaults)
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"OK: tạo {created}, cập nhật {updated}, bỏ qua {skipped}"
        ))
