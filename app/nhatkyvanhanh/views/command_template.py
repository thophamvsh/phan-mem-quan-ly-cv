from django.db import models, transaction
from django.db.models import Max, Q
from django.utils.dateparse import parse_datetime
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from nhatkyvanhanh.models.command_template import MauNoiDungVanHanh
from nhatkyvanhanh.serializers.command_template import MauNoiDungVanHanhSerializer


class MauNoiDungVanHanhPermission(permissions.DjangoModelPermissions):
    perms_map = {
        **permissions.DjangoModelPermissions.perms_map,
        "GET": ["nhatkyvanhanh.view_maunoidungvanhanh"],
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_superuser:
            return True
        profile = getattr(request.user, "profile", None)
        if profile and profile.can_manage_all_shift_handover_logs:
            return True

        action_permissions = {
            "list": "can_view_shift_command_templates",
            "retrieve": "can_view_shift_command_templates",
            "dang_ap_dung": "can_view_shift_command_templates",
            "create": "can_create_shift_command_templates",
            "update": "can_edit_shift_command_templates",
            "partial_update": "can_edit_shift_command_templates",
            "destroy": "can_delete_shift_command_templates",
            "kich_hoat": "can_activate_shift_command_templates",
            "toggle_active": "can_activate_shift_command_templates",
            "tao_phien_ban": "can_create_shift_command_templates",
            "khoi_phuc_mac_dinh": "can_create_shift_command_templates",
        }
        field = action_permissions.get(view.action)
        if profile and field and getattr(profile, field, False):
            return True

        if view.action in ("kich_hoat", "toggle_active"):
            return request.user.has_perm("nhatkyvanhanh.activate_maunoidungvanhanh")
        if view.action == "tao_phien_ban":
            return request.user.has_perm("nhatkyvanhanh.add_maunoidungvanhanh")

        return super().has_permission(request, view)

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        # Bảo vệ mẫu chung toàn hệ thống (nha_may=None): Chỉ superuser mới được sửa hoặc xóa
        if obj.nha_may is None:
            if request.method not in permissions.SAFE_METHODS and view.action not in ("list", "retrieve", "dang_ap_dung"):
                raise PermissionDenied("Chỉ quản trị viên hệ thống mới có quyền chỉnh sửa hoặc xóa mẫu chung toàn hệ thống.")

        # Cách ly dữ liệu nhà máy: Không cho phép thao tác chéo nhà máy
        if obj.nha_may is not None:
            profile = getattr(request.user, "profile", None)
            user_plant_id = getattr(profile, "nha_may_id", None)
            is_all_factories = getattr(profile, "is_all_factories", False)
            if not is_all_factories and user_plant_id != obj.nha_may_id:
                raise PermissionDenied("Bạn không có quyền thao tác trên mẫu của nhà máy khác.")

        return True


class MauNoiDungVanHanhViewSet(viewsets.ModelViewSet):
    serializer_class = MauNoiDungVanHanhSerializer
    permission_classes = [MauNoiDungVanHanhPermission]
    pagination_class = None  # <-- Trả về toàn bộ danh mục mẫu lệnh cho Modal
    queryset = MauNoiDungVanHanh.objects.select_related("nha_may", "nguoi_tao", "nguoi_cap_nhat")

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        # Với các action danh sách (list, dang_ap_dung), lọc theo phạm vi nhà máy
        # Các action chi tiết (retrieve, update, destroy, v.v.) không lọc bỏ trước ở queryset
        # để has_object_permission có thể kiểm tra và ném lỗi 403 Forbidden thay vì 404 Not Found.
        if getattr(self, "action", None) in ("list", "dang_ap_dung"):
            plant_id = self.request.query_params.get("nha_may")
            if plant_id:
                if str(plant_id).isdigit():
                    plant_filter = Q(nha_may_id=plant_id)
                else:
                    plant_filter = Q(nha_may__ma_nha_may__iexact=str(plant_id).strip())
                queryset = queryset.filter(plant_filter | Q(nha_may__isnull=True))
            elif not user.is_superuser and hasattr(user, "profile") and not user.profile.is_all_factories:
                user_plant_id = user.profile.nha_may_id
                if user_plant_id:
                    queryset = queryset.filter(Q(nha_may_id=user_plant_id) | Q(nha_may__isnull=True))
                else:
                    queryset = queryset.filter(nha_may__isnull=True)

        return queryset.order_by("thu_tu", "ma_mau", "-phien_ban")

    def perform_create(self, serializer):
        user = self.request.user
        plant = serializer.validated_data.get("nha_may")

        # Không phải superuser thì bắt buộc gắn với nhà máy của user (ngăn tạo mẫu hệ thống giả mạo)
        if not user.is_superuser:
            if not plant and hasattr(user, "profile") and user.profile.nha_may:
                plant = user.profile.nha_may
            elif plant and hasattr(user, "profile") and not user.profile.is_all_factories:
                if plant.pk != user.profile.nha_may_id:
                    raise PermissionDenied("Không thể tạo mẫu cho nhà máy khác.")

        # Tính toán số phiên bản kế tiếp
        ma_mau = serializer.validated_data.get("ma_mau")
        scope = {"ma_mau": ma_mau, "nha_may": plant}
        latest_version = (
            MauNoiDungVanHanh.objects.filter(**scope)
            .aggregate(max_v=Max("phien_ban"))
            .get("max_v")
            or 0
        )

        serializer.save(
            nha_may=plant,
            phien_ban=latest_version + 1,
            la_mau_he_thong=False if plant else user.is_superuser,
            nguoi_tao=user,
            nguoi_cap_nhat=user,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Kiểm soát cập nhật đồng thời (Optimistic Concurrency Control)
        client_updated_at = request.data.get("updated_at_client") or request.data.get("updated_at")
        if client_updated_at:
            client_dt = parse_datetime(str(client_updated_at).strip())
            if client_dt and abs((instance.updated_at - client_dt).total_seconds()) > 0.001:
                return Response(
                    {"detail": "Dữ liệu đã được cập nhật bởi người dùng khác. Vui lòng tải lại trang!"},
                    status=status.HTTP_409_CONFLICT,
                )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(nguoi_cap_nhat=request.user)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        if instance.la_mau_he_thong or instance.nha_may is None:
            raise ValidationError("Không thể xóa mẫu mặc định của toàn hệ thống.")
        if instance.dang_ap_dung:
            raise ValidationError("Không thể xóa phiên bản đang áp dụng. Vui lòng kích hoạt phiên bản khác trước khi xóa.")
        instance.delete()

    @action(detail=False, methods=["get"], url_path="dang-ap-dung")
    def dang_ap_dung(self, request):
        """
        Endpoint chuyên phục vụ form và thanh công cụ:
        Trả về danh sách mẫu đang áp dụng (dang_ap_dung=True).
        Áp dụng thuật toán ghi đè ưu tiên: Mẫu nhà máy (Plant) ghi đè mẫu hệ thống (Global) cùng ma_mau.
        """
        plant_id = request.query_params.get("nha_may")
        if not plant_id and hasattr(request.user, "profile") and request.user.profile.nha_may_id:
            plant_id = request.user.profile.nha_may_id

        # 1. Lấy mẫu chung toàn hệ thống đang áp dụng
        global_templates = list(
            MauNoiDungVanHanh.objects.filter(nha_may__isnull=True, dang_ap_dung=True)
            .select_related("nha_may", "nguoi_tao", "nguoi_cap_nhat")
            .order_by("thu_tu", "ma_mau")
        )

        result_map = {t.ma_mau: t for t in global_templates}

        # 2. Nếu có nhà máy, lấy mẫu của nhà máy đang áp dụng để ghi đè (Plant precedence)
        if plant_id:
            plant_qs = MauNoiDungVanHanh.objects.filter(dang_ap_dung=True).select_related("nha_may", "nguoi_tao", "nguoi_cap_nhat")
            if str(plant_id).isdigit():
                plant_qs = plant_qs.filter(nha_may_id=plant_id)
            else:
                plant_qs = plant_qs.filter(nha_may__ma_nha_may__iexact=str(plant_id).strip())
            plant_templates = list(plant_qs.order_by("thu_tu", "ma_mau"))
            for pt in plant_templates:
                result_map[pt.ma_mau] = pt

        # Sắp xếp danh sách kết quả theo thu_tu
        sorted_templates = sorted(result_map.values(), key=lambda x: (x.thu_tu, x.ma_mau))
        serializer = self.get_serializer(sorted_templates, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="tao-phien-ban")
    def tao_phien_ban(self, request, pk=None):
        """
        Tạo một bản ghi phiên bản mới nhân bản từ bản ghi hiện tại.
        Phiên bản mới có phien_ban = max(phien_ban) + 1, dang_ap_dung=False.
        """
        source = self.get_object()
        user = request.user

        # Tìm max phien_ban của ma_mau trong cùng scope
        latest_version = (
            MauNoiDungVanHanh.objects.filter(ma_mau=source.ma_mau, nha_may=source.nha_may)
            .aggregate(max_v=Max("phien_ban"))
            .get("max_v")
            or source.phien_ban
        )

        new_template = MauNoiDungVanHanh.objects.create(
            nha_may=source.nha_may,
            ma_mau=source.ma_mau,
            ten_mau=request.data.get("ten_mau") or source.ten_mau,
            nhom_mau=source.nhom_mau,
            dinh_dang_tieu_de=request.data.get("dinh_dang_tieu_de") or source.dinh_dang_tieu_de,
            dinh_dang_mau=request.data.get("dinh_dang_mau") or source.dinh_dang_mau,
            danh_sach_tham_so=request.data.get("danh_sach_tham_so") or source.danh_sach_tham_so,
            thu_tu=source.thu_tu,
            phien_ban=latest_version + 1,
            dang_ap_dung=False,
            la_mau_he_thong=False,
            ghi_chu=request.data.get("ghi_chu") or f"Tạo từ phiên bản v{source.phien_ban}",
            nguoi_tao=user,
            nguoi_cap_nhat=user,
        )

        serializer = self.get_serializer(new_template)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="kich-hoat")
    @transaction.atomic
    def kich_hoat(self, request, pk=None):
        """
        Kích hoạt áp dụng một phiên bản chỉ định.
        Tự động hạ các phiên bản khác của cùng mã mẫu trong cùng phạm vi về dang_ap_dung=False.
        """
        template = self.get_object()

        # Hạ tất cả các phiên bản khác cùng ma_mau trong cùng scope
        MauNoiDungVanHanh.objects.filter(
            nha_may=template.nha_may,
            ma_mau=template.ma_mau,
            dang_ap_dung=True,
        ).exclude(pk=template.pk).update(dang_ap_dung=False)

        template.dang_ap_dung = True
        template.nguoi_cap_nhat = request.user
        template.save(update_fields=["dang_ap_dung", "nguoi_cap_nhat", "updated_at"])

        serializer = self.get_serializer(template)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="toggle-active")
    @transaction.atomic
    def toggle_active(self, request, pk=None):
        """
        Bật/tắt trạng thái áp dụng của mẫu.
        Nếu tắt: dang_ap_dung=False.
        Nếu bật: kích hoạt phiên bản này và hạ các phiên bản khác cùng mã mẫu về False.
        """
        template = self.get_object()

        if template.dang_ap_dung:
            template.dang_ap_dung = False
        else:
            MauNoiDungVanHanh.objects.filter(
                nha_may=template.nha_may,
                ma_mau=template.ma_mau,
                dang_ap_dung=True,
            ).exclude(pk=template.pk).update(dang_ap_dung=False)
            template.dang_ap_dung = True

        template.nguoi_cap_nhat = request.user
        template.save(update_fields=["dang_ap_dung", "nguoi_cap_nhat", "updated_at"])

        serializer = self.get_serializer(template)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="khoi-phuc-mac-dinh")
    @transaction.atomic
    def khoi_phuc_mac_dinh(self, request):
        """
        Khôi phục mẫu mặc định cho nhà máy:
        Xóa toàn bộ các bản ghi tùy biến riêng của nhà máy chỉ định,
        giúp hệ thống tự động quay về sử dụng 14 mẫu chung hệ thống.
        """
        plant_id = request.query_params.get("nha_may") or request.data.get("nha_may")
        if not plant_id:
            raise ValidationError({"nha_may": "Vui lòng chỉ định nhà máy cần khôi phục mặc định."})

        # Kiểm tra quyền nhà máy
        if not request.user.is_superuser:
            profile = getattr(request.user, "profile", None)
            user_plant = getattr(profile, "nha_may", None)
            is_all = getattr(profile, "is_all_factories", False)
            if not is_all:
                if str(plant_id).isdigit():
                    if str(getattr(profile, "nha_may_id", "")) != str(plant_id):
                        raise PermissionDenied("Không có quyền khôi phục mẫu của nhà máy khác.")
                else:
                    if not user_plant or user_plant.ma_nha_may.upper() != str(plant_id).strip().upper():
                        raise PermissionDenied("Không có quyền khôi phục mẫu của nhà máy khác.")

        qs = MauNoiDungVanHanh.objects.filter(la_mau_he_thong=False)
        if str(plant_id).isdigit():
            qs = qs.filter(nha_may_id=plant_id)
        else:
            qs = qs.filter(nha_may__ma_nha_may__iexact=str(plant_id).strip())
        deleted_count, _ = qs.delete()
        return Response({
            "detail": f"Đã khôi phục thành công danh mục mẫu mặc định. Đã xóa {deleted_count} bản ghi tùy biến riêng.",
            "deleted_count": deleted_count,
        })
