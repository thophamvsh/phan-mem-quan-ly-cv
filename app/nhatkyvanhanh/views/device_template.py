from copy import deepcopy

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from nhatkyvanhanh.models import MauTrangThaiThietBiCa
from nhatkyvanhanh.serializers import MauTrangThaiThietBiCaSerializer


class MauTrangThaiThietBiCaPermission(permissions.DjangoModelPermissions):
    perms_map = {
        **permissions.DjangoModelPermissions.perms_map,
        "GET": ["nhatkyvanhanh.view_mautrangthaithietbica"],
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        profile = getattr(request.user, "profile", None)
        if profile and profile.can_manage_all_shift_handover_logs:
            return True
        profile_permission_by_action = {
            "list": "can_view_shift_device_templates",
            "retrieve": "can_view_shift_device_templates",
            "dang_ap_dung": "can_view_shift_device_templates",
            "create": "can_create_shift_device_templates",
            "update": "can_edit_shift_device_templates",
            "partial_update": "can_edit_shift_device_templates",
            "destroy": "can_delete_shift_device_templates",
            "kich_hoat": "can_activate_shift_device_templates",
            "tao_phien_ban": "can_create_shift_device_templates",
        }
        profile_permission = profile_permission_by_action.get(view.action)
        if profile and profile_permission and getattr(profile, profile_permission, False):
            return True
        if view.action == "kich_hoat":
            return request.user.has_perm("nhatkyvanhanh.activate_mautrangthaithietbica")
        if view.action == "tao_phien_ban":
            return request.user.has_perm("nhatkyvanhanh.add_mautrangthaithietbica")
        return super().has_permission(request, view)


class MauTrangThaiThietBiCaViewSet(viewsets.ModelViewSet):
    serializer_class = MauTrangThaiThietBiCaSerializer
    permission_classes = [MauTrangThaiThietBiCaPermission]
    queryset = MauTrangThaiThietBiCa.objects.select_related("nha_may", "nguoi_tao").prefetch_related("nhom_thiet_bi__thiet_bi__thiet_bi")

    def get_queryset(self):
        queryset = filter_queryset_by_factory(super().get_queryset(), self.request.user, "nha_may", "fk")
        plant_id = self.request.query_params.get("nha_may")
        if plant_id:
            queryset = queryset.filter(nha_may_id=plant_id)
        return queryset

    def perform_create(self, serializer):
        values = apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        serializer.save(nguoi_tao=self.request.user, **values)

    def perform_destroy(self, instance):
        if instance.da_duoc_su_dung:
            raise ValidationError("Không thể xóa mẫu đã được sổ giao nhận ca sử dụng.")
        if instance.dang_ap_dung:
            raise ValidationError(
                "Không thể xóa mẫu đang áp dụng. Hãy kích hoạt mẫu thay thế trước."
            )
        instance.delete()

    @action(detail=False, methods=["get"], url_path="dang-ap-dung")
    def dang_ap_dung(self, request):
        plant_id = request.query_params.get("nha_may")
        queryset = self.get_queryset().filter(dang_ap_dung=True)
        if plant_id:
            queryset = queryset.filter(nha_may_id=plant_id)
        template = queryset.first()
        if not template:
            return Response({"detail": "Chưa có mẫu đang áp dụng."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(template).data)

    @action(detail=True, methods=["post"], url_path="tao-phien-ban")
    def tao_phien_ban(self, request, pk=None):
        source = self.get_object()
        payload = MauTrangThaiThietBiCaSerializer(source).data
        payload.pop("id", None)
        payload.pop("phien_ban", None)
        payload.pop("dang_ap_dung", None)
        payload.pop("nguoi_tao", None)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        payload.pop("da_duoc_su_dung", None)
        payload.pop("nha_may_code", None)
        payload["ten_mau"] = request.data.get("ten_mau") or source.ten_mau
        if request.data.get("groups") is not None:
            payload["groups"] = request.data["groups"]
        for group in payload["groups"]:
            group.pop("id", None)
            for device in group["thiet_bi"]:
                device.pop("id", None)
                device.pop("ma_thiet_bi", None)
                device.pop("ghi_chu", None)
        serializer = self.get_serializer(data=deepcopy(payload))
        serializer.is_valid(raise_exception=True)
        new_template = serializer.save(nguoi_tao=request.user)
        return Response(self.get_serializer(new_template).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="kich-hoat")
    @transaction.atomic
    def kich_hoat(self, request, pk=None):
        template = self.get_object()
        MauTrangThaiThietBiCa.objects.filter(nha_may=template.nha_may, dang_ap_dung=True).exclude(pk=template.pk).update(dang_ap_dung=False)
        template.dang_ap_dung = True
        template.save(update_fields=["dang_ap_dung", "updated_at"])
        return Response(self.get_serializer(template).data)
