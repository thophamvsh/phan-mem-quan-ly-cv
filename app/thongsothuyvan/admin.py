from django.contrib import admin
import inspect
import math
from datetime import date, datetime, timedelta
from django.contrib.admin.views.main import ChangeList
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import formats as django_formats
from import_export import resources, widgets
from import_export.admin import ImportExportModelAdmin
from import_export.formats import base_formats

from .models import (
    SongHinhRealtimeSnapshot,
    SonghinhMnh, ThuongKonTumMnh,
    VinhSonRealtimeSnapshot,
    Vinhson_HoA, Vinhson_HoB, Vinhson_Hoc,
    MucnuocQuytrinh,
    ThongsoSanxuat, ThongsoGioPhat
)


if not hasattr(django_formats, "sanitize_strftime_format"):
    django_formats.sanitize_strftime_format = lambda fmt: fmt


class SafeFloatWidget(widgets.FloatWidget):
    def clean(self, value, row=None, **kwargs):
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)

        value = str(value).strip()
        if value in {"", "-", "--", "nan", "NaN", "None"}:
            return None

        value = value.replace(" ", "")
        if "," in value and "." in value:
            if value.rfind(",") > value.rfind("."):
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", "")
        elif "," in value:
            parts = value.split(",")
            if len(parts) > 2 or len(parts[-1]) == 3:
                value = value.replace(",", "")
            else:
                value = value.replace(",", ".")
        elif value.count(".") > 1:
            value = value.replace(".", "")

        return float(value)


class FlexibleDateTimeWidget(widgets.DateTimeWidget):
    supported_formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    )

    def clean(self, value, row=None, **kwargs):
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, date):
            dt = datetime.combine(value, datetime.min.time())
        else:
            value = str(value).strip()
            dt = None
            if dt is None:
                for fmt in self.supported_formats:
                    try:
                        dt = datetime.strptime(value, fmt)
                        break
                    except ValueError:
                        continue
            if dt is None:
                dt = parse_datetime(value)
            if dt is None:
                parsed_date = parse_date(value)
                if parsed_date is not None:
                    dt = datetime.combine(parsed_date, datetime.min.time())
            if dt is None:
                raise ValueError("Value could not be parsed using supported datetime formats.")

        if settings.USE_TZ and timezone.is_naive(dt):
            return timezone.make_aware(dt)
        return dt


class FlexibleDateWidget(widgets.DateWidget):
    supported_formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%Y/%m/%d",
    )

    def clean(self, value, row=None, **kwargs):
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        value = str(value).strip()
        for fmt in self.supported_formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        parsed_date = parse_date(value)
        if parsed_date is not None:
            return parsed_date
        raise ValueError("Value could not be parsed using supported date formats.")


class MonthDayWidget(widgets.Widget):
    supported_formats = (
        "%d/%m",
        "%d-%m",
        "%d-%b",
        "%d-%B",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%m/%d/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
    )

    def clean(self, value, row=None, **kwargs):
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.strftime("%d/%m")
        if isinstance(value, date):
            return value.strftime("%d/%m")
        if isinstance(value, (int, float)) and not math.isnan(value):
            # Excel serial date. Day 1 is 1900-01-01, with Excel's leap-year quirk.
            excel_epoch = datetime(1899, 12, 30)
            return (excel_epoch + timedelta(days=float(value))).strftime("%d/%m")

        value = str(value).strip()
        if value.endswith(".0") and value[:-2].isdigit():
            excel_epoch = datetime(1899, 12, 30)
            return (excel_epoch + timedelta(days=float(value))).strftime("%d/%m")

        for date_format in self.supported_formats:
            try:
                return datetime.strptime(value, date_format).strftime("%d/%m")
            except ValueError:
                continue

        parsed_date = parse_date(value)
        if parsed_date is not None:
            return parsed_date.strftime("%d/%m")

        raise ValueError("Ngày phải có định dạng dd/MM.")

    def render(self, value, obj=None):
        return value or ""


class XLSXOnlyMixin:
    search_help_text = None

    # Chỉ dùng các format đã có sẵn dependency trong project
    formats = (base_formats.XLSX, base_formats.CSV)

    def get_import_formats(self):
        return list(self.formats)

    def get_export_formats(self):
        return list(self.formats)

    def get_export_queryset(self, request):
        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        list_select_related = self.get_list_select_related(request)

        list_editable = getattr(self, "list_editable", ())
        list_per_page = getattr(self, "list_per_page", 100)
        list_max_show_all = getattr(self, "list_max_show_all", 200)
        sortable_by = getattr(self, "sortable_by", None)
        date_hierarchy = getattr(self, "date_hierarchy", None)

        kwargs = {"sortable_by": sortable_by}
        if "search_help_text" in inspect.signature(ChangeList.__init__).parameters:
            kwargs["search_help_text"] = self.search_help_text

        cl = ChangeList(
            request,
            self.model,
            list_display,
            list_display_links,
            list_filter,
            date_hierarchy,
            search_fields,
            list_select_related,
            list_per_page,
            list_max_show_all,
            list_editable,
            self,
            **kwargs,
        )
        return cl.get_queryset(request)


class BaseThuyVanResource(resources.ModelResource):
    class Meta:
        # File import chỉ cần đúng 2 cột: Mucnuoc, dungtich
        fields = ("Mucnuoc", "dungtich")
        export_order = fields
        # Luôn tạo bản ghi mới khi import, không dò trùng bằng get()
        force_init_instance = True


class SonghinhMnhResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = SonghinhMnh


class ThuongKonTumMnhResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = ThuongKonTumMnh


class Vinhson_HoAResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = Vinhson_HoA


class Vinhson_HoBResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = Vinhson_HoB


class Vinhson_HocResource(BaseThuyVanResource):
    class Meta(BaseThuyVanResource.Meta):
        model = Vinhson_Hoc


class SafeWidgetResource(resources.ModelResource):
    float_fields = ()
    datetime_fields = ()
    date_fields = ()
    required_import_fields = ()
    ignored_blank_fields = ("nha_may",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.float_fields:
            if field_name in self.fields:
                self.fields[field_name].widget = SafeFloatWidget()
        for field_name in self.datetime_fields:
            if field_name in self.fields:
                self.fields[field_name].widget = FlexibleDateTimeWidget()
        for field_name in self.date_fields:
            if field_name in self.fields:
                self.fields[field_name].widget = FlexibleDateWidget()

    @staticmethod
    def _is_empty_value(value):
        if value is None:
            return True
        if isinstance(value, float) and math.isnan(value):
            return True
        if isinstance(value, str):
            return value.strip() in {"", "-", "--", "nan", "NaN", "None"}
        return False

    def _has_meaningful_data(self, row):
        return any(
            not self._is_empty_value(row.get(field_name))
            for field_name in self.fields
            if field_name not in self.ignored_blank_fields
        )

    def skip_row(self, instance, original, row, import_validation_errors=None):
        if not self._has_meaningful_data(row):
            return True

        missing_fields = [
            field_name
            for field_name in self.required_import_fields
            if self._is_empty_value(row.get(field_name))
        ]
        if missing_fields:
            raise ValidationError(
                "Thiếu dữ liệu bắt buộc: " + ", ".join(missing_fields)
            )

        return super().skip_row(
            instance,
            original,
            row,
            import_validation_errors=import_validation_errors,
        )


class ThongsoSanxuatResource(SafeWidgetResource):
    required_import_fields = ("nha_may", "thoi_gian")
    datetime_fields = ("thoi_gian",)
    float_fields = (
        "cot_d",
        "cot_f",
        "cot_g",
        "cot_h",
        "cot_i",
        "cot_j",
        "cot_k",
        "cot_l",
        "cot_m",
        "cot_n",
        "cot_o",
        "cot_p",
        "cot_q",
        "cot_r",
        "cot_s",
        "cot_t",
        "cot_u",
        "cot_v",
        "cot_w",
        "cot_x",
        "sanluong_kh_thang",
        "mucnuoc_gioihan_tuan",
        "mucnuoc_gioihan_tuan_ho_a",
        "mucnuoc_gioihan_tuan_ho_b",
        "mucnuoc_thuongluu_ho_b",
        "mucnuoc_thuongluu_ho_c",
        "luuluong_ve_ho_b",
        "luuluong_ve_ho_c",
    )

    class Meta:
        model = ThongsoSanxuat
        fields = (
            "nha_may",
            "thoi_gian",
            "cot_c",
            "cot_d",
            "cot_f",
            "cot_g",
            "cot_h",
            "cot_i",
            "cot_j",
            "cot_k",
            "cot_l",
            "cot_m",
            "cot_n",
            "cot_o",
            "cot_p",
            "cot_q",
            "cot_r",
            "cot_s",
            "cot_t",
            "cot_u",
            "cot_v",
            "cot_w",
            "cot_x",
            "sanluong_kh_thang",
            "mucnuoc_gioihan_tuan",
            "mucnuoc_gioihan_tuan_ho_a",
            "mucnuoc_gioihan_tuan_ho_b",
            "mucnuoc_thuongluu_ho_b",
            "mucnuoc_thuongluu_ho_c",
            "luuluong_ve_ho_b",
            "luuluong_ve_ho_c",
        )
        export_order = fields
        import_id_fields = ("thoi_gian", "nha_may")


class ThongsoGioPhatResource(resources.ModelResource):
    class Meta:
        model = ThongsoGioPhat
        fields = (
            "nha_may",
            "ngay",
            "to_may",
            "gio_phat_dien",
            "gio_ngung",
        )
        export_order = fields
        import_id_fields = ("ngay", "to_may", "nha_may")


class MucnuocQuytrinhResource(SafeWidgetResource):
    required_import_fields = ("ngay_bat_dau", "ngay_ket_thuc")
    ignored_blank_fields = ("nha_may",)
    float_fields = ("muc_nuoc_bat_dau", "muc_nuoc_ket_thuc")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ngay_bat_dau"].widget = MonthDayWidget()
        self.fields["ngay_ket_thuc"].widget = MonthDayWidget()

    class Meta:
        model = MucnuocQuytrinh
        fields = (
            "nha_may",
            "ngay_bat_dau",
            "ngay_ket_thuc",
            "muc_nuoc_bat_dau",
            "muc_nuoc_ket_thuc",
        )
        export_order = fields
        import_id_fields = ("nha_may", "ngay_bat_dau", "ngay_ket_thuc")


@admin.register(SonghinhMnh)
class SonghinhMnhAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = SonghinhMnhResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")


@admin.register(ThuongKonTumMnh)
class ThuongKonTumMnhAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThuongKonTumMnhResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")


@admin.register(Vinhson_HoA)
class Vinhson_HoAAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = Vinhson_HoAResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")


@admin.register(Vinhson_HoB)
class Vinhson_HoBAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = Vinhson_HoBResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")


@admin.register(Vinhson_Hoc)
class Vinhson_HocAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = Vinhson_HocResource
    list_display = ("id", "Mucnuoc", "dungtich", "created_at")

@admin.register(ThongsoSanxuat)
class ThongsoSanxuatAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThongsoSanxuatResource
    list_display = ("thoi_gian", "nha_may","cot_g", "cot_h", "cot_i", "cot_j","cot_k", "cot_m", "cot_n", "cot_q", "cot_r", "cot_u", "cot_v", "created_by", "updated_by", "created_at")
    list_filter = ("nha_may", "thoi_gian")
    search_fields = ("thoi_gian", "nha_may", "cot_c")
    date_hierarchy = "thoi_gian"


@admin.register(MucnuocQuytrinh)
class MucnuocQuytrinhAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = MucnuocQuytrinhResource
    list_display = (
        "ngay_bat_dau",
        "ngay_ket_thuc",
        "nha_may",
        "muc_nuoc_bat_dau",
        "muc_nuoc_ket_thuc",
        "created_by",
        "updated_by",
        "created_at",
    )
    list_filter = ("nha_may", "ngay_bat_dau", "ngay_ket_thuc")
    search_fields = ("nha_may",)


@admin.register(ThongsoGioPhat)
class ThongsoGioPhatAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThongsoGioPhatResource
    list_display = ("ngay", "nha_may", "to_may", "gio_phat_dien", "gio_ngung", "created_by", "updated_by", "created_at")
    list_filter = ("nha_may", "to_may", "ngay")
    search_fields = ("ngay", "nha_may")
    date_hierarchy = "ngay"


@admin.register(SongHinhRealtimeSnapshot)
class SongHinhRealtimeSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "time_stamp",
        "mntl",
        "mnhl",
        "pnm",
        "qcm",
        "qtran",
        "dung_tich_ho",
        "dung_tich_phong_lu",
        "created_at",
    )
    list_filter = ("time_stamp", "created_at")
    search_fields = ("id", "time_stamp")
    date_hierarchy = "time_stamp"
    readonly_fields = ("created_at", "raw_data")


@admin.register(VinhSonRealtimeSnapshot)
class VinhSonRealtimeSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "time_stamp",
        "mntla",
        "mntla_td",
        "mntlb",
        "mntlc",
        "ph1",
        "ph2",
        "qcm",
        "qtran",
        "created_at",
    )
    list_filter = ("time_stamp", "created_at")
    search_fields = ("id", "time_stamp")
    date_hierarchy = "time_stamp"
    readonly_fields = ("created_at", "raw_data")
