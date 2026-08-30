import unicodedata
from rest_framework import serializers

LEADERSHIP_TITLES = {
    "giam doc",
    "gd",
    "pho giam doc",
    "pho gd",
    "pgd",
    "pho tong giam doc",
    "pho tong gd",
    "ptgd",
    "tong giam doc",
    "tgd",
    "quan doc",
    "qd",
    "pho quan doc",
    "pho qd",
    "pqd",
}

def _normalize_title(value):
    normalized = unicodedata.normalize("NFD", str(value or "").replace("đ", "d").replace("Đ", "D"))
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_marks.casefold().split())

def user_can_edit_chi_dao(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_edit_leadership_directives)


class UserSummaryMixin:
    def _build_file_url(self, file_field):
        if not file_field:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(file_field.url)
        return file_field.url

    def _get_user_display(self, user):
        if not user:
            return None
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name or user.username or user.email

    def _get_user_signature_url(self, user):
        if not user:
            return None
        profile = getattr(user, "profile", None)
        if profile and getattr(profile, "chu_ky", None):
            return self._build_file_url(profile.chu_ky)
        return None


class FlexibleNhaMayRelatedField(serializers.PrimaryKeyRelatedField):
    """
    Cho phép nhận cả ID (int/int string) hoặc mã nhà máy (str: 'SH', 'VS', 'TKT', 'song_hinh', 'vinh_son')
    giúp API linh hoạt tuyệt đối và không bị lỗi 'Incorrect type. Expected pk value, received str.'
    """
    def to_internal_value(self, data):
        if data is None or data == "":
            return None

        # Nếu là int hoặc chuỗi toàn chữ số
        if isinstance(data, int) or (isinstance(data, str) and data.strip().isdigit()):
            return super().to_internal_value(int(str(data).strip()))

        # Nếu là chuỗi ký tự (mã nhà máy hoặc tên)
        if isinstance(data, str):
            from tochuc.models import NhaMay
            code = data.strip()
            compact = code.replace(" ", "").replace("_", "").replace("-", "").upper()

            if compact in ["SH", "SONGHINH"]:
                nm = NhaMay.objects.filter(ma_nha_may__iexact="SH").first()
            elif compact in ["VS", "VINHSON"]:
                nm = NhaMay.objects.filter(ma_nha_may__iexact="VS").first()
            elif compact in ["TKT", "THUONGKONTUM"]:
                nm = NhaMay.objects.filter(ma_nha_may__iexact="TKT").first()
            else:
                nm = NhaMay.objects.filter(ma_nha_may__iexact=code).first()
                if not nm:
                    nm = NhaMay.objects.filter(ten_nha_may__icontains=code).first()

            if nm:
                return nm

        return super().to_internal_value(data)
