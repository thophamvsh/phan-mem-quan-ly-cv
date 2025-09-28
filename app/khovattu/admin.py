# apps/kho/admin.py
from django.contrib import admin
from django.db import transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.utils.html import format_html
from django.http import HttpResponse
from django.utils import timezone
import io, zipfile

from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget, DateTimeWidget, IntegerWidget
from django.core.exceptions import ValidationError
from django.utils import timezone
from import_export.formats import base_formats  # dùng base_formats.XLSX (class)

from .models import (
    Bang_vat_tu, Bang_vi_tri, Bang_kiem_ke,
    Bang_de_nghi_nhap, Bang_de_nghi_xuat, Bang_nha_may, Bang_xuat_xu
)
from core.models import UserProfile
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms


# ===================== CUSTOM USER FORMS =====================

class SimpleUserCreationForm(UserCreationForm):
    """Custom UserCreationForm with simple password validation"""
    password1 = forms.CharField(
        label="Mật khẩu",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text="Mật khẩu tối thiểu 6 ký tự (không cần phức tạp)"
    )
    password2 = forms.CharField(
        label="Xác nhận mật khẩu",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
        help_text="Nhập lại mật khẩu để xác nhận"
    )

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if len(password1) < 6:
            raise forms.ValidationError("Mật khẩu phải có ít nhất 6 ký tự.")
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Mật khẩu không khớp.")
        return password2

    def _post_clean(self):
        """Override to skip Django's password validation"""
        super()._post_clean()
        # Skip password validation - we handle it in clean_password1/2


class SimpleUserChangeForm(UserChangeForm):
    """Custom UserChangeForm with simple password validation"""
    password = forms.CharField(
        label="Mật khẩu mới",
        required=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text="Để trống nếu không muốn thay đổi mật khẩu. Tối thiểu 6 ký tự."
    )

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if password and len(password) < 6:
            raise forms.ValidationError("Mật khẩu phải có ít nhất 6 ký tự.")
        return password

    def _post_clean(self):
        """Override to skip Django's password validation"""
        super()._post_clean()
        # Skip password validation - we handle it in clean_password


class SafeIntegerWidget(IntegerWidget):
    """Custom IntegerWidget that converts empty/None values to 0 instead of None"""
    def clean(self, value, row=None, *args, **kwargs):
        if value is None or value == "" or str(value).strip() == "":
            return 0
        try:
            return super().clean(value, row, *args, **kwargs)
        except Exception:  # Catch all exceptions including decimal.InvalidOperation
            return 0


# Helper: chuẩn hoá header Excel
def _normalize_header(h: str) -> str:
    if not h:
        return h
    key = str(h).strip().lower()
    mapping = {
        "mã nhà máy": "ma_nha_may", "ma nha may": "ma_nha_may", "nhà máy": "ma_nha_may",
        "tên nhà máy": "ten_nha_may", "ten nha may": "ten_nha_may",
        "mã bravo": "ma_bravo", "ma bravo": "ma_bravo",
        "số lượng": "so_luong", "so luong": "so_luong",
        "đơn vị": "don_vi", "don vi": "don_vi",
        "ngày đề nghị": "ngay_de_nghi", "ngay de nghi": "ngay_de_nghi",
        "ngày đề nghị xuất": "ngay_de_nghi_xuat", "ngay de nghi xuat": "ngay_de_nghi_xuat",
        "stt": "stt",
        "tên vật tư": "ten_vat_tu", "ten vat tu": "ten_vat_tu",
    }
    return mapping.get(key, key)

# ===================== WIDGET TRA VẬT TƯ THEO NHÀ MÁY + MÃ BRAVO =====================
class VatTuByBravoAndPlantWidget(ForeignKeyWidget):
    """
    Tìm Bang_vat_tu theo ma_bravo và nhà máy LẤY TỪ DÒNG FILE:
    - Ưu tiên 'ma_nha_may'; nếu không có, thử 'ten_nha_may' (so khớp iexact).
    - Nếu thiếu cả hai -> raise lỗi yêu cầu bổ sung cột nhà máy.
    """
    def clean(self, value, row=None, *args, **kwargs):
        code = (value or "").strip()
        if not code:
            return None
        qs = Bang_vat_tu.objects

        plant_code = (row.get("ma_nha_may") or row.get("nha_may") or "").strip() if row else ""
        plant_name = (row.get("ten_nha_may") or "").strip() if row else ""

        try:
            if plant_code:
                return qs.get(ma_bravo=code, bang_nha_may__ma_nha_may=plant_code)
            if plant_name:
                return qs.get(ma_bravo=code, bang_nha_may__ten_nha_may__iexact=plant_name)
            raise ValueError("Thiếu cột 'ma_nha_may' hoặc 'ten_nha_may' trong file.")
        except Bang_vat_tu.DoesNotExist:
            raise ValueError(f"Không tìm thấy vật tư '{code}' cho nhà máy đã ghi trong file.")

# ===================== TIỆN ÍCH CHUNG =====================
def _is_dry_run(args, kwargs):
    """Bắt tham số dry_run cho mọi phiên bản django-import-export (positional/keyword)."""
    if "dry_run" in kwargs:
        return bool(kwargs["dry_run"])
    # một số phiên bản truyền (instance, using_transactions, dry_run)
    if len(args) >= 2:
        return bool(args[1])
    if len(args) == 1:
        return bool(args[0])
    return False

class AlwaysCreateResource(resources.ModelResource):
    """Luôn tạo bản ghi mới, bỏ qua id để không đòi cột 'id' trong Excel."""
    def get_instance(self, instance_loader, row):
        return None

    class Meta:
        import_id_fields = ()   # không dùng id
        skip_unchanged = True
        report_skipped = True
        use_bulk = False        # để chạy các hook sau mỗi dòng

# ===================== RESOURCES =====================

# -------- VẬT TƯ (sinh QR sau import) --------
class SafeForeignKeyWidget(ForeignKeyWidget):
    """Widget chỉ tìm existing records, không tạo mới"""
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return None
        try:
            return super().clean(value, row, *args, **kwargs)
        except Exception:
            # Nếu không tìm thấy, return None thay vì tạo mới
            print(f"⚠️  Không tìm thấy vị trí với mã '{value}', bỏ qua")
            return None

class BangVatTuResource(resources.ModelResource):
    ma_vi_tri = fields.Field(
        column_name="ma_vi_tri",
        attribute="ma_vi_tri",
        widget=SafeForeignKeyWidget(Bang_vi_tri, "ma_vi_tri"),
    )
    xuat_xu = fields.Field(
        column_name="xuat_xu",
        attribute="xuat_xu",
        widget=SafeForeignKeyWidget(Bang_xuat_xu, "ma_country"),
    )

    def before_import_row(self, row, *args, **kwargs):
        """Extract mã vị trí và xuất xứ từ mã bravo"""
        ma_bravo = row.get('ma_bravo', '').strip()

        if ma_bravo:
            # Format examples:
            # 5.46.85.020.000.D1.000 (no country) -> position: D1 (index 5)
            # 5.46.85.021.SWE.D1.000 (with country) -> position: D1 (index 5), country: SWE (index 4)
            bravo_parts = ma_bravo.split('.')

            if len(bravo_parts) >= 6:
                # Position code is always the 5th part (index 5)
                position_code = bravo_parts[5]
                print(f"🔍 Extracting position code '{position_code}' from bravo '{ma_bravo}'")

                # Check if position exists in database
                if Bang_vi_tri.objects.filter(ma_vi_tri=position_code).exists():
                    print(f"✅ Position '{position_code}' exists, using it")
                    row['ma_vi_tri'] = position_code
                else:
                    print(f"❌ Position '{position_code}' not found in database, skipping ma_vi_tri")
                    row['ma_vi_tri'] = None  # Don't create new position

                # Extract country code for xuất xứ (4th part, index 4)
                if len(bravo_parts) >= 5:
                    country_code = bravo_parts[4]
                    print(f"🔍 Extracting country code '{country_code}' from bravo '{ma_bravo}'")

                    # Check if country code exists in xuất xứ database
                    try:
                        xuat_xu = Bang_xuat_xu.objects.get(ma_country=country_code)
                        print(f"✅ Country '{country_code}' exists, mapping to xuất xứ: {xuat_xu.ten_nuoc}")
                        row['xuat_xu'] = country_code  # Map to ma_country
                    except Bang_xuat_xu.DoesNotExist:
                        print(f"❌ Country '{country_code}' not found in xuất xứ database, skipping")
                        row['xuat_xu'] = None

        return super().before_import_row(row, *args, **kwargs)
    ma_nha_may = fields.Field(
        column_name="ma_nha_may",
        attribute="bang_nha_may",
        widget=ForeignKeyWidget(Bang_nha_may, "ma_nha_may"),
    )
    ton_kho = fields.Field(column_name="ton_kho", attribute="ton_kho", widget=SafeIntegerWidget())
    so_luong_kh = fields.Field(column_name="so_luong_kh", attribute="so_luong_kh", widget=SafeIntegerWidget())

    class Meta:
        model = Bang_vat_tu
        import_id_fields = ("ma_bravo",)
        fields = (
            "ma_bravo", "ten_vat_tu", "don_vi", "thong_so_ky_thuat",
            "ton_kho", "so_luong_kh", "ma_vi_tri", "ma_nha_may", "xuat_xu",
        )
        export_order = fields
        skip_unchanged = True
        report_skipped = True
        use_bulk = False  # để gọi save() -> sinh QR

    def after_save_instance(self, instance, *args, **kwargs):
        if _is_dry_run(args, kwargs):
            return

        # Luôn tạo QR code cho vật tư mới import
        print(f"🔍 Creating QR for {instance.ma_bravo}...")
        try:
            instance.ensure_qr_image(force=True)
            instance.save(update_fields=['ma_QR'])
            print(f"✅ QR created successfully for {instance.ma_bravo}")
        except Exception as e:
            print(f"❌ Error creating QR for {instance.ma_bravo}: {e}")
            # Không raise exception để không làm crash import

# -------- PHIẾU KIỂM KÊ --------
class BangKiemKeResource(AlwaysCreateResource):
    vat_tu = fields.Field(
        column_name="ma_bravo",
        attribute="vat_tu",
        widget=VatTuByBravoAndPlantWidget(Bang_vat_tu, "ma_bravo"),
    )
    so_luong = fields.Field(column_name="so_luong", attribute="so_luong", widget=SafeIntegerWidget())
    so_luong_thuc_te = fields.Field(column_name="so_luong_thuc_te", attribute="so_luong_thuc_te", widget=SafeIntegerWidget())

    class Meta(AlwaysCreateResource.Meta):
        model = Bang_kiem_ke
        fields = ("so_thu_tu", "vat_tu", "ten_vat_tu", "don_vi", "so_luong", "so_luong_thuc_te")
        export_order = fields

# -------- ĐỀ NGHỊ NHẬP (+kho, -KH) --------
class BangDeNghiNhapResource(AlwaysCreateResource):
    _auto_stt = 0

    vat_tu = fields.Field(
        column_name="ma_bravo",
        attribute="vat_tu",
        widget=VatTuByBravoAndPlantWidget(Bang_vat_tu, "ma_bravo"),
    )
    ten_vat_tu = fields.Field(column_name="ten_vat_tu", attribute="ten_vat_tu")
    don_vi     = fields.Field(column_name="don_vi", attribute="don_vi")
    so_luong   = fields.Field(column_name="so_luong", attribute="so_luong")
    don_gia    = fields.Field(column_name="don_gia", attribute="don_gia")
    thanh_tien = fields.Field(column_name="thanh_tien", attribute="thanh_tien")
    so_de_nghi_cap = fields.Field(column_name="so_de_nghi_cap", attribute="so_de_nghi_cap")
    ngay_de_nghi = fields.Field(
        column_name="ngay_de_nghi",
        attribute="ngay_de_nghi",
        widget=DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
    )
    bo_phan    = fields.Field(column_name="bo_phan", attribute="bo_phan")
    ghi_chu    = fields.Field(column_name="ghi_chu", attribute="ghi_chu")

    class Meta(AlwaysCreateResource.Meta):
        model = Bang_de_nghi_nhap
        fields = ("stt", "vat_tu", "ten_vat_tu", "don_vi", "so_luong", "don_gia", "thanh_tien", "so_de_nghi_cap", "ngay_de_nghi", "bo_phan", "ghi_chu")
        export_order = fields

    def before_import(self, dataset, *args, **kwargs):
        self._auto_stt = 0
        dataset.headers = [_normalize_header(h) for h in dataset.headers]
        return super().before_import(dataset, *args, **kwargs)

    def before_import_row(self, row, *args, **kwargs):
        if not row.get("stt"):
            self._auto_stt += 1
            row["stt"] = self._auto_stt

        # bắt buộc có nhà máy
        if not (row.get("ma_nha_may") or row.get("ten_nha_may")):
            raise ValidationError("Thiếu cột 'ma_nha_may' hoặc 'ten_nha_may'.")

        # ép số lượng dương
        try:
            sl = int(row.get("so_luong"))
        except Exception:
            sl = 0
        if sl <= 0:
            raise ValidationError("so_luong phải > 0.")
        row["so_luong"] = sl

        # tự điền ngày/đơn vị/tên nếu thiếu (để xem trước)
        code = (row.get("ma_bravo") or "").strip()
        if not code:
            raise ValidationError("Thiếu ma_bravo.")
        qs = Bang_vat_tu.objects.filter(ma_bravo=code)
        if row.get("ma_nha_may"):
            qs = qs.filter(bang_nha_may__ma_nha_may=row["ma_nha_may"].strip())
        elif row.get("ten_nha_may"):
            qs = qs.filter(bang_nha_may__ten_nha_may__iexact=row["ten_nha_may"].strip())
        vt = qs.first()
        if not vt:
            raise ValidationError(f"Không tìm thấy vật tư ma_bravo='{code}' cho nhà máy đã chỉ định.")

        if not row.get("don_vi"):      row["don_vi"] = vt.don_vi
        if not row.get("ten_vat_tu"):  row["ten_vat_tu"] = vt.ten_vat_tu
        if not row.get("ngay_de_nghi"):
            row["ngay_de_nghi"] = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        if not row.get("don_gia"):     row["don_gia"] = 0
        if not row.get("thanh_tien"):  row["thanh_tien"] = 0
        if not row.get("so_de_nghi_cap"): row["so_de_nghi_cap"] = ""
        if not row.get("bo_phan"):     row["bo_phan"] = ""
        if not row.get("ghi_chu"):     row["ghi_chu"] = ""

        return super().before_import_row(row, *args, **kwargs)

    def before_save_instance(self, instance, *args, **kwargs):
        if getattr(instance, "vat_tu", None):
            instance.ten_vat_tu = instance.ten_vat_tu or instance.vat_tu.ten_vat_tu
            instance.don_vi     = instance.don_vi or instance.vat_tu.don_vi
            instance.ma_bravo_text = instance.vat_tu.ma_bravo
        if not getattr(instance, "ngay_de_nghi", None):
            instance.ngay_de_nghi = timezone.now()

    def after_save_instance(self, instance, *args, **kwargs):
        # nếu là preview (dry_run) thì bỏ qua
        dry_run = kwargs.get("dry_run", bool(len(args) >= 2 and args[1]))
        if dry_run:
            return
        with transaction.atomic():
            updated = Bang_vat_tu.objects.filter(pk=instance.vat_tu_id).update(
                ton_kho=F("ton_kho") + int(instance.so_luong),
                so_luong_kh=Greatest(F("so_luong_kh") - int(instance.so_luong), 0),
            )
            if updated == 0:
                raise ValidationError("Không cập nhật được tồn kho (không tìm thấy vật tư?).")

# -------- ĐỀ NGHỊ XUẤT (-kho, chặn âm) --------
class BangDeNghiXuatResource(AlwaysCreateResource):
    _auto_stt = 0

    vat_tu = fields.Field(
        column_name="ma_bravo",
        attribute="vat_tu",
        widget=VatTuByBravoAndPlantWidget(Bang_vat_tu, "ma_bravo"),
    )
    ten_vat_tu = fields.Field(column_name="ten_vat_tu", attribute="ten_vat_tu")
    don_vi     = fields.Field(column_name="don_vi", attribute="don_vi")
    so_luong   = fields.Field(column_name="so_luong", attribute="so_luong")
    ngay_de_nghi_xuat = fields.Field(
        column_name="ngay_de_nghi_xuat",
        attribute="ngay_de_nghi_xuat",
        widget=DateTimeWidget(format="%Y-%m-%d %H:%M:%S"),
    )
    ghi_chu = fields.Field(column_name="ghi_chu", attribute="ghi_chu")

    class Meta(AlwaysCreateResource.Meta):
        model = Bang_de_nghi_xuat
        fields = ("stt","vat_tu","ten_vat_tu","don_vi","so_luong","ngay_de_nghi_xuat","ghi_chu")
        export_order = fields

    def before_import(self, dataset, *args, **kwargs):
        self._auto_stt = 0
        dataset.headers = [_normalize_header(h) for h in dataset.headers]
        return super().before_import(dataset, *args, **kwargs)

    def before_import_row(self, row, *args, **kwargs):
        if not row.get("stt"):
            self._auto_stt += 1
            row["stt"] = self._auto_stt

        if not (row.get("ma_nha_may") or row.get("ten_nha_may")):
            raise ValidationError("Thiếu cột 'ma_nha_may' hoặc 'ten_nha_may'.")

        try:
            sl = int(row.get("so_luong"))
        except Exception:
            sl = 0
        if sl <= 0:
            raise ValidationError("so_luong phải > 0.")
        row["so_luong"] = sl

        code = (row.get("ma_bravo") or "").strip()
        if not code:
            raise ValidationError("Thiếu ma_bravo.")

        qs = Bang_vat_tu.objects.filter(ma_bravo=code)
        if row.get("ma_nha_may"):
            qs = qs.filter(bang_nha_may__ma_nha_may=row["ma_nha_may"].strip())
        elif row.get("ten_nha_may"):
            qs = qs.filter(bang_nha_may__ten_nha_may__iexact=row["ten_nha_may"].strip())
        vt = qs.first()
        if not vt:
            raise ValidationError(f"Không tìm thấy vật tư ma_bravo='{code}' cho nhà máy đã chỉ định.")

        # chặn ngay ở preview nếu vượt tồn
        if vt.ton_kho < sl:
            plant = vt.bang_nha_may.ma_nha_may if vt.bang_nha_may else "?"
            raise ValidationError(
                f"Không đủ tồn kho để xuất. Nhà máy: {plant}, Mã BRAVO: {vt.ma_bravo}, "
                f"Tồn hiện tại: {vt.ton_kho}, Số lượng yêu cầu: {sl}."
            )

        if not row.get("don_vi"):     row["don_vi"] = vt.don_vi
        if not row.get("ten_vat_tu"): row["ten_vat_tu"] = vt.ten_vat_tu
        if not row.get("ngay_de_nghi_xuat"):
            row["ngay_de_nghi_xuat"] = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        if not row.get("ghi_chu"):    row["ghi_chu"] = ""

        return super().before_import_row(row, *args, **kwargs)

    def before_save_instance(self, instance, *args, **kwargs):
        if getattr(instance, "vat_tu", None):
            instance.ten_vat_tu = instance.ten_vat_tu or instance.vat_tu.ten_vat_tu
            instance.don_vi     = instance.don_vi or instance.vat_tu.don_vi
            instance.ma_bravo_text = instance.vat_tu.ma_bravo
        if not getattr(instance, "ngay_de_nghi_xuat", None):
            instance.ngay_de_nghi_xuat = timezone.now()

    def after_save_instance(self, instance, *args, **kwargs):
        dry_run = kwargs.get("dry_run", bool(len(args) >= 2 and args[1]))
        if dry_run:
            return
        with transaction.atomic():
            updated = Bang_vat_tu.objects.filter(
                pk=instance.vat_tu_id,
                ton_kho__gte=int(instance.so_luong)
            ).update(ton_kho=F("ton_kho") - int(instance.so_luong))

            if updated == 0:
                # quay lại báo lỗi rõ ràng (trong trường hợp tồn thay đổi sau preview)
                vt = Bang_vat_tu.objects.select_related("bang_nha_may")\
                    .only("ton_kho", "ma_bravo", "bang_nha_may__ma_nha_may")\
                    .filter(pk=instance.vat_tu_id).first()
                current = vt.ton_kho if vt else "?"
                bravo   = instance.ma_bravo_text or (vt.ma_bravo if vt else "?")
                plant   = (vt.bang_nha_may.ma_nha_may if (vt and vt.bang_nha_may) else "?")
                raise ValidationError(
                    f"Không đủ tồn kho để xuất (sau khi xác nhận). Nhà máy: {plant}, "
                    f"Mã BRAVO: {bravo}, Tồn hiện tại: {current}, "
                    f"Số lượng yêu cầu: {int(instance.so_luong)}."
                )

# -------- Vị trí & Nhà máy (không đổi) --------
class BangViTriResource(resources.ModelResource):
    class Meta:
        model = Bang_vi_tri
        import_id_fields = ("ma_vi_tri",)
        fields = ("ma_vi_tri", "ma_he_thong", "kho", "ke", "ngan", "tang", "mo_ta")
        export_order = fields

class BangNhaMayResource(resources.ModelResource):
    class Meta:
        model = Bang_nha_may
        import_id_fields = ("ma_nha_may",)
        fields = ("ma_nha_may", "ten_nha_may")
        export_order = fields

class BangXuatXuResource(resources.ModelResource):
    class Meta:
        model = Bang_xuat_xu
        import_id_fields = ("ma_country",)
        fields = ("ma_country", "ten_nuoc", "ten_viet_tat", "mo_ta")
        export_order = fields

# ===================== ADMINS =====================

class XLSXOnlyMixin:
    """Chỉ cho phép XLSX; dùng class (base_formats.XLSX), không phải instance."""
    formats = (base_formats.XLSX,)

    def get_import_formats(self):
        return list(self.formats)

    def get_export_formats(self):
        return list(self.formats)

@admin.register(Bang_vat_tu)
class BangVatTuAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = BangVatTuResource
    list_display = ("ma_bravo", "ten_vat_tu", "don_vi", "ton_kho", "so_luong_kh", "ma_vi_tri", "bang_nha_may", "qr_preview")
    search_fields = ("ma_bravo", "ten_vat_tu")
    # list_filter = ("bang_nha_may", "ma_vi_tri")
    readonly_fields = ("ma_QR", "qr_preview")
    list_per_page = 500  # Hiển thị 200 vật tư mỗi trang

    def qr_preview(self, obj):
        if obj.ma_QR:
            return format_html('<img src="{}" height="80" />', obj.ma_QR.url)
        return "—"
    qr_preview.short_description = "QR"

    @admin.action(description="Sinh lại mã QR cho vật tư đã chọn")
    def regenerate_qr(self, request, queryset):
        for obj in queryset:
            obj.ensure_qr_image(force=True)
            obj.save()
        self.message_user(request, f"Đã sinh lại QR cho {queryset.count()} vật tư.")

    @admin.action(description="Tải ZIP mã QR")
    def export_qr_zip(self, request, queryset):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for obj in queryset:
                if not obj.ma_QR:
                    obj.ensure_qr_image(force=True)
                    obj.save()
                if obj.ma_QR and obj.ma_QR.path:
                    zf.write(obj.ma_QR.path, arcname=f"{obj.ma_bravo}.png")
        buf.seek(0)
        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="qr_vat_tu.zip"'
        return resp

    actions = ["regenerate_qr", "export_qr_zip"]

@admin.register(Bang_kiem_ke)
class BangKiemKeAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = BangKiemKeResource
    list_display = ("so_thu_tu", "vat_tu", "ten_vat_tu", "so_luong", "so_luong_thuc_te")
    search_fields = ("vat_tu__ma_bravo", "ten_vat_tu")
    list_filter = ("vat_tu__bang_nha_may",)
    list_per_page = 200  # Hiển thị 200 kiểm kê mỗi trang

@admin.register(Bang_de_nghi_nhap)
class BangDeNghiNhapAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = BangDeNghiNhapResource
    list_select_related = ("vat_tu__bang_nha_may",)
    list_display = ("stt", "vat_tu", "don_vi", "so_luong", "don_gia", "thanh_tien", "bo_phan", "ngay_de_nghi", "nha_may")
    search_fields = ("vat_tu__ma_bravo", "ten_vat_tu")
    list_filter = ("vat_tu__bang_nha_may",)
    list_per_page = 200  # Hiển thị 200 đề nghị nhập mỗi trang

    def nha_may(self, obj):
        nm = getattr(obj.vat_tu.bang_nha_may, "ma_nha_may", None) if obj.vat_tu else None
        return nm or "—"
    nha_may.short_description = "Nhà máy"

@admin.register(Bang_de_nghi_xuat)
class BangDeNghiXuatAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = BangDeNghiXuatResource
    list_select_related = ("vat_tu__bang_nha_may",)
    list_display = ("stt", "vat_tu", "don_vi", "so_luong", "ngay_de_nghi_xuat", "ghi_chu", "nha_may")
    search_fields = ("vat_tu__ma_bravo", "ten_vat_tu")
    # list_filter = ("vat_tu__bang_nha_may",)
    list_per_page = 200  # Hiển thị 200 đề nghị xuất mỗi trang

    def nha_may(self, obj):
        nm = getattr(obj.vat_tu.bang_nha_may, "ma_nha_may", None) if obj.vat_tu else None
        return nm or "—"
    nha_may.short_description = "Nhà máy"

@admin.register(Bang_vi_tri)
class BangViTriAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = BangViTriResource
    list_display = ("ma_vi_tri", "ma_he_thong", "kho", "ke", "ngan", "tang")
    search_fields = ("ma_vi_tri", "ma_he_thong", "kho", "ke", "ngan", "tang")
    list_per_page = 200  # Hiển thị 200 vị trí mỗi trang

@admin.register(Bang_nha_may)
class BangNhaMayAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = BangNhaMayResource
    list_display = ("ma_nha_may", "ten_nha_may")
    search_fields = ("ma_nha_may", "ten_nha_may")
    list_per_page = 200  # Hiển thị 200 nhà máy mỗi trang

@admin.register(Bang_xuat_xu)
class BangXuatXuAdmin(XLSXOnlyMixin, ImportExportModelAdmin):
    resource_class = BangXuatXuResource
    list_display = ("ma_country", "ten_nuoc", "ten_viet_tat")
    search_fields = ("ma_country", "ten_nuoc", "ten_viet_tat")
    list_per_page = 200  # Hiển thị 200 xuất xứ mỗi trang

    @admin.action(description="Cập nhật xuất xứ cho vật tư có mã này")
    def update_vattu_xuat_xu(self, request, queryset):
        """Cập nhật xuất xứ cho tất cả vật tư có country code được chọn"""
        from django.contrib import messages

        updated_count = 0

        for xuat_xu in queryset:
            country_code = xuat_xu.ma_country

            # Tìm tất cả vật tư có country code này nhưng chưa có xuất xứ
            vattu_list = Bang_vat_tu.objects.filter(
                ma_bravo__contains=f'.{country_code}.',
                xuat_xu__isnull=True
            )

            count = vattu_list.count()
            if count > 0:
                updated = vattu_list.update(xuat_xu=xuat_xu)
                updated_count += updated
                self.message_user(
                    request,
                    f"✅ Đã cập nhật {updated} vật tư với xuất xứ {xuat_xu.ten_nuoc}",
                    level=messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    f"ℹ️  Không có vật tư nào cần cập nhật cho {country_code}",
                    level=messages.INFO
                )

        if updated_count > 0:
            self.message_user(
                request,
                f"🎉 Tổng cộng đã cập nhật {updated_count} vật tư",
                level=messages.SUCCESS
            )

    actions = [update_vattu_xuat_xu]


# ===================== CUSTOM USER ADMIN =====================

class SimpleUserAdmin(BaseUserAdmin):
    """Custom UserAdmin with simple password validation"""
    form = SimpleUserChangeForm
    add_form = SimpleUserCreationForm

    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Thông tin cá nhân', {'fields': ('first_name', 'last_name', 'email')}),
        ('Quyền hạn', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Thời gian', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )

    def save_model(self, request, obj, form, change):
        """Override save to handle simple password validation"""
        if not change:  # Creating new user
            obj.set_password(form.cleaned_data['password1'])
        elif form.cleaned_data.get('password'):  # Changing password
            obj.set_password(form.cleaned_data['password'])
        super().save_model(request, obj, form, change)


# Register custom User admin (don't unregister as we use custom User model)
# admin.site.unregister(User)  # Commented out as we use custom User model
# admin.site.register(User, SimpleUserAdmin)  # Commented out as we use custom User model


# UserProfile is already registered in core.admin
# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'full_name', 'chuc_danh', 'phone', 'nha_may', 'is_mobile_user', 'created_at')
#     list_filter = ('is_mobile_user', 'nha_may', 'chuc_danh', 'created_at')
#     search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'phone', 'chuc_danh')
#     ordering = ('-created_at',)
#     fieldsets = (
#         ('Thông tin User', {'fields': ('user',)}),
#         ('Thông tin bổ sung', {'fields': ('phone', 'nha_may', 'chuc_danh')}),
#         ('Hình ảnh', {'fields': ('avatar', 'chu_ky')}),
#         ('Quyền hạn', {'fields': ('is_mobile_user',)}),
#         ('Thời gian', {'fields': ('created_at', 'updated_at')}),
#     )
#     readonly_fields = ('created_at', 'updated_at')
#
#     def full_name(self, obj):
#         return obj.full_name
#     full_name.short_description = 'Tên đầy đủ'



