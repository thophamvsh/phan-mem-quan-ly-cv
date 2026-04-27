from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Subquery
from django.utils import timezone
import django_filters
import unicodedata
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from .models import DienBienSuKien, KhacPhucSuKien, SuKien, SogiaonhancaVH
from .serializers import (
    DienBienSuKienSerializer,
    KhacPhucSuKienSerializer,
    NhatKySuKienSerializer,
    SogiaonhancaVHSerializer,
)
from .permissions import (
    CanAcknowledgeOperationEvents,
    CanConfirmOperationEvents,
    CanCreateOperationEvents,
    CanProcessOperationEvents,
    CanViewOperationEvents,
    has_profile_permission,
)

User = get_user_model()


def _gan_chu_ky_tu_profile(user, model_instance, field_name):
    profile = getattr(user, "profile", None)
    if profile and profile.chu_ky and not getattr(model_instance, field_name):
        setattr(model_instance, field_name, profile.chu_ky.name)


def _lay_chuc_danh_user(user):
    profile = getattr(user, "profile", None)
    return (getattr(profile, "chuc_danh", None) or "").strip()


def _normalize_text(value):
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_marks.casefold().split())


def _la_truong_ca(user):
    return _normalize_text(_lay_chuc_danh_user(user)) == "truong ca"


def _co_quyen_them_dien_bien(user):
    return _la_truong_ca(user) or has_profile_permission(user, "can_add_event_developments")


def _can_edit_event(user, su_kien):
    if has_profile_permission(user, "can_edit_all_operation_events"):
        return True
    return (
        has_profile_permission(user, "can_edit_own_operation_events")
        and su_kien.nguoi_tao_id == user.id
        and not su_kien.ben_ghi_nhan_su_kien_id
        and su_kien.trang_thai == SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG
    )


def _can_delete_event(user, su_kien):
    if has_profile_permission(user, "can_delete_all_operation_events"):
        return True
    return (
        has_profile_permission(user, "can_delete_own_operation_events")
        and su_kien.nguoi_tao_id == user.id
        and not su_kien.ben_ghi_nhan_su_kien_id
    )


def _can_edit_remediation(user, khac_phuc):
    if has_profile_permission(user, "can_edit_all_remediations"):
        return True
    return (
        has_profile_permission(user, "can_edit_own_remediations")
        and khac_phuc.nguoi_tao_id == user.id
    )


def _can_edit_development(user, dien_bien):
    if has_profile_permission(user, "can_edit_all_event_developments"):
        return True
    return (
        has_profile_permission(user, "can_edit_own_event_developments")
        and dien_bien.nguoi_tao_id == user.id
    )


def _dong_bo_chu_ky_so_giao_nhan(so, current_user=None):
    so.dong_bo_chu_ky_tu_user()
    if current_user:
        if so.user_giao_ca_id == current_user.id:
            _gan_chu_ky_tu_profile(current_user, so, "chu_ky_user_giao_ca")
        if so.user_nhan_ca_id == current_user.id:
            _gan_chu_ky_tu_profile(current_user, so, "chu_ky_user_nhan_ca")


def _get_or_create_latest_khac_phuc(su_kien, nguoi_tao=None):
    latest = su_kien.latest_khac_phuc
    if latest:
        return latest
    return KhacPhucSuKien.objects.create(su_kien=su_kien, nguoi_tao=nguoi_tao)


class NhatKySuKienFilterSet(django_filters.FilterSet):
    ngay_xay_ra = django_filters.DateFilter(
        field_name="thoi_gian_xay_ra",
        lookup_expr="date",
    )
    ben_ghi_nhan_su_kien = django_filters.ModelChoiceFilter(
        queryset=User.objects.all()
    )
    ben_xu_ly_su_kien_thiet_bi = django_filters.ModelChoiceFilter(
        field_name="khac_phuc_su_kiens__ben_xu_ly_su_kien_thiet_bi",
        queryset=User.objects.all(),
    )

    class Meta:
        model = SuKien
        fields = [
            "nha_may",
            "trang_thai",
            "ben_ghi_nhan_su_kien",
            "ben_xu_ly_su_kien_thiet_bi",
            "ngay_xay_ra",
        ]


class NhatKySuKienViewSet(viewsets.ModelViewSet):
    serializer_class = NhatKySuKienSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = NhatKySuKienFilterSet
    search_fields = [
        "ten_he_thong_thiet_bi",
        "hien_tuong_dien_bien",
        "phan_tich_nguyen_nhan",
        "bao_cho",
        "ben_ghi_nhan_su_kien__email",
        "ben_ghi_nhan_su_kien__username",
        "khac_phuc_su_kiens__ben_xu_ly_su_kien_thiet_bi__email",
        "khac_phuc_su_kiens__ben_xu_ly_su_kien_thiet_bi__username",
    ]
    ordering_fields = ["thoi_gian_xay_ra", "created_at", "updated_at", "latest_thoi_gian_xu_ly"]
    ordering = ["-thoi_gian_xay_ra", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewOperationEvents]
        if self.action == "create":
            permission_classes = [CanCreateOperationEvents]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [CanViewOperationEvents]
        elif self.action == "ghi_nhan_su_kien":
            permission_classes = [CanAcknowledgeOperationEvents]
        elif self.action in ["tao_khac_phuc", "cap_nhat_khac_phuc", "xu_ly_xong"]:
            permission_classes = [CanProcessOperationEvents]
        elif self.action == "xac_nhan_xu_ly":
            permission_classes = [CanConfirmOperationEvents]
        elif self.action == "tao_dien_bien":
            permission_classes = [CanViewOperationEvents]
        elif self.action == "cap_nhat_dien_bien":
            permission_classes = [CanViewOperationEvents]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        latest_khac_phuc = KhacPhucSuKien.objects.filter(
            su_kien_id=OuterRef("pk")
        ).order_by("-thoi_gian_xu_ly", "-created_at")

        queryset = (
            SuKien.objects.select_related(
                "nha_may",
                "nguoi_tao",
                "ben_ghi_nhan_su_kien",
            )
            .prefetch_related(
                "dien_bien_su_kiens",
                "dien_bien_su_kiens__nguoi_tao",
                "khac_phuc_su_kiens",
                "khac_phuc_su_kiens__nguoi_tao",
                "khac_phuc_su_kiens__ben_xu_ly_su_kien_thiet_bi",
                "khac_phuc_su_kiens__nguoi_xac_nhan_xu_ly",
            )
            .annotate(
                latest_thoi_gian_xu_ly=Subquery(latest_khac_phuc.values("thoi_gian_xu_ly")[:1])
            )
            .distinct()
        )
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        serializer.save(
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk"),
        )

    def perform_update(self, serializer):
        if not _can_edit_event(self.request.user, serializer.instance):
            raise PermissionDenied("Ban khong co quyen chinh sua su kien nay.")
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk"),
        )

    def perform_destroy(self, instance):
        if not _can_delete_event(self.request.user, instance):
            raise PermissionDenied("Ban khong co quyen xoa su kien nay.")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="khac-phuc")
    def tao_khac_phuc(self, request, pk=None):
        su_kien = self.get_object()
        if su_kien.nguoi_tao_id and su_kien.nguoi_tao_id == request.user.id:
            return Response(
                {"detail": "User tao moi su kien khong duoc phep tu xu ly su kien nay."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not su_kien.ben_ghi_nhan_su_kien_id:
            return Response(
                {"detail": "Can ghi nhan su kien truoc khi xu ly."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if su_kien.trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG:
            return Response(
                {"detail": "Su kien da xu ly xong, khong the tao them ban ghi khac phuc."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data.copy()
        payload["su_kien"] = str(su_kien.id)
        if not payload.get("ben_xu_ly_su_kien_thiet_bi"):
            payload["ben_xu_ly_su_kien_thiet_bi"] = str(request.user.id)

        serializer = KhacPhucSuKienSerializer(data=payload, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        khac_phuc = serializer.save(nguoi_tao=request.user)

        trang_thai = request.data.get("trang_thai")
        if trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG and not khac_phuc.thoi_gian_xu_ly:
            khac_phuc.thoi_gian_xu_ly = timezone.now()

        if khac_phuc.ben_xu_ly_su_kien_thiet_bi:
            _gan_chu_ky_tu_profile(
                khac_phuc.ben_xu_ly_su_kien_thiet_bi,
                khac_phuc,
                "chu_ky_ben_xu_ly_su_kien_thiet_bi",
            )
        khac_phuc.save()

        if trang_thai in [SuKien.TrangThaiXuLy.DANG_XU_LY, SuKien.TrangThaiXuLy.XU_LY_XONG]:
            su_kien.trang_thai = trang_thai
        else:
            su_kien.trang_thai = SuKien.TrangThaiXuLy.DANG_XU_LY
        su_kien.save()

        response_serializer = self.get_serializer(su_kien)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"khac-phuc/(?P<khac_phuc_id>[^/.]+)")
    def cap_nhat_khac_phuc(self, request, pk=None, khac_phuc_id=None):
        su_kien = self.get_object()
        try:
            khac_phuc = su_kien.khac_phuc_su_kiens.get(pk=khac_phuc_id)
        except KhacPhucSuKien.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay ban ghi khac phuc."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if khac_phuc.nguoi_xac_nhan_xu_ly_id:
            return Response(
                {"detail": "Ban ghi khac phuc da duoc xac nhan, khong the chinh sua."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if khac_phuc.nguoi_tao_id and not _can_edit_remediation(request.user, khac_phuc):
            return Response(
                {
                    "detail": "Ban khong co quyen chinh sua noi dung khac phuc nay."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not khac_phuc.nguoi_tao_id:
            khac_phuc.nguoi_tao = request.user
            khac_phuc.save(update_fields=["nguoi_tao"])

        payload = request.data.copy()
        payload["su_kien"] = str(su_kien.id)
        if not payload.get("ben_xu_ly_su_kien_thiet_bi") and not khac_phuc.ben_xu_ly_su_kien_thiet_bi_id:
            payload["ben_xu_ly_su_kien_thiet_bi"] = str(request.user.id)

        serializer = KhacPhucSuKienSerializer(
            khac_phuc,
            data=payload,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        khac_phuc = serializer.save()

        if khac_phuc.ben_xu_ly_su_kien_thiet_bi:
            _gan_chu_ky_tu_profile(
                khac_phuc.ben_xu_ly_su_kien_thiet_bi,
                khac_phuc,
                "chu_ky_ben_xu_ly_su_kien_thiet_bi",
            )

        trang_thai = request.data.get("trang_thai")
        if trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG and not khac_phuc.thoi_gian_xu_ly:
            khac_phuc.thoi_gian_xu_ly = timezone.now()
        khac_phuc.save()

        if trang_thai in [SuKien.TrangThaiXuLy.DANG_XU_LY, SuKien.TrangThaiXuLy.XU_LY_XONG]:
            su_kien.trang_thai = trang_thai
            su_kien.save()

        response_serializer = self.get_serializer(su_kien)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ghi_nhan_su_kien(self, request, pk=None):
        su_kien = self.get_object()
        if su_kien.nguoi_tao_id and su_kien.nguoi_tao_id == request.user.id:
            return Response(
                {"detail": "User tao moi su kien khong duoc phep ghi nhan su kien cua minh."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not su_kien.ben_ghi_nhan_su_kien_id:
            su_kien.ben_ghi_nhan_su_kien = request.user
        if su_kien.ben_ghi_nhan_su_kien_id == request.user.id:
            _gan_chu_ky_tu_profile(request.user, su_kien, "chu_ky_ben_ghi_nhan_su_kien")
        elif su_kien.ben_ghi_nhan_su_kien:
            _gan_chu_ky_tu_profile(
                su_kien.ben_ghi_nhan_su_kien,
                su_kien,
                "chu_ky_ben_ghi_nhan_su_kien",
            )
        su_kien.save()
        serializer = self.get_serializer(su_kien)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="dien-bien")
    def tao_dien_bien(self, request, pk=None):
        su_kien = self.get_object()
        if not _co_quyen_them_dien_bien(request.user):
            return Response(
                {"detail": "Ban khong co quyen them dien bien su kien."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not su_kien.ben_ghi_nhan_su_kien_id:
            return Response(
                {"detail": "Can ghi nhan su kien truoc khi them dien bien."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if su_kien.trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG:
            return Response(
                {"detail": "Su kien da xu ly xong, khong the them dien bien."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = request.data.copy()
        payload["su_kien"] = str(su_kien.id)
        serializer = DienBienSuKienSerializer(
            data=payload,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(
            nguoi_tao=request.user,
            chuc_danh_nguoi_tao=_lay_chuc_danh_user(request.user),
        )

        response_serializer = self.get_serializer(su_kien)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path=r"dien-bien/(?P<dien_bien_id>[^/.]+)")
    def cap_nhat_dien_bien(self, request, pk=None, dien_bien_id=None):
        su_kien = self.get_object()
        try:
            dien_bien = su_kien.dien_bien_su_kiens.get(pk=dien_bien_id)
        except DienBienSuKien.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay dien bien su kien."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if su_kien.trang_thai == SuKien.TrangThaiXuLy.XU_LY_XONG:
            return Response(
                {"detail": "Su kien da xu ly xong, khong the chinh sua dien bien."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if dien_bien.nguoi_tao_id and not _can_edit_development(request.user, dien_bien):
            return Response(
                {"detail": "Ban khong co quyen chinh sua dien bien su kien nay."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not dien_bien.nguoi_tao_id:
            dien_bien.nguoi_tao = request.user
            dien_bien.chuc_danh_nguoi_tao = _lay_chuc_danh_user(request.user)
            dien_bien.save(update_fields=["nguoi_tao", "chuc_danh_nguoi_tao"])
        elif not dien_bien.chuc_danh_nguoi_tao:
            dien_bien.chuc_danh_nguoi_tao = _lay_chuc_danh_user(dien_bien.nguoi_tao)
            dien_bien.save(update_fields=["chuc_danh_nguoi_tao"])

        payload = request.data.copy()
        payload["su_kien"] = str(su_kien.id)
        serializer = DienBienSuKienSerializer(
            dien_bien,
            data=payload,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        response_serializer = self.get_serializer(su_kien)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def xu_ly_xong(self, request, pk=None):
        su_kien = self.get_object()
        if su_kien.nguoi_tao_id and su_kien.nguoi_tao_id == request.user.id:
            return Response(
                {"detail": "User tao moi su kien khong duoc phep tu xu ly su kien nay."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not su_kien.ben_ghi_nhan_su_kien_id:
            return Response(
                {"detail": "Can ghi nhan su kien truoc khi xu ly."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        su_kien.trang_thai = SuKien.TrangThaiXuLy.XU_LY_XONG
        _gan_chu_ky_tu_profile(su_kien.ben_ghi_nhan_su_kien, su_kien, "chu_ky_ben_ghi_nhan_su_kien")
        khac_phuc = _get_or_create_latest_khac_phuc(su_kien, request.user)
        if khac_phuc.nguoi_tao_id and not _can_edit_remediation(request.user, khac_phuc):
            return Response(
                {
                    "detail": "Ban khong co quyen chinh sua noi dung khac phuc nay."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not khac_phuc.nguoi_tao_id:
            khac_phuc.nguoi_tao = request.user
        if not khac_phuc.thoi_gian_xu_ly:
            khac_phuc.thoi_gian_xu_ly = timezone.now()
        if not khac_phuc.ben_xu_ly_su_kien_thiet_bi_id:
            khac_phuc.ben_xu_ly_su_kien_thiet_bi = request.user
        if khac_phuc.ben_xu_ly_su_kien_thiet_bi:
            _gan_chu_ky_tu_profile(
                khac_phuc.ben_xu_ly_su_kien_thiet_bi,
                khac_phuc,
                "chu_ky_ben_xu_ly_su_kien_thiet_bi",
            )
        su_kien.save()
        khac_phuc.save()
        serializer = self.get_serializer(su_kien)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def xac_nhan_xu_ly(self, request, pk=None):
        su_kien = self.get_object()
        khac_phuc = su_kien.latest_khac_phuc

        if su_kien.trang_thai not in [
            SuKien.TrangThaiXuLy.DANG_XU_LY,
            SuKien.TrangThaiXuLy.XU_LY_XONG,
        ]:
            return Response(
                {"detail": "Su kien phai dang xu ly hoac xu ly xong truoc khi xac nhan."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not khac_phuc:
            return Response(
                {"detail": "Can co noi dung khac phuc truoc khi xac nhan."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if (
            khac_phuc.ben_xu_ly_su_kien_thiet_bi_id
            and khac_phuc.ben_xu_ly_su_kien_thiet_bi_id == request.user.id
        ):
            return Response(
                {"detail": "User dang xu ly su kien khong duoc phep tu xac nhan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not khac_phuc.nguoi_xac_nhan_xu_ly_id:
            khac_phuc.nguoi_xac_nhan_xu_ly = request.user
        if khac_phuc.nguoi_xac_nhan_xu_ly:
            _gan_chu_ky_tu_profile(
                khac_phuc.nguoi_xac_nhan_xu_ly,
                khac_phuc,
                "chu_ky_nguoi_xac_nhan_xu_ly",
            )
        khac_phuc.save()
        serializer = self.get_serializer(su_kien)
        return Response(serializer.data, status=status.HTTP_200_OK)

class SogiaonhancaVHViewSet(viewsets.ModelViewSet):
    serializer_class = SogiaonhancaVHSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["nha_may", "ca_truc", "trang_thai", "ngay_truc", "user_giao_ca", "user_nhan_ca"]
    search_fields = [
        "dia_diem",
        "truc_chinh",
        "truc_phu",
        "truc_ktvh",
        "noi_dung_chi_tiet",
        "luu_y",
        "user_giao_ca__email",
        "user_giao_ca__username",
        "user_nhan_ca__email",
        "user_nhan_ca__username",
    ]
    ordering_fields = ["ngay_truc", "thoi_gian_giao_ca", "created_at", "updated_at"]
    ordering = ["-ngay_truc", "-thoi_gian_giao_ca", "-created_at"]

    def get_queryset(self):
        queryset = SogiaonhancaVH.objects.select_related(
            "nha_may",
            "user_giao_ca",
            "user_nhan_ca",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def perform_create(self, serializer):
        so = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
        so.save()

    def perform_update(self, serializer):
        so = serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk")
        )
        _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
        so.save()

    @action(detail=True, methods=["post"])
    def ky_giao_ca(self, request, pk=None):
        so = self.get_object()
        if not so.giao_ca_ky_at:
            so.giao_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ky_nhan_ca(self, request, pk=None):
        so = self.get_object()
        if not so.nhan_ca_ky_at:
            so.nhan_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)
