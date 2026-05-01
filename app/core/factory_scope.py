from django.db.models import Q
from rest_framework.exceptions import PermissionDenied, ValidationError


def get_user_profile(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "profile", None)


def has_all_factory_access(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    profile = get_user_profile(user)
    return bool(profile and profile.is_all_factories)


def get_user_factory(user):
    profile = get_user_profile(user)
    if not profile:
        return None
    return profile.nha_may


def get_user_factory_code(user):
    factory = get_user_factory(user)
    return factory.ma_nha_may if factory else None


def get_user_factory_name(user):
    factory = get_user_factory(user)
    return factory.ten_nha_may if factory else None


def require_user_factory(user):
    if has_all_factory_access(user):
        return None

    factory = get_user_factory(user)
    if not factory:
        raise PermissionDenied("User chưa được gán nhà máy.")
    return factory


def _target_factory_code(value):
    if not value:
        return None
    return getattr(value, "ma_nha_may", value)


def ensure_factory_code_allowed(user, factory_code):
    if has_all_factory_access(user):
        return

    factory = require_user_factory(user)
    if not factory_code or str(factory.ma_nha_may).lower() != str(factory_code).lower():
        raise PermissionDenied("Bạn không có quyền truy cập nhà máy này.")


def ensure_factory_allowed(user, factory):
    code = _target_factory_code(factory)
    ensure_factory_code_allowed(user, code)


def _factory_string_query(field_name, factory):
    code = factory.ma_nha_may
    name = factory.ten_nha_may
    query = Q(**{f"{field_name}__iexact": code})

    if name:
        query |= Q(**{f"{field_name}__iexact": name})
        query |= Q(**{f"{field_name}__icontains": name})

    return query


def _model_field_path_exists(model, field_path):
    parts = field_path.split("__")
    current_model = model

    for index, part in enumerate(parts):
        try:
            field = current_model._meta.get_field(part)
        except Exception:
            return False

        if index == len(parts) - 1:
            return True

        current_model = getattr(field, "related_model", None)
        if current_model is None:
            return False

    return False


def _factory_string_query_for_queryset(qs, field_name, factory):
    query = _factory_string_query(field_name, factory)
    prefix_lookup = None

    relation_parts = field_name.split("__")[:-1]
    if relation_parts:
        candidate = "__".join(relation_parts + ["ma_day_du"])
        if _model_field_path_exists(qs.model, candidate):
            prefix_lookup = candidate
    elif _model_field_path_exists(qs.model, "ma_day_du"):
        prefix_lookup = "ma_day_du"
    elif _model_field_path_exists(qs.model, "thiet_bi__ma_day_du"):
        prefix_lookup = "thiet_bi__ma_day_du"

    if prefix_lookup and factory.ma_nha_may:
        query |= Q(**{f"{prefix_lookup}__istartswith": f"{factory.ma_nha_may}."})

    return query


def filter_queryset_by_factory(qs, user, field_name, field_kind="fk"):
    if has_all_factory_access(user):
        return qs

    factory = require_user_factory(user)

    if field_kind == "fk":
        return qs.filter(**{field_name: factory})
    if field_kind == "fk_code":
        return qs.filter(**{f"{field_name}__ma_nha_may__iexact": factory.ma_nha_may})
    if field_kind == "code":
        return qs.filter(**{f"{field_name}__iexact": factory.ma_nha_may})
    if field_kind == "string":
        return qs.filter(_factory_string_query_for_queryset(qs, field_name, factory))

    raise ValueError(f"Unsupported factory field kind: {field_kind}")


def apply_request_factory_to_serializer(user, serializer, field_name, field_kind="fk"):
    if has_all_factory_access(user):
        target = serializer.validated_data.get(field_name)
        if target is not None:
            if field_kind in ["fk", "fk_code"]:
                ensure_factory_allowed(user, target)
            elif field_kind in ["code", "string"]:
                ensure_factory_code_allowed(user, target)
        return {}

    factory = require_user_factory(user)

    if field_kind in ["fk", "fk_code"]:
        return {field_name: factory}
    if field_kind == "code":
        return {field_name: factory.ma_nha_may}
    if field_kind == "string":
        return {field_name: factory.ten_nha_may or factory.ma_nha_may}

    raise ValidationError({field_name: "Kiểu field nhà máy không hợp lệ."})


class FactoryScopedViewSetMixin:
    factory_field = "nha_may"
    factory_field_kind = "fk"

    def get_queryset(self):
        qs = super().get_queryset()
        return filter_queryset_by_factory(
            qs,
            self.request.user,
            self.factory_field,
            self.factory_field_kind,
        )

    def perform_create(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(
                self.request.user,
                serializer,
                self.factory_field,
                self.factory_field_kind,
            )
        )

    def perform_update(self, serializer):
        serializer.save(
            **apply_request_factory_to_serializer(
                self.request.user,
                serializer,
                self.factory_field,
                self.factory_field_kind,
            )
        )
