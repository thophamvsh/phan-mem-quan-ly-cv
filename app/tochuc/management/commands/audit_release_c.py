from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, F, Q

from quanlycatruc.models import (
    ChiTietPhuongAnPhanCongCa,
    LichTrucCa,
    PhamViNhanSuCaTruc,
    ThanhVienKipTruc,
)
from tochuc.models import NhanSu


class Command(BaseCommand):
    help = "Kiểm tra tính toàn vẹn dữ liệu nhân sự cho Release C."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-error",
            action="store_true",
            help="Trả exit code khác 0 nếu phát hiện dữ liệu không hợp lệ.",
        )

    def handle(self, *args, **options):
        duplicate_codes = list(
            NhanSu.objects.exclude(ma_nhan_vien__isnull=True)
            .exclude(ma_nhan_vien="")
            .values("ma_nhan_vien")
            .annotate(so_luong=Count("id"))
            .filter(so_luong__gt=1)
        )
        duplicate_users = list(
            NhanSu.objects.exclude(user__isnull=True)
            .values("user_id")
            .annotate(so_luong=Count("id"))
            .filter(so_luong__gt=1)
        )
        mismatched_departments = NhanSu.objects.exclude(
            bo_phan__don_vi_id=F("don_vi_id")
        ).count()
        missing_plant_scope = NhanSu.objects.filter(
            Q(don_vi__nha_may__isnull=True)
            & Q(don_vi__don_vi_cha__nha_may__isnull=True)
            & Q(
                don_vi__don_vi_cha__don_vi_cha__nha_may__isnull=True
            )
        ).count()

        report = {
            "nhan_su": NhanSu.objects.count(),
            "pham_vi_nhan_su": PhamViNhanSuCaTruc.objects.count(),
            "thanh_vien_kip": ThanhVienKipTruc.objects.count(),
            "chi_tiet_phan_cong": ChiTietPhuongAnPhanCongCa.objects.count(),
            "lich_da_khoa": LichTrucCa.objects.filter(
                trang_thai=LichTrucCa.TrangThai.DA_KHOA
            ).count(),
            "ma_nhan_vien_trung": duplicate_codes,
            "tai_khoan_lien_ket_trung": duplicate_users,
            "sai_quan_he_bo_phan": mismatched_departments,
            "thieu_pham_vi_nha_may": missing_plant_scope,
        }
        for key, value in report.items():
            self.stdout.write(f"{key}: {value}")

        has_errors = bool(
            duplicate_codes
            or duplicate_users
            or mismatched_departments
            or missing_plant_scope
        )
        if has_errors and options["fail_on_error"]:
            raise CommandError(
                "Dữ liệu nhân sự chưa an toàn cho Release C."
            )
        if not has_errors:
            self.stdout.write(
                self.style.SUCCESS("Audit Release C đạt yêu cầu.")
            )
