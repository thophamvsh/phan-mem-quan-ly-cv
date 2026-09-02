from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q

from quanlyvanhanh.models import ThietBi, ThongSoToMay, ThongSoVanHanh
from tochuc.models import BoPhan, DonViToChuc, NhaMay, NhanSu


MODEL_MAPPINGS = (
    ("khovattu", "bang_nha_may", "tochuc", "nhamay"),
    ("quanlycatruc", "donvitochuc", "tochuc", "donvitochuc"),
    ("quanlycatruc", "bophan", "tochuc", "bophan"),
    ("quanlycatruc", "nhansu", "tochuc", "nhansu"),
)


class Command(BaseCommand):
    help = "Kiểm tra ownership, quyền và phạm vi dữ liệu sau khi chuyển sang app tochuc."

    def add_arguments(self, parser):
        parser.add_argument("--fail-on-error", action="store_true")
        parser.add_argument(
            "--strict-factory-scope",
            action="store_true",
            help="Xem bản ghi thiết bị/thông số thiếu nhà máy là lỗi chặn.",
        )

    def handle(self, *args, **options):
        expected_models = (NhaMay, DonViToChuc, BoPhan, NhanSu)
        ownership_errors = [
            model._meta.label
            for model in expected_models
            if model._meta.app_label != "tochuc"
        ]
        relation_errors = NhanSu.objects.exclude(
            bo_phan__don_vi_id=F("don_vi_id")
        ).count()
        missing_staff_scope = NhanSu.objects.filter(
            Q(don_vi__nha_may__isnull=True)
            & Q(don_vi__don_vi_cha__nha_may__isnull=True)
            & Q(don_vi__don_vi_cha__don_vi_cha__nha_may__isnull=True)
        ).count()

        permission_gaps = []
        legacy_content_types = []
        for source_app, source_model, target_app, target_model in MODEL_MAPPINGS:
            source_type = ContentType.objects.filter(
                app_label=source_app,
                model=source_model,
            ).first()
            target_type = ContentType.objects.filter(
                app_label=target_app,
                model=target_model,
            ).first()
            if source_type is not None:
                legacy_content_types.append(f"{source_app}.{source_model}")
            if source_type is None or target_type is None:
                continue
            for source_permission in Permission.objects.filter(
                content_type=source_type
            ).prefetch_related("user_set", "group_set"):
                action = source_permission.codename.split("_", 1)[0]
                target_permission = Permission.objects.filter(
                    content_type=target_type,
                    codename=f"{action}_{target_model}",
                ).first()
                if target_permission is None:
                    permission_gaps.append(source_permission.codename)
                    continue
                missing_users = source_permission.user_set.exclude(
                    pk__in=target_permission.user_set.values("pk")
                ).count()
                missing_groups = source_permission.group_set.exclude(
                    pk__in=target_permission.group_set.values("pk")
                ).count()
                if missing_users or missing_groups:
                    permission_gaps.append(
                        f"{source_permission.codename}: "
                        f"{missing_users} user, {missing_groups} group"
                    )

        factory_scope = {
            "thiet_bi_thieu_nha_may": ThietBi.objects.filter(
                Q(nha_may__isnull=True) | Q(nha_may="")
            ).count(),
            "thong_so_van_hanh_thieu_nha_may": ThongSoVanHanh.objects.filter(
                Q(nha_may__isnull=True) | Q(nha_may="")
            ).count(),
            "thong_so_to_may_thieu_nha_may": ThongSoToMay.objects.filter(
                Q(nha_may__isnull=True) | Q(nha_may="")
            ).count(),
        }
        report = {
            "model_tochuc": [model._meta.label for model in expected_models],
            "bang_du_lieu": [model._meta.db_table for model in expected_models],
            "ownership_sai": ownership_errors,
            "nhan_su_sai_bo_phan": relation_errors,
            "nhan_su_thieu_pham_vi": missing_staff_scope,
            "quyen_chua_chuyen": permission_gaps,
            "content_type_legacy_con_giu": legacy_content_types,
            **factory_scope,
        }
        for key, value in report.items():
            self.stdout.write(f"{key}: {value}")

        blocking_errors = bool(
            ownership_errors
            or relation_errors
            or missing_staff_scope
            or permission_gaps
        )
        scope_warnings = any(factory_scope.values())
        if options["fail_on_error"] and (
            blocking_errors
            or (options["strict_factory_scope"] and scope_warnings)
        ):
            raise CommandError("Chuyển đổi danh mục tổ chức chưa đạt yêu cầu.")
        if not blocking_errors:
            self.stdout.write(self.style.SUCCESS("Ownership và quyền tổ chức đạt yêu cầu."))
        if scope_warnings:
            self.stdout.write(self.style.WARNING(
                "Còn dữ liệu thiếu phạm vi nhà máy; chưa được phép tự động xóa legacy."
            ))
