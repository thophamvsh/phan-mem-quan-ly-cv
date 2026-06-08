from django.contrib import admin
from django.utils.html import format_html
from import_export.results import RowResult
from django.utils.text import slugify
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from import_export import resources, fields, widgets
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget, DateWidget, IntegerWidget, DecimalWidget
from import_export.formats import base_formats
from datetime import date, datetime, timedelta
import tablib
import io
import zipfile
import base64
import qrcode

from .models import (
    ThietBi, VatTu, ThietBiVatTu, ThongSoVanHanh, AnToanThietBi, DinhKem, ThongSoToMay, ThongSoTram110KV, NguongThongSo
)

# # Cho phép A hoặc A.B-C...


# ===================== CUSTOM WIDGETS =====================

class FlexibleDateWidget(widgets.Widget):
    """Widget xử lý nhiều format ngày tháng"""

    def clean(self, value, row=None, **kwargs):
        if not value or value == '' or str(value).strip() == '':
            return None

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        try:
            normalized_number = str(value).strip().replace(".", "", 1)
            if isinstance(value, (int, float)) or normalized_number.isdigit():
                serial = float(value)
                if serial > 0:
                    return (datetime(1899, 12, 30) + timedelta(days=serial)).date()
        except (TypeError, ValueError, OverflowError):
            pass

        # Danh sách các format có thể
        date_formats = [
            '%Y-%m-%d',      # 2023-12-25
            '%Y-%m-%d %H:%M:%S',  # 2023-12-25 00:00:00
            '%Y-%m-%d %H:%M',     # 2023-12-25 00:00
            '%d/%m/%Y',      # 25/12/2023
            '%d/%m/%Y %H:%M:%S',  # 25/12/2023 00:00:00
            '%d/%m/%Y %H:%M',     # 25/12/2023 00:00
            '%d-%m-%Y',      # 25-12-2023
            '%m/%d/%Y',      # 12/25/2023
            '%d.%m.%Y',      # 25.12.2023
            '%Y/%m/%d',      # 2023/12/25
        ]

        # Thử từng format
        for fmt in date_formats:
            try:
                return datetime.strptime(str(value).strip(), fmt).date()
            except ValueError:
                continue

        # Nếu không parse được, trả về None thay vì lỗi
        return None

    def render(self, value, obj=None):
        """Render ngày tháng thành string"""
        if value:
            return value.strftime('%Y-%m-%d')
        return ''


class SafeIntegerWidget(IntegerWidget):
    """Integer widget tolerant with blank and Excel float-like values."""

    def clean(self, value, row=None, *args, **kwargs):
        if value is None or value == "" or str(value).strip() == "":
            return 0
        try:
            return int(float(str(value).strip().replace(",", ".")))
        except Exception:
            return 0


class SafeDecimalWidget(DecimalWidget):
    """Decimal widget tolerant with blank, dash, and Vietnamese comma numbers."""

    def __init__(self, default=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default = default

    def clean(self, value, row=None, *args, **kwargs):
        if value is None:
            return super().clean(self.default, row, *args, **kwargs) if self.default is not None else None

        value = str(value).strip()
        if value == "" or value in {"-", "--", "nan", "NaN", "None"}:
            return super().clean(self.default, row, *args, **kwargs) if self.default is not None else None

        value = value.replace(" ", "")
        if "," in value and "." in value:
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", ".")

        try:
            return super().clean(value, row, *args, **kwargs)
        except Exception:
            return super().clean(self.default, row, *args, **kwargs) if self.default is not None else None


class FlexibleForeignKeyWidget(ForeignKeyWidget):
    """Widget xử lý foreign key linh hoạt, cho phép tìm kiếm theo nhiều cách"""

    def __init__(self, model, field='id', **kwargs):
        super().__init__(model, field, **kwargs)
        self.missing_parents = []

    def clean(self, value, row=None, **kwargs):
        """
        Tìm kiếm parent thiết bị theo nhiều cách:
        1. Tìm chính xác theo ma_day_du
        2. Tìm theo ma_day_du không phân biệt hoa thường
        3. Nếu không tìm thấy, trả về None thay vì lỗi
        """
        if not value or value == '' or str(value).strip() == '':
            return None

        value = str(value).strip()

        try:
            # Thử tìm chính xác
            obj = self.model.objects.get(ma_day_du=value)
            return obj
        except self.model.DoesNotExist:
            # Thử tìm không phân biệt hoa thường
            try:
                obj = self.model.objects.get(ma_day_du__iexact=value)
                return obj
            except self.model.DoesNotExist:
                # Không tìm thấy, trả về None
                child_code = row.get('ma_day_du', 'N/A') if row else 'N/A'
                self.missing_parents.append((child_code, value))
                return None
        except self.model.MultipleObjectsReturned:
            # Nếu có nhiều kết quả, lấy cái đầu tiên
            return self.model.objects.filter(ma_day_du__iexact=value).first()

    def get_missing_parents(self):
        """Trả về danh sách các parent không tồn tại"""
        return self.missing_parents


class NguongThongSoThietBiWidget(ForeignKeyWidget):
    """Widget thông minh tìm kiếm thiết bị cho cấu hình ngưỡng thông số"""
    def clean(self, value, row=None, **kwargs):
        if not value or value == '' or str(value).strip() == '':
            return None
        value = str(value).strip()

        # 1. Tìm chính xác theo mã đầy đủ (ma_day_du)
        try:
            return self.model.objects.get(ma_day_du__iexact=value)
        except self.model.DoesNotExist:
            pass

        # 2. Tìm theo tên thiết bị (ten) kết hợp mã thông số từ dòng Excel
        ma_thong_so = None
        if row:
            for key in ['ma_thong_so', 'Mã thông số', 'ma_thong_so_id', 'mathongso']:
                if key in row:
                    ma_thong_so = str(row[key]).strip()
                    break

        candidates = self.model.objects.filter(ten__iexact=value)
        if not candidates.exists():
            candidates = self.model.objects.filter(ten__icontains=value)

        if candidates.exists():
            if candidates.count() == 1:
                return candidates.first()

            if ma_thong_so:
                from quanlyvanhanh.models import ThongSoToMay, ThongSoTram110KV, ThongSoVanHanh
                for tb in candidates:
                    if ThongSoToMay.objects.filter(thiet_bi=tb, ma_thong_so=ma_thong_so).exists():
                        return tb
                    if ThongSoTram110KV.objects.filter(thiet_bi=tb, ma_thong_so=ma_thong_so).exists():
                        return tb
                    if ThongSoVanHanh.objects.filter(thiet_bi=tb, ma_thong_so=ma_thong_so).exists():
                        return tb

            return candidates.first()

        return None


# ===================== RESOURCES =====================

class SafeExportChangeListMixin:
    """
    ExportChangeList tương thích Django 3.2:
    - Không truyền search_help_text.
    - Chỉ dùng các getter có sẵn ở 3.2; phần còn lại dùng ATTR fallback.
    """
    def get_export_queryset(self, request):
        # Các getter tồn tại trên Django 3.2
        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        list_select_related = self.get_list_select_related(request)

        # Fallback qua thuộc tính cho các phần Django 3.2 không có getter
        list_editable = getattr(self, "list_editable", ())
        list_per_page = getattr(self, "list_per_page", 100)
        list_max_show_all = getattr(self, "list_max_show_all", 200)
        sortable_by = getattr(self, "sortable_by", None)
        date_hierarchy = getattr(self, "date_hierarchy", None)

        from import_export.admin import ExportChangeList
        cl = ExportChangeList(
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
            self,                    # model_admin
            sortable_by=sortable_by, # kwarg tuỳ chọn, OK ở 3.2
        )
        return cl.get_queryset(request)

    search_help_text = ""

    def get_export_queryset(self, request):
        from django.contrib.admin.views.main import ChangeList

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
            sortable_by,
        )
        return cl.get_queryset(request)

    @admin.action(description="Xuất Excel các bản ghi đã chọn")
    def export_selected_to_excel(self, request, queryset):
        """Xuất Excel các dòng đã chọn sử dụng resource_class"""
        resource_class = self.get_export_resource_class()
        resource = resource_class()
        dataset = resource.export(queryset)
        response = HttpResponse(
            dataset.xlsx,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"{self.model._meta.db_table}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class ThietBiResource(resources.ModelResource):
    # Map cột Excel "cha_ma_day_du" sang FK "cha" của model ThietBi
    cha_ma_day_du = fields.Field(
        column_name="cha_ma_day_du",
        attribute="cha",
        widget=FlexibleForeignKeyWidget(ThietBi, "ma_day_du"),
    )

    # Date fields với widget tolerant định dạng
    ngay_lap_dat = fields.Field(
        column_name="ngay_lap_dat",
        attribute="ngay_lap_dat",
        widget=FlexibleDateWidget(),
    )
    ngay_dua_vao_van_hanh = fields.Field(
        column_name="ngay_dua_vao_van_hanh",
        attribute="ngay_dua_vao_van_hanh",
        widget=FlexibleDateWidget(),
    )
    do_uu_tien = fields.Field(
        column_name="do_uu_tien",
        attribute="do_uu_tien",
        widget=SafeIntegerWidget(),
    )
    thu_tu = fields.Field(
        column_name="thu_tu",
        attribute="thu_tu",
        widget=SafeIntegerWidget(),
    )

    class Meta:
        model = ThietBi
        # Dùng ma_day_du làm khoá định danh để UPDATE nếu đã tồn tại
        import_id_fields = ("ma_day_du",)
        # Các cột được hỗ trợ import/export
        fields = (
            "ma_day_du", "ten", "ma", "cha_ma_day_du", "loai", "trang_thai",
            "nha_che_tao", "nha_cung_cap", "nuoc_san_xuat", "nha_may",
            "do_uu_tien", "so_serial", "ma_van_hanh", "bo_phan_quan_ly",
            "bang_ve", "mo_ta_ky_thuat", "thu_tu",
            "ngay_lap_dat", "ngay_dua_vao_van_hanh",
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True

    # ------------------------ Helpers ------------------------
    def _norm(self, s):
        return "" if s is None else str(s).strip().strip(" .")

    def _ensure_codes(self, row: dict) -> dict:
        """
        Đồng bộ mã: TỪ MA_DAY_DU TỰ ĐỘNG SUY RA MA & CHA_MA_DAY_DU.
        Logic: Chỉ cần điền ma_day_du, chương trình sẽ tự động:
        - ma = phần cuối cùng sau dấu chấm cuối
        - cha_ma_day_du = tất cả phần trước dấu chấm cuối (nếu có)
        GHI ĐÈ tất cả giá trị từ Excel nếu có ma_day_du.
        """
        row = dict(row or {})

        row["ma_day_du"] = self._norm(row.get("ma_day_du"))
        row["cha_ma_day_du"] = self._norm(row.get("cha_ma_day_du"))
        row["ma"] = self._norm(row.get("ma"))
        row["ten"] = self._norm(row.get("ten"))

        # 1) Có ma_day_du -> LUÔN suy ra ma & cha_ma_day_du (ghi đè tất cả)
        if row["ma_day_du"]:
            parts = [p for p in row["ma_day_du"].split(".") if p]
            if parts:
                # LUÔN gán ma từ ma_day_du (ghi đè Excel nếu có)
                row["ma"] = parts[-1]

                # Logic cấp độ: SH.TB.1 = cấp 0, SH.TB.1.2 = cấp 1, SH.TB.1.2.3 = cấp 2
                # Cấp = số dấu chấm - 1 (vì SH.TB.1 có 2 dấu chấm nhưng là cấp 0)
                level = len(parts) - 2  # SH.TB.1 = 3-2=1, nhưng thực tế là cấp 0

                if level <= 0:
                    # Cấp 0: SH.TB.1, SH.TB.2, etc. (không có cha)
                    row["cha_ma_day_du"] = ""
                else:
                    # Cấp > 0: SH.TB.1.CT472, SH.TB.1.2.TI1T1-Pha A (có cha)
                    row["cha_ma_day_du"] = ".".join(parts[:-1])

        # 2) Không có ma_day_du nhưng có ma -> ghép lại
        if not row["ma_day_du"] and row["ma"]:
            row["ma_day_du"] = f"{row['cha_ma_day_du']}.{row['ma']}" if row["cha_ma_day_du"] else row["ma"]

        # 3) Có cả ma & cha_ma_day_du -> chuẩn hoá lại ma_day_du
        if row["ma"] and row["cha_ma_day_du"]:
            expected = f"{row['cha_ma_day_du']}.{row['ma']}"
            if row["ma_day_du"] != expected:
                row["ma_day_du"] = expected

        # 4) Fallback: nếu cả ma & ma_day_du đều trống nhưng có tên -> phát sinh ma
        if not row["ma"] and not row["ma_day_du"] and row["ten"]:
            from django.utils.text import slugify
            row["ma"] = slugify(row["ten"], allow_unicode=False).upper().replace("-", "")
            row["ma_day_du"] = f"{row['cha_ma_day_du']}.{row['ma']}" if row["cha_ma_day_du"] else row["ma"]

        # 5) Chuẩn dấu chấm cuối
        row["ma_day_du"] = row["ma_day_du"].rstrip(".")
        row["cha_ma_day_du"] = row["cha_ma_day_du"].rstrip(".")

        return row

    # -------------------- Dataset-level clean --------------------
    def before_import(self, dataset, **kwargs):
        """
        - Đảm bảo dataset có cột 'ma' & 'cha_ma_day_du' để widget FK hoạt động.
        - Loại bỏ dòng thiếu ma_day_du.
        - Bỏ trùng lặp ngay trong file (ưu tiên dòng xuất hiện trước).
        """
        headers = list(dataset.headers or [])
        for required in ("ma", "cha_ma_day_du"):
            if required not in headers:
                headers.append(required)

        new_ds = tablib.Dataset(headers=headers)
        seen = set()
        for idx, raw in enumerate(dataset, start=1):
            row = dict(zip(dataset.headers, raw)) if not isinstance(raw, dict) else {**raw}
            row = self._ensure_codes(row)
            code = row.get("ma_day_du")

            if not code:
                # Bỏ qua dòng không có mã
                continue

            if code in seen:
                continue

            seen.add(code)
            new_ds.append(tuple(row.get(h, "") for h in headers))

        dataset._data = new_ds._data
        dataset.headers = headers

    # -------------------- Row-level clean --------------------
    def before_import_row(self, row, **kwargs):
        """
        Đồng bộ lại mã từng dòng (an toàn nếu before_import không chạy trong 1 số context).
        """
        row.update(self._ensure_codes(row))
        return super().before_import_row(row, **kwargs)

    # -------------------- Import behavior --------------------
    def skip_row(self, *args, **kwargs):
        """
        Luôn cho phép xử lý (không skip). Với import_id_fields, nếu tồn tại sẽ UPDATE.
        """
        return False

    # Không override import_row/before_save_instance để tránh lỗi tham số
    # do khác biệt giữa các phiên bản django-import-export.

    # -------------------- Preview Processing --------------------
    def get_import_data_kwargs(self, request, *args, **kwargs):
        """
        Đảm bảo preview cũng xử lý dữ liệu như import thực tế.
        """
        kwargs = super().get_import_data_kwargs(request, *args, **kwargs)
        # Force processing in preview mode
        kwargs['dry_run'] = False
        return kwargs

    # -------------------- Report (tuỳ chọn) --------------------
    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)


class VatTuResource(resources.ModelResource):
    """Resource cho import/export Vật tư"""

    class Meta:
        model = VatTu
        import_id_fields = ("ma_vat_tu",)
        fields = (
            "ma_vat_tu", "ten_vat_tu", "don_vi_tinh", "quy_cach",
            "nha_che_tao", "nha_cung_cap"
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class ThietBiVatTuResource(resources.ModelResource):
    """Resource cho import/export Vật tư gắn thiết bị"""
    thiet_bi_ma = fields.Field(
        column_name="thiet_bi_ma_day_du",
        attribute="thiet_bi",
        widget=ForeignKeyWidget(ThietBi, "ma_day_du"),
    )
    vat_tu_ma = fields.Field(
        column_name="ma_vat_tu",
        attribute="vat_tu",
        widget=ForeignKeyWidget(VatTu, "ma_vat_tu"),
    )
    so_luong = fields.Field(
        column_name="so_luong",
        attribute="so_luong",
        widget=SafeDecimalWidget(default="1"),
    )

    class Meta:
        model = ThietBiVatTu
        fields = ("thiet_bi_ma", "vat_tu_ma", "so_luong", "ghi_chu")
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class ThongSoVanHanhResource(resources.ModelResource):
    """Resource cho import/export Thông số vận hành"""
    thiet_bi_ma = fields.Field(
        column_name="Mã thiết bị",
        attribute="thiet_bi",
        widget=ForeignKeyWidget(ThietBi, "ma_day_du"),
    )
    thiet_bi_ten = fields.Field(
        column_name="Tên thiết bị",
        attribute="thiet_bi__ten",
        readonly=True,
    )
    ten_thong_so = fields.Field(
        column_name="Tên thông số",
        attribute="ten_thong_so",
    )
    ma_thong_so = fields.Field(
        column_name="Mã thông số",
        attribute="ma_thong_so",
    )
    don_vi = fields.Field(
        column_name="Đơn vị",
        attribute="don_vi",
    )
    ky_hieu_van_hanh = fields.Field(
        column_name="Ký hiệu vận hành",
        attribute="ky_hieu_van_hanh",
    )
    nha_may = fields.Field(
        column_name="Nhà máy",
        attribute="nha_may",
    )
    gia_tri = fields.Field(
        column_name="Giá trị",
        attribute="gia_tri",
    )
    gia_tri_thiet_ke = fields.Field(
        column_name="Giá trị thiết kế",
        attribute="gia_tri_thiet_ke",
    )
    gia_tri_toi_da = fields.Field(
        column_name="Giá trị tối đa",
        attribute="gia_tri_toi_da",
    )
    gia_tri_toi_thieu = fields.Field(
        column_name="Giá trị tối thiểu",
        attribute="gia_tri_toi_thieu",
    )
    thoi_diem_nhap = fields.Field(
        column_name="Thời điểm nhập",
        attribute="thoi_diem_nhap",
    )

    class Meta:
        model = ThongSoVanHanh
        import_id_fields = ("thiet_bi_ma", "ma_thong_so", "thoi_diem_nhap")  # Sử dụng mã thiết bị + mã thông số + thời điểm làm khóa định danh
        fields = (
            "thiet_bi_ma", "thiet_bi_ten", "ten_thong_so", "ma_thong_so", "don_vi", "ky_hieu_van_hanh",
            "nha_may", "gia_tri", "gia_tri_thiet_ke", "gia_tri_toi_da", "gia_tri_toi_thieu", "thoi_diem_nhap"
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class AnToanThietBiResource(resources.ModelResource):
    """Resource cho import/export An toàn thiết bị"""
    thiet_bi_ma = fields.Field(
        column_name="thiet_bi_ma_day_du",
        attribute="thiet_bi",
        widget=ForeignKeyWidget(ThietBi, "ma_day_du"),
    )

    class Meta:
        model = AnToanThietBi
        fields = (
            "thiet_bi_ma", "moi_nguy", "bien_phap",
            "bao_ho_lao_dong", "ghi_chu"
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class ThongSoToMayResource(resources.ModelResource):
    """Resource cho import/export Thông số tổ máy"""
    thiet_bi_ma = fields.Field(
        column_name="Mã thiết bị",
        attribute="thiet_bi",
        widget=ForeignKeyWidget(ThietBi, "ma_day_du"),
    )
    thiet_bi_ten = fields.Field(
        column_name="Tên thiết bị",
        attribute="thiet_bi__ten",
        readonly=True,
    )
    ten_thong_so = fields.Field(
        column_name="Tên thông số",
        attribute="ten_thong_so",
    )
    ma_thong_so = fields.Field(
        column_name="Mã thông số",
        attribute="ma_thong_so",
    )
    don_vi = fields.Field(
        column_name="Đơn vị",
        attribute="don_vi",
    )
    ky_hieu_van_hanh = fields.Field(
        column_name="Ký hiệu vận hành",
        attribute="ky_hieu_van_hanh",
    )
    nha_may = fields.Field(
        column_name="Nhà máy",
        attribute="nha_may",
    )
    gia_tri = fields.Field(
        column_name="Giá trị",
        attribute="gia_tri",
    )
    thoi_diem_nhap = fields.Field(
        column_name="Thời điểm nhập",
        attribute="thoi_diem_nhap",
    )
    ngay_nhap = fields.Field(
        column_name="Ngày nhập",
        attribute="ngay_nhap",
        widget=FlexibleDateWidget(),
    )

    class Meta:
        model = ThongSoToMay
        import_id_fields = ("thiet_bi_ma", "ma_thong_so", "thoi_diem_nhap", "ngay_nhap")
        fields = (
            "thiet_bi_ma", "thiet_bi_ten", "ten_thong_so", "ma_thong_so", "don_vi", "ky_hieu_van_hanh",
            "nha_may", "gia_tri", "thoi_diem_nhap", "ngay_nhap", "ghi_chu"
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


class ThongSoTram110KVResource(resources.ModelResource):
    """Resource cho import/export Thông số trạm 110kV"""
    thiet_bi_ma = fields.Field(
        column_name="Mã thiết bị",
        attribute="thiet_bi",
        widget=ForeignKeyWidget(ThietBi, "ma_day_du"),
    )
    thiet_bi_ten = fields.Field(
        column_name="Tên thiết bị",
        attribute="thiet_bi__ten",
        readonly=True,
    )
    ten_thong_so = fields.Field(
        column_name="Tên thông số",
        attribute="ten_thong_so",
    )
    ma_thong_so = fields.Field(
        column_name="Mã thông số",
        attribute="ma_thong_so",
    )
    don_vi = fields.Field(
        column_name="Đơn vị",
        attribute="don_vi",
    )
    ky_hieu_van_hanh = fields.Field(
        column_name="Ký hiệu vận hành",
        attribute="ky_hieu_van_hanh",
    )
    nha_may = fields.Field(
        column_name="Nhà máy",
        attribute="nha_may",
    )
    gia_tri = fields.Field(
        column_name="Giá trị",
        attribute="gia_tri",
    )
    thoi_diem_nhap = fields.Field(
        column_name="Thời điểm nhập",
        attribute="thoi_diem_nhap",
    )
    ngay_nhap = fields.Field(
        column_name="Ngày nhập",
        attribute="ngay_nhap",
        widget=FlexibleDateWidget(),
    )

    class Meta:
        model = ThongSoTram110KV
        import_id_fields = ("thiet_bi_ma", "ma_thong_so", "thoi_diem_nhap", "ngay_nhap")
        fields = (
            "thiet_bi_ma", "thiet_bi_ten", "ten_thong_so", "ma_thong_so", "don_vi", "ky_hieu_van_hanh",
            "nha_may", "gia_tri", "thoi_diem_nhap", "ngay_nhap", "ghi_chu"
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True


# ===================== MIXIN =====================

class XLSXOnlyMixin:
    """Chỉ cho phép XLSX"""
    formats = (base_formats.XLSX,)

    def get_import_formats(self):
        return list(self.formats)

    def get_export_formats(self):
        return list(self.formats)


# ===================== HELPERS =====================

def format_datetime_24h(dt_field_name, description=None):
    """Helper decorator để tạo method hiển thị datetime theo định dạng 24 giờ"""
    def decorator(func):
        def wrapper(self, obj):
            """Hiển thị thời gian theo định dạng 24 giờ"""
            dt_value = getattr(obj, dt_field_name, None)
            if dt_value:
                # Chuyển về Vietnam timezone và hiển thị theo định dạng 24h
                import pytz
                vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                if dt_value.tzinfo is None:
                    # Nếu không có timezone, giả sử là UTC
                    utc_tz = pytz.UTC
                    dt_utc = utc_tz.localize(dt_value)
                else:
                    dt_utc = dt_value.astimezone(pytz.UTC)

                dt_vietnam = dt_utc.astimezone(vietnam_tz)
                return dt_vietnam.strftime('%d/%m/%Y %H:%M:%S')
            return '-'

        wrapper.short_description = description or f'{dt_field_name} (24h)'
        wrapper.admin_order_field = dt_field_name
        return wrapper
    return decorator


# ===================== ADMINS =====================

@admin.register(ThietBi)
class ThietBiAdmin(SafeExportChangeListMixin, XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThietBiResource
    list_display = ['hinh_anh_thumbnail', 'ma_day_du', 'ten', 'nha_may', 'loai', 'trang_thai', 'nha_che_tao', 'ngay_lap_dat_24h', 'ngay_dua_vao_van_hanh_24h', 'cap', 'thu_tu', 'do_uu_tien']
    list_filter = ['nha_may']
    search_fields = ['ten', 'ma', 'ma_day_du', 'so_serial', 'ma_van_hanh', 'bo_phan_quan_ly', 'bang_ve']
    list_editable = ['thu_tu', 'do_uu_tien']
    ordering = ['cha__id', 'thu_tu', 'ten']
    actions = ['delete_selected', 'delete_by_type', 'delete_by_status']

    @admin.action(description="Xóa các thiết bị đã chọn")
    def delete_selected(self, request, queryset):
        """Xóa các thiết bị đã chọn"""
        count = queryset.count()
        if count > 0:
            queryset.delete()
            self.message_user(request, f"Đã xóa {count} thiết bị.")
        else:
            self.message_user(request, "Không có thiết bị nào được chọn để xóa.")

    @admin.action(description="Xóa theo loại thiết bị đã chọn")
    def delete_by_type(self, request, queryset):
        """Xóa tất cả thiết bị theo loại của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách loại từ các bản ghi đã chọn
            types = queryset.values_list('loai', flat=True).distinct()
            total_deleted = 0

            for device_type in types:
                deleted_count = ThietBi.objects.filter(loai=device_type).count()
                ThietBi.objects.filter(loai=device_type).delete()
                total_deleted += deleted_count
                self.message_user(request, f"Đã xóa {deleted_count} thiết bị loại '{device_type}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thiết bị.")
        else:
            self.message_user(request, "Không có thiết bị nào được chọn.")

    @admin.action(description="Xóa theo trạng thái thiết bị đã chọn")
    def delete_by_status(self, request, queryset):
        """Xóa tất cả thiết bị theo trạng thái của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách trạng thái từ các bản ghi đã chọn
            statuses = queryset.values_list('trang_thai', flat=True).distinct()
            total_deleted = 0

            for status in statuses:
                deleted_count = ThietBi.objects.filter(trang_thai=status).count()
                ThietBi.objects.filter(trang_thai=status).delete()
                total_deleted += deleted_count
                self.message_user(request, f"Đã xóa {deleted_count} thiết bị trạng thái '{status}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thiết bị.")
        else:
            self.message_user(request, "Không có thiết bị nào được chọn.")

    def ngay_lap_dat_24h(self, obj):
        """Hiển thị ngày lắp đặt theo định dạng 24 giờ"""
        if obj.ngay_lap_dat:
            return obj.ngay_lap_dat.strftime('%d/%m/%Y')
        return '-'
    ngay_lap_dat_24h.short_description = 'Ngày lắp đặt'
    ngay_lap_dat_24h.admin_order_field = 'ngay_lap_dat'

    def ngay_dua_vao_van_hanh_24h(self, obj):
        """Hiển thị ngày đưa vào vận hành theo định dạng 24 giờ"""
        if obj.ngay_dua_vao_van_hanh:
            return obj.ngay_dua_vao_van_hanh.strftime('%d/%m/%Y')
        return '-'
    ngay_dua_vao_van_hanh_24h.short_description = 'Ngày đưa vào vận hành'
    ngay_dua_vao_van_hanh_24h.admin_order_field = 'ngay_dua_vao_van_hanh'

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('ten', 'ma', 'ma_day_du', 'cha', 'loai', 'trang_thai')
        }),
        ('Thông tin nhà sản xuất', {
            'fields': ('nha_che_tao', 'nha_cung_cap', 'nuoc_san_xuat', 'nha_may')
        }),
        ('Thông tin kỹ thuật', {
            'fields': ('so_serial', 'ma_van_hanh', 'bo_phan_quan_ly', 'bang_ve', 'mo_ta_ky_thuat', 'do_uu_tien', 'thu_tu')
        }),
        ('Thời gian', {
            'fields': ('ngay_lap_dat', 'ngay_dua_vao_van_hanh')
        }),
        ('Hình ảnh', {
            'fields': ('hinh_anh', 'hinh_anh_preview')
        }),
        ('QR Code', {
            'fields': ('qrcode_preview',)
        }),
    )
    readonly_fields = ('qrcode_preview', 'hinh_anh_preview')

    def hinh_anh_thumbnail(self, obj):
        """Hiển thị thumbnail nhỏ trong danh sách"""
        if obj and obj.hinh_anh:
            return format_html('<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />', obj.hinh_anh.url)
        return "—"
    hinh_anh_thumbnail.short_description = "Ảnh"

    def hinh_anh_preview(self, obj):
        """Hiển thị preview hình ảnh thiết bị"""
        if obj and obj.hinh_anh:
            return format_html('<img src="{}" style="max-width: 300px; max-height: 300px;" />', obj.hinh_anh.url)
        return "—"
    hinh_anh_preview.short_description = "Xem trước hình ảnh"

    def qrcode_preview(self, obj):
        """Hiển thị QR code preview"""
        if not obj or not obj.pk:
            return ""
        url = f"https://YOUR_DOMAIN/app/thiet-bi/{obj.ma_day_du}?include_subtree=1"
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = base64.b64encode(buf.getvalue()).decode("ascii")
        return mark_safe(f'<img src="data:image/png;base64,{data}" alt="QR" width="160" height="160" />')
    qrcode_preview.short_description = "Mã QR"

    @admin.action(description="Xuất QR (ZIP) cho các thiết bị đã chọn")
    def export_qr_zip(self, request, queryset):
        """Xuất QR codes dạng ZIP"""
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
            for tb in queryset:
                url = f"https://YOUR_DOMAIN/app/thiet-bi/{tb.ma_day_du}?include_subtree=1"
                img = qrcode.make(url)
                ibuf = io.BytesIO()
                img.save(ibuf, format="PNG")
                ibuf.seek(0)
                z.writestr(f"{tb.ma_day_du.replace('.','_')}.png", ibuf.read())
        zbuf.seek(0)
        resp = HttpResponse(zbuf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="qr_thietbi.zip"'
        return resp

    actions = ["export_qr_zip"]


@admin.register(VatTu)
class VatTuAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = VatTuResource
    list_display = ['ma_vat_tu', 'ten_vat_tu', 'don_vi_tinh', 'nha_che_tao', 'nha_cung_cap']
    list_filter = ['nha_che_tao', 'nha_cung_cap', 'don_vi_tinh']
    search_fields = ['ma_vat_tu', 'ten_vat_tu', 'quy_cach']
    ordering = ['ma_vat_tu']
    actions = ['delete_selected', 'delete_by_manufacturer', 'delete_by_supplier']

    @admin.action(description="Xóa các vật tư đã chọn")
    def delete_selected(self, request, queryset):
        """Xóa các vật tư đã chọn"""
        count = queryset.count()
        if count > 0:
            queryset.delete()
            self.message_user(request, f"Đã xóa {count} vật tư.")
        else:
            self.message_user(request, "Không có vật tư nào được chọn để xóa.")

    @admin.action(description="Xóa theo nhà chế tạo đã chọn")
    def delete_by_manufacturer(self, request, queryset):
        """Xóa tất cả vật tư theo nhà chế tạo của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách nhà chế tạo từ các bản ghi đã chọn
            manufacturers = queryset.values_list('nha_che_tao', flat=True).distinct()
            total_deleted = 0

            for manufacturer in manufacturers:
                if manufacturer:  # Chỉ xóa nếu có nhà chế tạo
                    deleted_count = VatTu.objects.filter(nha_che_tao=manufacturer).count()
                    VatTu.objects.filter(nha_che_tao=manufacturer).delete()
                    total_deleted += deleted_count
                    self.message_user(request, f"Đã xóa {deleted_count} vật tư của nhà chế tạo '{manufacturer}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} vật tư.")
        else:
            self.message_user(request, "Không có vật tư nào được chọn.")

    @admin.action(description="Xóa theo nhà cung cấp đã chọn")
    def delete_by_supplier(self, request, queryset):
        """Xóa tất cả vật tư theo nhà cung cấp của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách nhà cung cấp từ các bản ghi đã chọn
            suppliers = queryset.values_list('nha_cung_cap', flat=True).distinct()
            total_deleted = 0

            for supplier in suppliers:
                if supplier:  # Chỉ xóa nếu có nhà cung cấp
                    deleted_count = VatTu.objects.filter(nha_cung_cap=supplier).count()
                    VatTu.objects.filter(nha_cung_cap=supplier).delete()
                    total_deleted += deleted_count
                    self.message_user(request, f"Đã xóa {deleted_count} vật tư của nhà cung cấp '{supplier}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} vật tư.")
        else:
            self.message_user(request, "Không có vật tư nào được chọn.")


@admin.register(ThietBiVatTu)
class ThietBiVatTuAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThietBiVatTuResource
    list_display = ['thiet_bi', 'vat_tu', 'so_luong', 'ghi_chu']
    list_filter = ['thiet_bi__loai', 'vat_tu__nha_che_tao']
    search_fields = ['thiet_bi__ten', 'vat_tu__ten_vat_tu', 'ghi_chu']
    autocomplete_fields = ['thiet_bi', 'vat_tu']
    actions = ['delete_selected', 'delete_by_device', 'delete_by_material']

    @admin.action(description="Xóa các liên kết thiết bị-vật tư đã chọn")
    def delete_selected(self, request, queryset):
        """Xóa các liên kết thiết bị-vật tư đã chọn"""
        count = queryset.count()
        if count > 0:
            queryset.delete()
            self.message_user(request, f"Đã xóa {count} liên kết thiết bị-vật tư.")
        else:
            self.message_user(request, "Không có liên kết nào được chọn để xóa.")

    @admin.action(description="Xóa theo thiết bị đã chọn")
    def delete_by_device(self, request, queryset):
        """Xóa tất cả liên kết theo thiết bị của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách thiết bị từ các bản ghi đã chọn
            devices = queryset.values_list('thiet_bi', flat=True).distinct()
            total_deleted = 0

            for device_id in devices:
                deleted_count = ThietBiVatTu.objects.filter(thiet_bi_id=device_id).count()
                ThietBiVatTu.objects.filter(thiet_bi_id=device_id).delete()
                total_deleted += deleted_count
                device = queryset.filter(thiet_bi_id=device_id).first().thiet_bi
                self.message_user(request, f"Đã xóa {deleted_count} liên kết của thiết bị '{device.ten}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} liên kết.")
        else:
            self.message_user(request, "Không có liên kết nào được chọn.")

    @admin.action(description="Xóa theo vật tư đã chọn")
    def delete_by_material(self, request, queryset):
        """Xóa tất cả liên kết theo vật tư của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách vật tư từ các bản ghi đã chọn
            materials = queryset.values_list('vat_tu', flat=True).distinct()
            total_deleted = 0

            for material_id in materials:
                deleted_count = ThietBiVatTu.objects.filter(vat_tu_id=material_id).count()
                ThietBiVatTu.objects.filter(vat_tu_id=material_id).delete()
                total_deleted += deleted_count
                material = queryset.filter(vat_tu_id=material_id).first().vat_tu
                self.message_user(request, f"Đã xóa {deleted_count} liên kết của vật tư '{material.ten_vat_tu}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} liên kết.")
        else:
            self.message_user(request, "Không có liên kết nào được chọn.")


@admin.register(ThongSoVanHanh)
class ThongSoVanHanhAdmin(SafeExportChangeListMixin, XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThongSoVanHanhResource
    list_display = ['thiet_bi', 'ma_thong_so', 'ten_thong_so', 'gia_tri', 'nha_may', 'thoi_diem_nhap_24h']
    list_filter = ['nha_may', 'ngay_nhap', 'thoi_diem_nhap']
    search_fields = ['ma_thong_so', 'ten_thong_so', 'gia_tri', 'ghi_chu', 'nha_may', 'ky_hieu_van_hanh']
    autocomplete_fields = ['thiet_bi']
    readonly_fields = ['thoi_diem_nhap', 'ngay_nhap']
    actions = ['delete_selected', 'delete_by_date', 'delete_by_device', 'delete_by_parameter', 'export_selected_to_excel']

    @admin.action(description="Xóa các thông số đã chọn")
    def delete_selected(self, request, queryset):
        """Xóa các thông số đã chọn"""
        count = queryset.count()
        if count > 0:
            queryset.delete()
            self.message_user(request, f"Đã xóa {count} thông số vận hành.")
        else:
            self.message_user(request, "Không có thông số nào được chọn để xóa.")

    @admin.action(description="Xóa theo ngày đã chọn")
    def delete_by_date(self, request, queryset):
        """Xóa tất cả thông số theo ngày của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách ngày từ các bản ghi đã chọn
            dates = queryset.values_list('ngay_nhap', flat=True).distinct()
            total_deleted = 0

            for date in dates:
                deleted_count = ThongSoVanHanh.objects.filter(ngay_nhap=date).count()
                ThongSoVanHanh.objects.filter(ngay_nhap=date).delete()
                total_deleted += deleted_count
                self.message_user(request, f"Đã xóa {deleted_count} thông số của ngày {date}.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    @admin.action(description="Xóa theo thiết bị đã chọn")
    def delete_by_device(self, request, queryset):
        """Xóa tất cả thông số theo thiết bị của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách thiết bị từ các bản ghi đã chọn
            devices = queryset.values_list('thiet_bi', flat=True).distinct()
            total_deleted = 0

            for device_id in devices:
                device = queryset.first().thiet_bi if queryset.exists() else None
                if device:
                    deleted_count = ThongSoVanHanh.objects.filter(thiet_bi=device).count()
                    ThongSoVanHanh.objects.filter(thiet_bi=device).delete()
                    total_deleted += deleted_count
                    self.message_user(request, f"Đã xóa {deleted_count} thông số của thiết bị {device.ten}.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    @admin.action(description="Xóa theo thông số đã chọn")
    def delete_by_parameter(self, request, queryset):
        """Xóa tất cả thông số theo mã thông số của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách mã thông số từ các bản ghi đã chọn
            parameters = queryset.values_list('ma_thong_so', flat=True).distinct()
            total_deleted = 0

            for param in parameters:
                deleted_count = ThongSoVanHanh.objects.filter(ma_thong_so=param).count()
                ThongSoVanHanh.objects.filter(ma_thong_so=param).delete()
                total_deleted += deleted_count
                self.message_user(request, f"Đã xóa {deleted_count} thông số có mã '{param}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    def thoi_diem_nhap_24h(self, obj):
        """Hiển thị thời gian theo định dạng 24 giờ"""
        if obj.thoi_diem_nhap:
            # Chuyển về Vietnam timezone và hiển thị theo định dạng 24h
            import pytz
            vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
            if obj.thoi_diem_nhap.tzinfo is None:
                # Nếu không có timezone, giả sử là UTC
                utc_tz = pytz.UTC
                dt_utc = utc_tz.localize(obj.thoi_diem_nhap)
            else:
                dt_utc = obj.thoi_diem_nhap.astimezone(pytz.UTC)

            dt_vietnam = dt_utc.astimezone(vietnam_tz)
            return dt_vietnam.strftime('%d/%m/%Y %H:%M:%S')
        return '-'
    thoi_diem_nhap_24h.short_description = 'Thời điểm nhập (24h)'
    thoi_diem_nhap_24h.admin_order_field = 'thoi_diem_nhap'

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('thiet_bi', 'ma_thong_so', 'ten_thong_so', 'gia_tri', 'don_vi')
        }),
        ('Giá trị giới hạn', {
            'fields': ('gia_tri_toi_thieu', 'gia_tri_toi_da', 'gia_tri_thiet_ke')
        }),
        ('Thông tin bổ sung', {
            'fields': ('ky_hieu_van_hanh', 'nha_may', 'ghi_chu')
        }),
        ('Thời gian', {
            'fields': ('thoi_diem_nhap', 'ngay_nhap')
        }),
    )


@admin.register(AnToanThietBi)
class AnToanThietBiAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = AnToanThietBiResource
    list_display = ['thiet_bi', 'moi_nguy', 'bao_ho_lao_dong']
    list_filter = ['thiet_bi__loai', 'bao_ho_lao_dong']
    search_fields = ['moi_nguy', 'bien_phap', 'bao_ho_lao_dong']
    autocomplete_fields = ['thiet_bi']


@admin.register(DinhKem)
class DinhKemAdmin(admin.ModelAdmin):
    list_display = ['thiet_bi', 'tieu_de', 'dinh_dang', 'ngay_tai_len_24h']
    list_filter = ['dinh_dang', 'ngay_tai_len', 'thiet_bi__loai']
    search_fields = ['tieu_de', 'thiet_bi__ten']
    autocomplete_fields = ['thiet_bi']
    readonly_fields = ['ngay_tai_len']

    def ngay_tai_len_24h(self, obj):
        """Hiển thị thời gian theo định dạng 24 giờ"""
        if obj.ngay_tai_len:
            # Chuyển về Vietnam timezone và hiển thị theo định dạng 24h
            import pytz
            vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
            if obj.ngay_tai_len.tzinfo is None:
                # Nếu không có timezone, giả sử là UTC
                utc_tz = pytz.UTC
                dt_utc = utc_tz.localize(obj.ngay_tai_len)
            else:
                dt_utc = obj.ngay_tai_len.astimezone(pytz.UTC)

            dt_vietnam = dt_utc.astimezone(vietnam_tz)
            return dt_vietnam.strftime('%d/%m/%Y %H:%M:%S')
        return '-'
    ngay_tai_len_24h.short_description = 'Ngày tải lên (24h)'
    ngay_tai_len_24h.admin_order_field = 'ngay_tai_len'


@admin.register(ThongSoToMay)
class ThongSoToMayAdmin(SafeExportChangeListMixin, XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThongSoToMayResource
    list_display = ['thiet_bi', 'ma_thong_so', 'ten_thong_so', 'gia_tri', 'nha_may', 'thoi_diem_nhap_24h', 'ngay_nhap_24h']
    list_filter = ['nha_may', 'ngay_nhap', 'thoi_diem_nhap']
    search_fields = ['ma_thong_so', 'ten_thong_so', 'gia_tri', 'ghi_chu', 'nha_may', 'ky_hieu_van_hanh', 'thiet_bi__ten']
    autocomplete_fields = ['thiet_bi']
    readonly_fields = ['thoi_diem_nhap', 'ngay_nhap']
    actions = ['delete_selected', 'delete_by_date', 'delete_by_device', 'delete_by_parameter', 'delete_by_plant', 'export_selected_to_excel']

    @admin.action(description="Xóa các thông số tổ máy đã chọn")
    def delete_selected(self, request, queryset):
        """Xóa các thông số tổ máy đã chọn"""
        count = queryset.count()
        if count > 0:
            queryset.delete()
            self.message_user(request, f"Đã xóa {count} thông số tổ máy.")
        else:
            self.message_user(request, "Không có thông số nào được chọn để xóa.")

    @admin.action(description="Xóa theo ngày đã chọn")
    def delete_by_date(self, request, queryset):
        """Xóa tất cả thông số theo ngày của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách ngày từ các bản ghi đã chọn
            dates = queryset.values_list('ngay_nhap', flat=True).distinct()
            total_deleted = 0

            for date in dates:
                deleted_count = ThongSoToMay.objects.filter(ngay_nhap=date).count()
                ThongSoToMay.objects.filter(ngay_nhap=date).delete()
                total_deleted += deleted_count
                self.message_user(request, f"Đã xóa {deleted_count} thông số của ngày {date}.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    @admin.action(description="Xóa theo thiết bị đã chọn")
    def delete_by_device(self, request, queryset):
        """Xóa tất cả thông số theo thiết bị của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách thiết bị từ các bản ghi đã chọn
            devices = queryset.values_list('thiet_bi', flat=True).distinct()
            total_deleted = 0

            for device_id in devices:
                device = queryset.filter(thiet_bi_id=device_id).first().thiet_bi
                if device:
                    deleted_count = ThongSoToMay.objects.filter(thiet_bi=device).count()
                    ThongSoToMay.objects.filter(thiet_bi=device).delete()
                    total_deleted += deleted_count
                    self.message_user(request, f"Đã xóa {deleted_count} thông số của thiết bị {device.ten}.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    @admin.action(description="Xóa theo thông số đã chọn")
    def delete_by_parameter(self, request, queryset):
        """Xóa tất cả thông số theo mã thông số của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách mã thông số từ các bản ghi đã chọn
            parameters = queryset.values_list('ma_thong_so', flat=True).distinct()
            total_deleted = 0

            for param in parameters:
                deleted_count = ThongSoToMay.objects.filter(ma_thong_so=param).count()
                ThongSoToMay.objects.filter(ma_thong_so=param).delete()
                total_deleted += deleted_count
                self.message_user(request, f"Đã xóa {deleted_count} thông số có mã '{param}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    @admin.action(description="Xóa theo nhà máy đã chọn")
    def delete_by_plant(self, request, queryset):
        """Xóa tất cả thông số theo nhà máy của các bản ghi đã chọn"""
        if queryset.exists():
            # Lấy danh sách nhà máy từ các bản ghi đã chọn
            plants = queryset.values_list('nha_may', flat=True).distinct()
            total_deleted = 0

            for plant in plants:
                if plant:  # Chỉ xóa nếu có nhà máy
                    deleted_count = ThongSoToMay.objects.filter(nha_may=plant).count()
                    ThongSoToMay.objects.filter(nha_may=plant).delete()
                    total_deleted += deleted_count
                    self.message_user(request, f"Đã xóa {deleted_count} thông số của nhà máy '{plant}'.")

            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    def thoi_diem_nhap_24h(self, obj):
        """Hiển thị thời gian theo định dạng 24 giờ"""
        if obj.thoi_diem_nhap:
            return obj.thoi_diem_nhap.strftime('%H:%M')
        return '-'
    thoi_diem_nhap_24h.short_description = 'Thời điểm nhập'
    thoi_diem_nhap_24h.admin_order_field = 'thoi_diem_nhap'

    def ngay_nhap_24h(self, obj):
        """Hiển thị ngày nhập theo định dạng 24 giờ"""
        if obj.ngay_nhap:
            return obj.ngay_nhap.strftime('%d/%m/%Y')
        return '-'
    ngay_nhap_24h.short_description = 'Ngày nhập'
    ngay_nhap_24h.admin_order_field = 'ngay_nhap'

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('thiet_bi', 'ma_thong_so', 'ten_thong_so', 'gia_tri', 'don_vi')
        }),
        ('Thông tin bổ sung', {
            'fields': ('ky_hieu_van_hanh', 'nha_may', 'ghi_chu')
        }),
        ('Thời gian', {
            'fields': ('thoi_diem_nhap', 'ngay_nhap')
        }),
    )


@admin.register(ThongSoTram110KV)
class ThongSoTram110KVAdmin(SafeExportChangeListMixin, XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = ThongSoTram110KVResource
    list_display = ['thiet_bi', 'ma_thong_so', 'ten_thong_so', 'gia_tri', 'nha_may', 'thoi_diem_nhap_24h', 'ngay_nhap_24h']
    list_filter = ['nha_may', 'ngay_nhap', 'thoi_diem_nhap']
    search_fields = ['ma_thong_so', 'ten_thong_so', 'gia_tri', 'ghi_chu', 'nha_may', 'ky_hieu_van_hanh', 'thiet_bi__ten']
    autocomplete_fields = ['thiet_bi']
    readonly_fields = ['thoi_diem_nhap', 'ngay_nhap']
    actions = ['delete_selected', 'delete_by_date', 'delete_by_device', 'delete_by_parameter', 'delete_by_plant', 'export_selected_to_excel']

    @admin.action(description="Xóa các thông số trạm 110kV đã chọn")
    def delete_selected(self, request, queryset):
        """Xóa các thông số trạm 110kV đã chọn"""
        count = queryset.count()
        if count > 0:
            queryset.delete()
            self.message_user(request, f"Đã xóa {count} thông số trạm 110kV.")
        else:
            self.message_user(request, "Không có thông số nào được chọn để xóa.")

    @admin.action(description="Xóa theo ngày đã chọn")
    def delete_by_date(self, request, queryset):
        """Xóa tất cả thông số theo ngày của các bản ghi đã chọn"""
        if queryset.exists():
            dates = queryset.values_list('ngay_nhap', flat=True).distinct()
            total_deleted = 0
            for date in dates:
                deleted_count = ThongSoTram110KV.objects.filter(ngay_nhap=date).count()
                ThongSoTram110KV.objects.filter(ngay_nhap=date).delete()
                total_deleted += deleted_count
                self.message_user(request, f"Đã xóa {deleted_count} thông số của ngày {date}.")
            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    @admin.action(description="Xóa theo thiết bị đã chọn")
    def delete_by_device(self, request, queryset):
        """Xóa tất cả thông số theo thiết bị của các bản ghi đã chọn"""
        if queryset.exists():
            devices = queryset.values_list('thiet_bi', flat=True).distinct()
            total_deleted = 0
            for device_id in devices:
                device = queryset.filter(thiet_bi_id=device_id).first().thiet_bi
                if device:
                    deleted_count = ThongSoTram110KV.objects.filter(thiet_bi=device).count()
                    ThongSoTram110KV.objects.filter(thiet_bi=device).delete()
                    total_deleted += deleted_count
                    self.message_user(request, f"Đã xóa {deleted_count} thông số của thiết bị {device.ten}.")
            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    @admin.action(description="Xóa theo thông số đã chọn")
    def delete_by_parameter(self, request, queryset):
        """Xóa tất cả thông số theo mã thông số của các bản ghi đã chọn"""
        if queryset.exists():
            parameters = queryset.values_list('ma_thong_so', flat=True).distinct()
            total_deleted = 0
            for param in parameters:
                deleted_count = ThongSoTram110KV.objects.filter(ma_thong_so=param).count()
                ThongSoTram110KV.objects.filter(ma_thong_so=param).delete()
                total_deleted += deleted_count
                self.message_user(request, f"Đã xóa {deleted_count} thông số có mã '{param}'.")
            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    @admin.action(description="Xóa theo nhà máy đã chọn")
    def delete_by_plant(self, request, queryset):
        """Xóa tất cả thông số theo nhà máy của các bản ghi đã chọn"""
        if queryset.exists():
            plants = queryset.values_list('nha_may', flat=True).distinct()
            total_deleted = 0
            for plant in plants:
                if plant:
                    deleted_count = ThongSoTram110KV.objects.filter(nha_may=plant).count()
                    ThongSoTram110KV.objects.filter(nha_may=plant).delete()
                    total_deleted += deleted_count
                    self.message_user(request, f"Đã xóa {deleted_count} thông số của nhà máy '{plant}'.")
            self.message_user(request, f"Tổng cộng đã xóa {total_deleted} thông số.")
        else:
            self.message_user(request, "Không có thông số nào được chọn.")

    def thoi_diem_nhap_24h(self, obj):
        """Hiển thị thời gian theo định dạng 24 giờ"""
        if obj.thoi_diem_nhap:
            return obj.thoi_diem_nhap.strftime('%H:%M')
        return '-'
    thoi_diem_nhap_24h.short_description = 'Thời điểm nhập'
    thoi_diem_nhap_24h.admin_order_field = 'thoi_diem_nhap'

    def ngay_nhap_24h(self, obj):
        """Hiển thị ngày nhập theo định dạng 24 giờ"""
        if obj.ngay_nhap:
            return obj.ngay_nhap.strftime('%d/%m/%Y')
        return '-'
    ngay_nhap_24h.short_description = 'Ngày nhập'
    ngay_nhap_24h.admin_order_field = 'ngay_nhap'

    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('thiet_bi', 'ma_thong_so', 'ten_thong_so', 'gia_tri', 'don_vi')
        }),
        ('Thông tin bổ sung', {
            'fields': ('ky_hieu_van_hanh', 'nha_may', 'ghi_chu')
        }),
        ('Thời gian', {
            'fields': ('thoi_diem_nhap', 'ngay_nhap')
        }),
    )


class NguongThongSoResource(resources.ModelResource):
    """Resource cho import/export Ngưỡng thông số"""
    thiet_bi_ma = fields.Field(
        column_name="Mã thiết bị",
        attribute="thiet_bi",
        widget=NguongThongSoThietBiWidget(ThietBi, "ma_day_du"),
    )
    thiet_bi_ten = fields.Field(
        column_name="Tên thiết bị",
        attribute="thiet_bi__ten",
        readonly=True,
    )

    class Meta:
        model = NguongThongSo
        fields = ('id', 'nha_may', 'thiet_bi_ma', 'thiet_bi_ten', 'ma_thong_so', 'ten_thong_so', 'don_vi', 'alarm', 'trip', 'rated')
        export_order = ('id', 'nha_may', 'thiet_bi_ma', 'thiet_bi_ten', 'ma_thong_so', 'ten_thong_so', 'don_vi', 'alarm', 'trip', 'rated')


@admin.register(NguongThongSo)
class NguongThongSoAdmin(SafeExportChangeListMixin, ImportExportModelAdmin):
    resource_class = NguongThongSoResource
    list_display = ['nha_may', 'thiet_bi', 'ma_thong_so', 'ten_thong_so', 'alarm', 'trip', 'rated', 'don_vi']
    list_filter = ['nha_may', 'ma_thong_so']
    search_fields = ['ma_thong_so', 'ten_thong_so', 'thiet_bi__ten', 'thiet_bi__ma_day_du']
    autocomplete_fields = ['thiet_bi']
    actions = ['export_selected_to_excel']

