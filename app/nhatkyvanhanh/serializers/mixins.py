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
