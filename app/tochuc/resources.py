from datetime import date, datetime

from django.contrib.auth import get_user_model
from import_export import fields, resources, widgets

from .models import BoPhan, DonViToChuc, NhaMay, NhanSu


class OptionalForeignKeyWidget(widgets.ForeignKeyWidget):
    def clean(self, value, row=None, **kwargs):
        if value is None or not str(value).strip():
            return None
        return super().clean(str(value).strip(), row=row, **kwargs)


class DepartmentByUnitWidget(widgets.ForeignKeyWidget):
    def clean(self, value, row=None, **kwargs):
        department_code = str(value or "").strip()
        unit_code = str((row or {}).get("ma_don_vi") or "").strip()
        if not department_code:
            return None
        if not unit_code:
            raise ValueError("Cần có ma_don_vi để xác định bộ phận.")
        return self.model.objects.get(
            ma_bo_phan=department_code,
            don_vi__ma_don_vi=unit_code,
        )

    def render(self, value, obj=None, **kwargs):
        return value.ma_bo_phan if value else ""


class FlexibleDateWidget(widgets.Widget):
    formats = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")

    def clean(self, value, row=None, **kwargs):
        if value is None or not str(value).strip():
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        for date_format in self.formats:
            try:
                return datetime.strptime(str(value).strip(), date_format).date()
            except ValueError:
                continue
        raise ValueError("Ngày phải có định dạng YYYY-MM-DD hoặc DD/MM/YYYY.")

    def render(self, value, obj=None, **kwargs):
        return value.strftime("%d/%m/%Y") if value else ""


class NhaMayResource(resources.ModelResource):
    class Meta:
        model = NhaMay
        import_id_fields = ("ma_nha_may",)
        fields = ("ma_nha_may", "ten_nha_may")
        export_order = fields


class NhanSuResource(resources.ModelResource):
    don_vi = fields.Field(
        column_name="ma_don_vi",
        attribute="don_vi",
        widget=widgets.ForeignKeyWidget(DonViToChuc, "ma_don_vi"),
    )
    bo_phan = fields.Field(
        column_name="ma_bo_phan",
        attribute="bo_phan",
        widget=DepartmentByUnitWidget(BoPhan, "ma_bo_phan"),
    )
    user = fields.Field(
        column_name="username",
        attribute="user",
        widget=OptionalForeignKeyWidget(get_user_model(), "username"),
    )
    tu_ngay = fields.Field(
        column_name="tu_ngay",
        attribute="tu_ngay",
        widget=FlexibleDateWidget(),
    )
    den_ngay = fields.Field(
        column_name="den_ngay",
        attribute="den_ngay",
        widget=FlexibleDateWidget(),
    )

    class Meta:
        model = NhanSu
        import_id_fields = ("ma_nhan_vien",)
        fields = (
            "ma_nhan_vien",
            "ho_ten",
            "don_vi",
            "bo_phan",
            "user",
            "chuc_danh",
            "dien_thoai",
            "tu_ngay",
            "den_ngay",
            "dang_lam_viec",
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        employee_code = str(row.get("ma_nhan_vien") or "").strip()
        if not employee_code:
            raise ValueError("ma_nhan_vien là bắt buộc khi nhập Excel.")
        row["ma_nhan_vien"] = employee_code
