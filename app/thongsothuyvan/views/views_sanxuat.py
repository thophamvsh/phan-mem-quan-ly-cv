import os
from datetime import date, datetime, time, timedelta
from django.conf import settings
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from ..models import (
    ThongsoSanxuat,
    ThongsoGioPhat,
    ThongSoThuyVanCaiDat,
)

def get_env_value(name):
    value = os.environ.get(name)
    if value:
        return value

    env_path = os.path.join(settings.BASE_DIR.parent, ".env")
    if not os.path.exists(env_path):
        return None

    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, raw_value = line.split("=", 1)
            if key.strip() == name:
                return raw_value.strip().strip('"').strip("'")

    return None

from ..serializers import (
    ThongsoSanxuatSerializer,
    ThongsoGioPhatSerializer,
)
from ..plants import get_hydrology_plants, normalize_plant_code
from .views_settings import build_hydrology_settings_payload

# --- Permission Helper Functions ---

def user_can_write_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(
        profile
        and (
            profile.can_create_hydrology_data
            or profile.can_edit_hydrology_data
        )
    )


def user_can_view_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(
        profile
        and (
            profile.can_view_hydrology_data
            or profile.can_view_realtime_hydrology
            or profile.can_view_hydrology_settings
            or profile.can_edit_hydrology_settings
            or profile.can_create_hydrology_data
            or profile.can_edit_hydrology_data
        )
    )


def user_can_edit_hydrology_settings(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_edit_hydrology_settings)


def user_can_delete_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_delete_hydrology_data)


def user_can_view_realtime_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_view_realtime_hydrology)


def user_can_update_realtime_hydrology(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_update_realtime_hydrology)


def user_can_modify_hydrology_object(user, obj):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    created_by_id = getattr(obj, "created_by_id", None)
    return created_by_id is None or created_by_id == user.id


def user_can_access_plant(user, nhamay):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    if not profile:
        return False
    if profile.is_all_factories:
        return True

    user_factory = getattr(profile, "nha_may", None)
    user_factory_code = getattr(user_factory, "ma_nha_may", "")
    return normalize_plant_code(user_factory_code) == normalize_plant_code(nhamay)


# --- Helper Functions ---

def parse_filter_date(date_str):
    if not date_str:
        return None

    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_float_or_none(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("Gia tri so khong hop le")


def get_year_offset_date(value, offset):
    if not value:
        return None

    try:
        return value.replace(year=value.year - offset)
    except ValueError:
        return value.replace(year=value.year - offset, day=28)


def get_quarter_bounds(value):
    if not value:
        return None, None

    start_month = ((value.month - 1) // 3) * 3 + 1
    return date(value.year, start_month, 1), value


def add_record(record_map, record):
    if record:
        record_map[record.id] = record


def add_queryset_records(record_map, queryset):
    for record in queryset:
        add_record(record_map, record)


def get_latest_record_before(plant, target_date=None):
    queryset = ThongsoSanxuat.objects.filter(nha_may=plant)
    if target_date:
        queryset = queryset.filter(thoi_gian__date__lte=target_date)
    return queryset.order_by("-thoi_gian").first()


def build_dashboard_records_for_plant(plant, target_date=None):
    record_map = {}
    latest_record = get_latest_record_before(plant, target_date)
    latest_date = latest_record.thoi_gian.date() if latest_record else None
    report_date = target_date or latest_date

    add_record(record_map, latest_record)

    if not report_date:
        return []

    previous_year_date = get_year_offset_date(report_date, 1)
    if previous_year_date:
        add_record(
            record_map,
            ThongsoSanxuat.objects.filter(
                nha_may=plant,
                thoi_gian__date=previous_year_date,
            )
            .order_by("-thoi_gian")
            .first(),
        )

    quarter_start, quarter_end = get_quarter_bounds(report_date)
    if quarter_start and quarter_end:
        add_queryset_records(
            record_map,
            ThongsoSanxuat.objects.filter(
                nha_may=plant,
                thoi_gian__date__gte=quarter_start,
                thoi_gian__date__lte=quarter_end,
            ).order_by("-thoi_gian"),
        )

    return sorted(record_map.values(), key=lambda record: record.thoi_gian, reverse=True)


def build_operation_hours_for_records(plant, records):
    latest_record = records[0] if records else None
    if not latest_record or not latest_record.thoi_gian:
        return {"h1Year": None, "h2Year": None}

    report_date = latest_record.thoi_gian.date()
    year_start = date(report_date.year, 1, 1)
    rows = (
        ThongsoGioPhat.objects.filter(
            nha_may=plant,
            ngay__gte=year_start,
            ngay__lte=report_date,
        )
        .values("to_may")
        .annotate(year=Sum("gio_phat_dien"))
        .order_by()
    )
    totals = {str(row["to_may"]): row["year"] or 0 for row in rows}

    return {
        "h1Year": totals.get("1"),
        "h2Year": totals.get("2"),
    }


# --- API ViewSets ---

class ThongsoSanxuatViewSet(viewsets.ModelViewSet):
    serializer_class = ThongsoSanxuatSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        nhamay = normalize_plant_code(self.request.query_params.get('nhamay', 'songhinh'))
        if not user_can_access_plant(self.request.user, nhamay):
            raise PermissionDenied("Bạn không có quyền truy cập dữ liệu của nhà máy này.")

        queryset = ThongsoSanxuat.objects.filter(nha_may=nhamay)

        date_from = parse_filter_date(self.request.query_params.get("date_from"))
        date_to = parse_filter_date(self.request.query_params.get("date_to"))
        if date_from:
            queryset = queryset.filter(thoi_gian__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(thoi_gian__date__lte=date_to)

        queryset = queryset.order_by('-thoi_gian')
        try:
            limit = int(self.request.query_params.get("limit") or 0)
        except (TypeError, ValueError):
            limit = 0

        return queryset[:limit] if limit > 0 else queryset

    def perform_create(self, serializer):
        nhamay = normalize_plant_code(serializer.validated_data.get('nha_may', 'songhinh'))
        if not user_can_access_plant(self.request.user, nhamay):
            raise PermissionDenied("Bạn không có quyền tạo dữ liệu cho nhà máy này.")
        
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        obj = self.get_object()
        if not user_can_access_plant(self.request.user, obj.nha_may):
            raise PermissionDenied("Bạn không có quyền cập nhật dữ liệu của nhà máy này.")
        if not user_can_modify_hydrology_object(self.request.user, obj):
            raise PermissionDenied("Ban chi duoc sua du lieu do chinh ban cap nhat.")
        
        save_kwargs = {"updated_by": self.request.user}
        if obj.created_by_id is None:
            save_kwargs["created_by"] = self.request.user
        serializer.save(**save_kwargs)

    def perform_destroy(self, instance):
        if not user_can_access_plant(self.request.user, instance.nha_may):
            raise PermissionDenied("Bạn không có quyền xóa dữ liệu của nhà máy này.")
        if not user_can_modify_hydrology_object(self.request.user, instance):
            raise PermissionDenied("Ban chi duoc xoa du lieu do chinh ban cap nhat.")
        instance.delete()


class ThongsoGioPhatViewSet(viewsets.ModelViewSet):
    serializer_class = ThongsoGioPhatSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        nhamay = normalize_plant_code(self.request.query_params.get('nhamay', 'songhinh'))
        if not user_can_access_plant(self.request.user, nhamay):
            raise PermissionDenied("Bạn không có quyền truy cập dữ liệu của nhà máy này.")

        queryset = ThongsoGioPhat.objects.filter(nha_may=nhamay)

        date_from = parse_filter_date(self.request.query_params.get("date_from"))
        date_to = parse_filter_date(self.request.query_params.get("date_to"))
        if date_from:
            queryset = queryset.filter(ngay__gte=date_from)
        if date_to:
            queryset = queryset.filter(ngay__lte=date_to)

        queryset = queryset.order_by('-ngay', 'to_may')
        try:
            limit = int(self.request.query_params.get("limit") or 0)
        except (TypeError, ValueError):
            limit = 0

        return queryset[:limit] if limit > 0 else queryset

    def perform_create(self, serializer):
        nhamay = normalize_plant_code(serializer.validated_data.get('nha_may', 'songhinh'))
        if not user_can_access_plant(self.request.user, nhamay):
            raise PermissionDenied("Bạn không có quyền tạo dữ liệu cho nhà máy này.")
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        obj = self.get_object()
        if not user_can_access_plant(self.request.user, obj.nha_may):
            raise PermissionDenied("Bạn không có quyền cập nhật dữ liệu của nhà máy này.")
        if not user_can_modify_hydrology_object(self.request.user, obj):
            raise PermissionDenied("Ban chi duoc sua du lieu do chinh ban cap nhat.")
        
        save_kwargs = {"updated_by": self.request.user}
        if obj.created_by_id is None:
            save_kwargs["created_by"] = self.request.user
        serializer.save(**save_kwargs)

    def perform_destroy(self, instance):
        if not user_can_access_plant(self.request.user, instance.nha_may):
            raise PermissionDenied("Bạn không có quyền xóa dữ liệu của nhà máy này.")
        if not user_can_modify_hydrology_object(self.request.user, instance):
            raise PermissionDenied("Ban chi duoc xoa du lieu do chinh ban cap nhat.")
        instance.delete()


# --- API Views ---

class DashboardSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date")
        target_date = None

        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        data_by_plant = {}
        operation_hours_by_plant = {}
        
        plants = ["songhinh", "vinhson", "thuongkontum"]

        for plant in plants:
            records = build_dashboard_records_for_plant(plant, target_date)
            data_by_plant[plant] = ThongsoSanxuatSerializer(records, many=True).data
            operation_hours_by_plant[plant] = build_operation_hours_for_records(
                plant,
                records,
            )

        report_year = (
            target_date.year
            if target_date
            else timezone.localdate().year
        )
        hydrology_settings = build_hydrology_settings_payload(
            report_year,
            plants,
        )

        return Response(
            {
                "data_by_plant": data_by_plant,
                "operation_hours_by_plant": operation_hours_by_plant,
                "hydrology_settings": hydrology_settings,
            }
        )


class GioPhatSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        nhamay = normalize_plant_code(request.query_params.get("nhamay", "songhinh"))
        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Ban khong co quyen truy cap du lieu nha may nay."},
                status=status.HTTP_403_FORBIDDEN,
            )

        dates_str = request.query_params.get("dates")

        if dates_str:
            dates_list = sorted({d.strip() for d in dates_str.split(",") if d.strip()})
            parsed_dates = []
            for d_str in dates_list:
                try:
                    parsed_dates.append(datetime.strptime(d_str, "%Y-%m-%d").date())
                except ValueError:
                    continue

            if not parsed_dates:
                return Response(
                    {"error": "Khong tim thay ngay hop le trong danh sach dates"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            min_year = min(d.year for d in parsed_dates)
            max_date = max(parsed_dates)

            records = list(
                ThongsoGioPhat.objects.filter(
                    nha_may=nhamay,
                    ngay__gte=date(min_year, 1, 1),
                    ngay__lte=max_date,
                ).order_by("ngay", "to_may")
            )
            machines_set = {str(record.to_may) for record in records}
            running_sums = {}
            results = {}
            record_index = 0

            for d in sorted(parsed_dates):
                day_values = {}
                while record_index < len(records) and records[record_index].ngay <= d:
                    record = records[record_index]
                    machine = str(record.to_may)
                    value = record.gio_phat_dien or 0.0
                    sum_key = (record.ngay.year, machine)
                    running_sums[sum_key] = running_sums.get(sum_key, 0.0) + value
                    if record.ngay == d:
                        day_values[machine] = day_values.get(machine, 0.0) + value
                    record_index += 1

                d_str = d.isoformat()
                results[d_str] = {
                    "nha_may": nhamay,
                    "date": d_str,
                    "year": d.year,
                    "machines": {}
                }
                for m in machines_set:
                    results[d_str]["machines"][m] = {
                        "day": day_values.get(m, 0.0),
                        "year": running_sums.get((d.year, m), 0.0),
                    }

            return Response(results)

        date_str = request.query_params.get("date")
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            target_date = timezone.localdate()

        year_start = date(target_date.year, 1, 1)
        machines = {}

        day_rows = (
            ThongsoGioPhat.objects.filter(nha_may=nhamay, ngay=target_date)
            .values("to_may")
            .annotate(total=Sum("gio_phat_dien"))
            .order_by()
        )
        year_rows = (
            ThongsoGioPhat.objects.filter(
                nha_may=nhamay,
                ngay__gte=year_start,
                ngay__lte=target_date,
            )
            .values("to_may")
            .annotate(total=Sum("gio_phat_dien"))
            .order_by()
        )

        for row in day_rows:
            machine = str(row["to_may"])
            machines.setdefault(machine, {"day": 0, "year": 0})
            machines[machine]["day"] = row["total"] or 0

        for row in year_rows:
            machine = str(row["to_may"])
            machines.setdefault(machine, {"day": 0, "year": 0})
            machines[machine]["year"] = row["total"] or 0

        return Response(
            {
                "nha_may": nhamay,
                "date": target_date.isoformat(),
                "year": target_date.year,
                "machines": machines,
            }
        )


class GioPhatYearSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        nhamay = normalize_plant_code(request.query_params.get("nhamay", "songhinh"))
        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Ban khong co quyen truy cap du lieu nha may nay."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_str = request.query_params.get("date")

        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            target_date = timezone.localdate()

        year_start = date(target_date.year, 1, 1)
        queryset = ThongsoGioPhat.objects.filter(
            nha_may=nhamay,
            ngay__gte=year_start,
            ngay__lte=target_date,
        )

        rows = (
            queryset.values("to_may")
            .annotate(
                year=Sum("gio_phat_dien"),
                row_count=Count("id"),
            )
            .order_by("to_may")
        )

        machines = {
            str(row["to_may"]): {
                "year": row["year"] or 0,
                "row_count": row["row_count"],
            }
            for row in rows
        }

        return Response(
            {
                "nha_may": nhamay,
                "date": target_date.isoformat(),
                "date_from": year_start.isoformat(),
                "date_to": target_date.isoformat(),
                "year": target_date.year,
                "row_count": queryset.count(),
                "machines": machines,
            }
        )


class DeletePlantDataByDateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_can_delete_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen xoa du lieu thuy van."},
                status=status.HTTP_403_FORBIDDEN,
            )

        nhamay = normalize_plant_code(
            request.data.get("nhamay") or request.query_params.get("nhamay", "songhinh")
        )
        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Ban khong co quyen xoa du lieu cua nha may nay."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_str = request.data.get("date") or request.query_params.get("date")

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return Response(
                {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sanluong_qs = ThongsoSanxuat.objects.filter(
            nha_may=nhamay,
            thoi_gian__date=target_date,
        )
        giophat_qs = ThongsoGioPhat.objects.filter(
            nha_may=nhamay,
            ngay=target_date,
        )
        total_available = sanluong_qs.count() + giophat_qs.count()
        if not request.user.is_superuser:
            sanluong_qs = sanluong_qs.filter(created_by=request.user)
            giophat_qs = giophat_qs.filter(created_by=request.user)

        sanluong_deleted = sanluong_qs.count()
        giophat_deleted = giophat_qs.count()
        total_deleted = sanluong_deleted + giophat_deleted

        if total_available > 0 and total_deleted == 0:
            return Response(
                {
                    "success": False,
                    "error": "Ban chi duoc xoa du lieu do chinh ban cap nhat.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        sanluong_qs.delete()
        giophat_qs.delete()

        return Response(
            {
                "success": True,
                "message": f"Da xoa du lieu ngay {target_date.isoformat()} cho {nhamay}",
                "deleted": {
                    "sanluong": sanluong_deleted,
                    "giophat": giophat_deleted,
                    "total": total_deleted,
                },
            }
        )


SANLUONG_FIELDS = [
    "cot_c", "cot_d", "cot_f", "cot_g", "cot_h", "cot_i", "cot_j", "cot_k",
    "cot_l", "cot_m", "cot_n", "cot_o", "cot_p", "cot_q", "cot_r", "cot_s",
    "cot_t", "cot_u", "cot_v", "cot_w", "cot_x", "sanluong_kh_thang",
    "mucnuoc_gioihan_tuan", "mucnuoc_gioihan_tuan_ho_a", "mucnuoc_gioihan_tuan_ho_b",
    "mucnuoc_thuongluu_ho_b", "mucnuoc_thuongluu_ho_c", "luuluong_ve_ho_b",
    "luuluong_ve_ho_c",
]

class ManualHydrologyDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not user_can_write_hydrology(request.user):
            return Response(
                {"error": "Ban khong co quyen nhap du lieu thuy van."},
                status=status.HTTP_403_FORBIDDEN,
            )

        nhamay = normalize_plant_code(request.data.get("nhamay") or "songhinh")
        if nhamay not in ("songhinh", "vinhson", "thuongkontum"):
            return Response(
                {"error": "Nha may khong hop le."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_can_access_plant(request.user, nhamay):
            return Response(
                {"error": "Ban khong co quyen nhap du lieu cho nha may nay."},
                status=status.HTTP_403_FORBIDDEN,
            )

        date_str = request.data.get("date")
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return Response(
                {"error": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            defaults = {}
            for field in SANLUONG_FIELDS:
                if field == "cot_c":
                    defaults[field] = request.data.get(field) or None
                else:
                    defaults[field] = parse_float_or_none(request.data.get(field))

            existing = (
                ThongsoSanxuat.objects.filter(
                    nha_may=nhamay,
                    thoi_gian__date=target_date,
                )
                .order_by("-thoi_gian")
                .first()
            )

            if existing:
                if not user_can_modify_hydrology_object(request.user, existing):
                    return Response(
                        {"error": "Ban chi duoc sua du lieu do chinh ban cap nhat."},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                for field, value in defaults.items():
                    setattr(existing, field, value)
                update_fields = [*SANLUONG_FIELDS, "updated_by"]
                if existing.created_by_id is None:
                    existing.created_by = request.user
                    update_fields.append("created_by")
                existing.updated_by = request.user
                existing.save(update_fields=update_fields)
                sanluong_created = False
                sanluong_obj = existing
            else:
                thoi_gian = timezone.make_aware(
                    datetime.combine(target_date, time.min),
                    timezone.get_current_timezone(),
                )
                sanluong_obj = ThongsoSanxuat.objects.create(
                    nha_may=nhamay,
                    thoi_gian=thoi_gian,
                    created_by=request.user,
                    updated_by=request.user,
                    **defaults,
                )
                sanluong_created = True

            gio_phat_results = []
            for to_may in (1, 2):
                gio_phat = request.data.get(f"gio_phat_h{to_may}")
                gio_ngung = request.data.get(f"gio_ngung_h{to_may}")

                if gio_phat in (None, "") and gio_ngung in (None, ""):
                    continue

                existing_gio_phat = ThongsoGioPhat.objects.filter(
                    nha_may=nhamay,
                    ngay=target_date,
                    to_may=to_may,
                ).first()
                if existing_gio_phat and not user_can_modify_hydrology_object(
                    request.user,
                    existing_gio_phat,
                ):
                    return Response(
                        {"error": "Ban chi duoc sua du lieu gio phat do chinh ban cap nhat."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

                obj, created = ThongsoGioPhat.objects.update_or_create(
                    nha_may=nhamay,
                    ngay=target_date,
                    to_may=to_may,
                    defaults={
                        "gio_phat_dien": parse_float_or_none(gio_phat),
                        "gio_ngung": parse_float_or_none(gio_ngung),
                        "updated_by": request.user,
                        **(
                            {}
                            if existing_gio_phat and existing_gio_phat.created_by_id
                            else {"created_by": request.user}
                        ),
                    },
                )
                gio_phat_results.append(
                    {
                        "to_may": obj.to_may,
                        "created": created,
                    }
                )
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "success": True,
                "message": f"Da luu du lieu nhap tay ngay {target_date.isoformat()} cho {nhamay}",
                "sanluong": {
                    "id": sanluong_obj.id,
                    "created": sanluong_created,
                },
                "giophat": gio_phat_results,
            }
        )
