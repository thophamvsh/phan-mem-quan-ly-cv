from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from core.models import UserProfile
from khovattu.models import Bang_nha_may
from quanlyvanhanh.models import ThietBi, ThongSoToMay, ThongSoVanHanh


class Command(BaseCommand):
    help = (
        "Audit and optionally normalize text nha_may values used by "
        "quanlyvanhanh factory scoping."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply safe normalization changes. Without this flag the command only reports.",
        )
        parser.add_argument(
            "--default-factory",
            dest="default_factory",
            default=None,
            help=(
                "Optional Bang_nha_may.ma_nha_may used to fill blank ThietBi.nha_may. "
                "Blank ThongSo rows are normally inferred from their ThietBi."
            ),
        )

    def handle(self, *args, **options):
        self.apply = options["apply"]
        self.default_factory_code = options["default_factory"]
        self.factories = list(Bang_nha_may.objects.all().order_by("ma_nha_may"))
        self.factory_lookup = self._build_factory_lookup(self.factories)

        self.stdout.write(self.style.MIGRATE_HEADING("Factory scope audit: quanlyvanhanh"))
        self._print_factories()
        self._print_profiles()
        self._audit_model_text_field(ThietBi, "nha_may", "ThietBi.nha_may")
        self._audit_model_text_field(ThongSoVanHanh, "nha_may", "ThongSoVanHanh.nha_may")
        self._audit_model_text_field(ThongSoToMay, "nha_may", "ThongSoToMay.nha_may")
        self._audit_thong_so_links(ThongSoVanHanh, "ThongSoVanHanh")
        self._audit_thong_so_links(ThongSoToMay, "ThongSoToMay")

        if self.apply:
            self.stdout.write(self.style.WARNING("Apply mode enabled. Normalizing data..."))
            self._normalize_thiet_bi()
            self._normalize_thong_so(ThongSoVanHanh, "ThongSoVanHanh")
            self._normalize_thong_so(ThongSoToMay, "ThongSoToMay")
            self.stdout.write(self.style.SUCCESS("Normalization completed."))
        else:
            self.stdout.write("Dry-run only. Re-run with --apply to write safe changes.")

    def _build_factory_lookup(self, factories):
        lookup = {}
        for factory in factories:
            canonical = self._canonical_factory_value(factory)
            for value in [factory.ma_nha_may, factory.ten_nha_may, canonical]:
                if value:
                    lookup[str(value).strip().lower()] = canonical
        return lookup

    def _canonical_factory_value(self, factory):
        return factory.ten_nha_may or factory.ma_nha_may

    def _normalize_value(self, value):
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return ""
        lowered = raw.lower()
        if lowered in self.factory_lookup:
            return self.factory_lookup[lowered]

        for factory in self.factories:
            name = (factory.ten_nha_may or "").strip()
            code = (factory.ma_nha_may or "").strip()
            if name and name.lower() in lowered:
                return self._canonical_factory_value(factory)
            if code and code.lower() == lowered:
                return self._canonical_factory_value(factory)
        return None

    def _get_default_factory_value(self):
        if not self.default_factory_code:
            return None
        factory = Bang_nha_may.objects.filter(
            ma_nha_may__iexact=self.default_factory_code.strip()
        ).first()
        if not factory:
            raise ValueError(f"Unknown default factory code: {self.default_factory_code}")
        return self._canonical_factory_value(factory)

    def _print_factories(self):
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("Configured factories"))
        if not self.factories:
            self.stdout.write(self.style.WARNING("  No Bang_nha_may records found."))
            return
        for factory in self.factories:
            self.stdout.write(f"  {factory.ma_nha_may}: {factory.ten_nha_may}")

    def _print_profiles(self):
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("UserProfile factory assignment"))
        total = UserProfile.objects.count()
        unrestricted = UserProfile.objects.filter(is_all_factories=True).count()
        missing = UserProfile.objects.filter(is_all_factories=False, nha_may__isnull=True).count()
        self.stdout.write(f"  profiles: {total}")
        self.stdout.write(f"  all factories: {unrestricted}")
        if missing:
            self.stdout.write(self.style.WARNING(f"  missing nha_may: {missing}"))
        else:
            self.stdout.write("  missing nha_may: 0")

    def _audit_model_text_field(self, model, field_name, label):
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO(label))
        total = model.objects.count()
        blank_filter = Q(**{f"{field_name}__isnull": True}) | Q(**{field_name: ""})
        blank_count = model.objects.filter(blank_filter).count()
        distinct_values = list(
            model.objects.values(field_name)
            .annotate(count=Count("id"))
            .order_by(field_name)
        )

        matched = 0
        unknown = 0
        for row in distinct_values:
            value = row[field_name]
            count = row["count"]
            normalized = self._normalize_value(value)
            if normalized is None and value not in [None, ""]:
                unknown += count
                self.stdout.write(self.style.WARNING(f"  unknown {value!r}: {count}"))
            elif normalized:
                matched += count

        self.stdout.write(f"  total: {total}")
        self.stdout.write(f"  blank: {blank_count}")
        self.stdout.write(f"  matched known factory: {matched}")
        self.stdout.write(f"  unknown: {unknown}")

    def _audit_thong_so_links(self, model, label):
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO(f"{label} related ThietBi consistency"))
        total = model.objects.count()
        missing_device_factory = model.objects.filter(
            Q(thiet_bi__nha_may__isnull=True) | Q(thiet_bi__nha_may="")
        ).count()
        own_blank = model.objects.filter(Q(nha_may__isnull=True) | Q(nha_may="")).count()
        self.stdout.write(f"  total: {total}")
        self.stdout.write(f"  rows with blank own nha_may: {own_blank}")
        self.stdout.write(f"  rows whose ThietBi has blank nha_may: {missing_device_factory}")

    def _normalize_thiet_bi(self):
        default_value = self._get_default_factory_value()
        changed = 0
        for obj in ThietBi.objects.all().only("id", "nha_may"):
            normalized = self._normalize_value(obj.nha_may)
            if normalized is None and not obj.nha_may and default_value:
                normalized = default_value
            if normalized and obj.nha_may != normalized:
                obj.nha_may = normalized
                obj.save(update_fields=["nha_may"])
                changed += 1
        self.stdout.write(f"  ThietBi normalized: {changed}")

    def _normalize_thong_so(self, model, label):
        changed = 0
        queryset = model.objects.select_related("thiet_bi").only(
            "id",
            "nha_may",
            "thiet_bi__nha_may",
        )
        for obj in queryset:
            device_factory = self._normalize_value(getattr(obj.thiet_bi, "nha_may", None))
            own_factory = self._normalize_value(obj.nha_may)
            normalized = device_factory or own_factory
            if normalized and obj.nha_may != normalized:
                obj.nha_may = normalized
                obj.save(update_fields=["nha_may"])
                changed += 1
        self.stdout.write(f"  {label} normalized: {changed}")
