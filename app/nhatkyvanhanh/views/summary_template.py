from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from nhatkyvanhanh.models import MauTomLuocGiaoCaVH
from nhatkyvanhanh.serializers import MauTomLuocGiaoCaVHSerializer


class MauTomLuocGiaoCaVHPermission(permissions.DjangoModelPermissions):
    perms_map = {
        **permissions.DjangoModelPermissions.perms_map,
        "GET": ["nhatkyvanhanh.view_mautomluocgiaocavh"],
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        profile = getattr(request.user, "profile", None)
        if profile and profile.can_manage_all_shift_handover_logs:
            return True
        fields = {
            "list": "can_view_shift_summary_templates",
            "retrieve": "can_view_shift_summary_templates",
            "dang_ap_dung": "can_view_shift_summary_templates",
            "create": "can_create_shift_summary_templates",
            "update": "can_edit_shift_summary_templates",
            "partial_update": "can_edit_shift_summary_templates",
            "destroy": "can_delete_shift_summary_templates",
            "kich_hoat": "can_activate_shift_summary_templates",
            "tao_phien_ban": "can_create_shift_summary_templates",
        }
        field = fields.get(view.action)
        if profile and field and getattr(profile, field, False):
            return True
        if view.action == "kich_hoat":
            return request.user.has_perm("nhatkyvanhanh.activate_mautomluocgiaocavh")
        if view.action == "tao_phien_ban":
            return request.user.has_perm("nhatkyvanhanh.add_mautomluocgiaocavh")
        return super().has_permission(request, view)


class MauTomLuocGiaoCaVHViewSet(viewsets.ModelViewSet):
    serializer_class = MauTomLuocGiaoCaVHSerializer
    permission_classes = [MauTomLuocGiaoCaVHPermission]
    queryset = MauTomLuocGiaoCaVH.objects.select_related("nha_may", "nguoi_tao").prefetch_related("hang_muc")

    def get_queryset(self):
        queryset = filter_queryset_by_factory(super().get_queryset(), self.request.user, "nha_may", "fk")
        plant_id = self.request.query_params.get("nha_may")
        return queryset.filter(nha_may_id=plant_id) if plant_id else queryset

    def perform_create(self, serializer):
        values = apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        serializer.save(nguoi_tao=self.request.user, **values)

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.da_duoc_su_dung:
            raise ValidationError("Không thể xóa mẫu đã được sổ giao nhận ca sử dụng.")
        was_active = instance.dang_ap_dung
        plant = instance.nha_may
        pk = instance.pk
        instance.delete()
        if was_active:
            other_template = (
                MauTomLuocGiaoCaVH.objects.filter(nha_may=plant)
                .exclude(pk=pk)
                .order_by("-phien_ban")
                .first()
            )
            if other_template:
                other_template.dang_ap_dung = True
                other_template.save(update_fields=["dang_ap_dung", "updated_at"])

    @action(detail=False, methods=["get"], url_path="dang-ap-dung")
    def dang_ap_dung(self, request):
        queryset = self.get_queryset().filter(dang_ap_dung=True)
        template = queryset.first()
        if not template:
            return Response({"detail": "Chưa có mẫu tóm lược đang áp dụng."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(template).data)

    @action(detail=True, methods=["post"], url_path="tao-phien-ban")
    def tao_phien_ban(self, request, pk=None):
        source = self.get_object()
        payload = self.get_serializer(source).data
        for key in ["id", "phien_ban", "dang_ap_dung", "nguoi_tao", "created_at", "updated_at", "da_duoc_su_dung", "nha_may_code"]:
            payload.pop(key, None)
        payload["ten_mau"] = request.data.get("ten_mau") or source.ten_mau
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save(nguoi_tao=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="kich-hoat")
    @transaction.atomic
    def kich_hoat(self, request, pk=None):
        template = self.get_object()
        MauTomLuocGiaoCaVH.objects.filter(nha_may=template.nha_may, dang_ap_dung=True).exclude(pk=template.pk).update(dang_ap_dung=False)
        template.dang_ap_dung = True
        template.save(update_fields=["dang_ap_dung", "updated_at"])
        return Response(self.get_serializer(template).data)
