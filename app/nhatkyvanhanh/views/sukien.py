from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
import django_filters
from datetime import datetime
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from core.factory_scope import (
    apply_request_factory_to_serializer,
    filter_queryset_by_factory,
    get_user_factory,
    has_all_factory_access,
)
from nhatkyvanhanh.models import SuKien, ChiDaoSuKien, DienBienSuKien, KhacPhucSuKien, Sonhatkyvanhanh
from nhatkyvanhanh.serializers import (
    NhatKySuKienSerializer,
    ChiDaoSuKienSerializer,
    DienBienSuKienSerializer,
    KhacPhucSuKienSerializer,
    user_can_edit_chi_dao,
)
from nhatkyvanhanh.permissions import (
    CanViewOperationEvents,
    CanCreateOperationEvents,
    CanEditOperationEvents,
    CanDeleteOperationEvents,
    CanAcknowledgeOperationEvents,
    CanProcessOperationEvents,
    CanConfirmOperationEvents,
)
from .helpers import (
    _can_edit_event,
    _lay_chuc_danh_user,
    _can_delete_event,
    _factory_from_dashboard_param,
    _factory_ids_from_dashboard_param,
    _is_song_hinh_factory,
    _is_song_hinh_dashboard_param,
    _normalize_event_status,
    _normalize_event_type,
    _gan_chu_ky_tu_profile,
    _co_quyen_them_dien_bien,
    _can_edit_remediation,
    _can_edit_development,
    _get_or_create_latest_khac_phuc,
)

User = get_user_model()


class NhatKySuKienFilterSet(django_filters.FilterSet):
    id = django_filters.UUIDFilter(field_name="id")
    ngay_xay_ra = django_filters.DateFilter(
        field_name="thoi_gian_xay_ra",
        lookup_expr="date",
    )
    ngay_xay_ra_tu = django_filters.DateFilter(
        field_name="thoi_gian_xay_ra",
        lookup_expr="date__gte",
    )
    ngay_xay_ra_den = django_filters.DateFilter(
        field_name="thoi_gian_xay_ra",
        lookup_expr="date__lte",
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
            "thiet_bi",
            "id",
            "loai",
            "trang_thai",
            "ben_ghi_nhan_su_kien",
            "ben_xu_ly_su_kien_thiet_bi",
            "ngay_xay_ra",
            "ngay_xay_ra_tu",
            "ngay_xay_ra_den",
        ]


class NhatKySuKienViewSet(viewsets.ModelViewSet):
    serializer_class = NhatKySuKienSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = NhatKySuKienFilterSet
    search_fields = [
        "ten_he_thong_thiet_bi",
        "thiet_bi__ten",
        "thiet_bi__ma_day_du",
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
        elif self.action in ["update", "partial_update"]:
            permission_classes = [CanEditOperationEvents]
        elif self.action == "destroy":
            permission_classes = [CanDeleteOperationEvents]
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
        elif self.action == "tao_chi_dao":
            permission_classes = [CanViewOperationEvents]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = self._build_event_queryset()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def _build_event_queryset(self):
        latest_khac_phuc = KhacPhucSuKien.objects.filter(
            su_kien_id=OuterRef("pk")
        ).order_by("-thoi_gian_xu_ly", "-created_at")

        return (
            SuKien.objects.select_related(
                "nha_may",
                "thiet_bi",
                "nguoi_tao",
                "nguoi_chi_dao",
                "ben_ghi_nhan_su_kien",
            )
            .prefetch_related(
                "chi_dao_su_kiens",
                "chi_dao_su_kiens__nguoi_chi_dao",
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

    def perform_create(self, serializer):
        serializer.save(
            nguoi_tao=self.request.user,
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk"),
        )

    def perform_update(self, serializer):
        request_fields = {
            key
            for key in self.request.data.keys()
            if key not in {"csrfmiddlewaretoken"}
        }
        is_chi_dao_only_update = request_fields and request_fields <= {"chi_dao"}
        if (
            not _can_edit_event(self.request.user, serializer.instance)
            and not (is_chi_dao_only_update and user_can_edit_chi_dao(self.request.user))
        ):
            raise PermissionDenied("Ban khong co quyen chinh sua su kien nay.")
        if is_chi_dao_only_update and not _can_edit_event(self.request.user, serializer.instance):
            serializer.save()
            return
        serializer.save(
            **apply_request_factory_to_serializer(self.request.user, serializer, "nha_may", "fk"),
        )

    @action(detail=True, methods=["post"], url_path="chi-dao")
    def tao_chi_dao(self, request, pk=None):
        su_kien = self.get_object()
        if not user_can_edit_chi_dao(request.user):
            raise PermissionDenied("Chi lanh dao moi duoc cap nhat noi dung chi dao.")

        serializer = ChiDaoSuKienSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        chi_dao = serializer.save(
            su_kien=su_kien,
            nguoi_chi_dao=request.user,
            chuc_danh_nguoi_chi_dao=_lay_chuc_danh_user(request.user),
        )

        # Keep legacy fields populated for screens/reports that still read SuKien.chi_dao.
        su_kien.chi_dao = chi_dao.noi_dung
        su_kien.nguoi_chi_dao = request.user
        su_kien.chu_ky_nguoi_chi_dao = chi_dao.chu_ky_nguoi_chi_dao
        su_kien.save(update_fields=["chi_dao", "nguoi_chi_dao", "chu_ky_nguoi_chi_dao", "updated_at"])
        return Response(
            ChiDaoSuKienSerializer(chi_dao, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        if not _can_delete_event(self.request.user, instance):
            raise PermissionDenied("Ban khong co quyen xoa su kien nay.")
        instance.delete()

    @action(detail=False, methods=["get"], url_path="dashboard-summary")
    def dashboard_summary(self, request):
        date_str = request.query_params.get("date")
        try:
            target_date = (
                datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str
                else timezone.localdate()
            )
        except ValueError:
            return Response(
                {"detail": "Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        year = int(request.query_params.get("year") or target_date.year)
        nhamay_param = request.query_params.get("nhamay")
        factory = _factory_from_dashboard_param(nhamay_param)
        factory_ids = _factory_ids_from_dashboard_param(nhamay_param)
        loai = request.query_params.get("loai")
        scope = request.query_params.get("scope") or "ytd"

        events_qs = self._build_event_queryset()
        if scope != "all":
            events_qs = events_qs.filter(
                thoi_gian_xay_ra__date__gte=datetime(year, 1, 1).date(),
            )
            if scope != "year":
                events_qs = events_qs.filter(thoi_gian_xay_ra__date__lte=target_date)
        logbooks_qs = Sonhatkyvanhanh.objects.all()

        if factory_ids:
            factory_query = Q(nha_may_id__in=factory_ids)
            if _is_song_hinh_factory(factory) or _is_song_hinh_dashboard_param(nhamay_param):
                factory_query |= Q(nha_may__isnull=True)
            if not has_all_factory_access(request.user):
                user_factory = get_user_factory(request.user)
                if not user_factory or user_factory.id not in factory_ids:
                    events_qs = events_qs.none()
                else:
                    events_qs = events_qs.filter(factory_query)
            else:
                events_qs = events_qs.filter(factory_query)
            logbooks_qs = logbooks_qs.filter(nha_may_id__in=factory_ids)
        else:
            events_qs = filter_queryset_by_factory(
                events_qs,
                request.user,
                "nha_may",
                "fk",
            )
            logbooks_qs = filter_queryset_by_factory(
                logbooks_qs,
                request.user,
                "nha_may",
                "fk",
            )

        base_status_counts = {
            SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG: 0,
            SuKien.TrangThaiXuLy.DANG_XU_LY: 0,
            SuKien.TrangThaiXuLy.XU_LY_XONG: 0,
        }
        base_type_counts = {
            SuKien.LoaiSuKien.SU_CO: 0,
            SuKien.LoaiSuKien.KHIEM_KHUYET: 0,
        }
        status_by_type = {
            event_type: dict(base_status_counts)
            for event_type in base_type_counts.keys()
        }

        for item in events_qs.values("trang_thai").annotate(total=Count("id")):
            status = _normalize_event_status(item["trang_thai"])
            if status in base_status_counts:
                base_status_counts[status] += item["total"]

        for item in events_qs.values("loai").annotate(total=Count("id")):
            event_type = _normalize_event_type(item["loai"])
            if event_type in base_type_counts:
                base_type_counts[event_type] += item["total"]

        for item in events_qs.values("loai", "trang_thai").annotate(total=Count("id")):
            event_type = _normalize_event_type(item["loai"])
            status = _normalize_event_status(item["trang_thai"])
            if event_type in status_by_type and status in status_by_type[event_type]:
                status_by_type[event_type][status] += item["total"]

        filtered_events_qs = events_qs
        if loai in dict(SuKien.LoaiSuKien.choices):
            filtered_events_qs = events_qs.filter(loai=loai)

        selected_status_counts = dict(base_status_counts)
        if loai in status_by_type:
            selected_status_counts = dict(status_by_type[loai])

        open_events = (
            filtered_events_qs.filter(
                trang_thai__in=[
                    SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG,
                    SuKien.TrangThaiXuLy.DANG_XU_LY,
                ]
            )
            .order_by("-thoi_gian_xay_ra", "-created_at")[:8]
        )

        serializer = self.get_serializer(open_events, many=True)
        operation_log_count = logbooks_qs.filter(thoi_gian_tao__date=target_date).count()

        return Response(
            {
                "date": target_date.isoformat(),
                "year": year,
                "operation_log_count": operation_log_count,
                "has_operation_log": operation_log_count > 0,
                "status_counts": {
                    "chua_xu_ly_xong": selected_status_counts[SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG],
                    "dang_xu_ly": selected_status_counts[SuKien.TrangThaiXuLy.DANG_XU_LY],
                    "xu_ly_xong": selected_status_counts[SuKien.TrangThaiXuLy.XU_LY_XONG],
                },
                "type_counts": {
                    "su_co": base_type_counts[SuKien.LoaiSuKien.SU_CO],
                    "khiem_khuyet": base_type_counts[SuKien.LoaiSuKien.KHIEM_KHUYET],
                },
                "status_by_type": {
                    "su_co": {
                        "chua_xu_ly_xong": status_by_type[SuKien.LoaiSuKien.SU_CO][SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG],
                        "dang_xu_ly": status_by_type[SuKien.LoaiSuKien.SU_CO][SuKien.TrangThaiXuLy.DANG_XU_LY],
                        "xu_ly_xong": status_by_type[SuKien.LoaiSuKien.SU_CO][SuKien.TrangThaiXuLy.XU_LY_XONG],
                    },
                    "khiem_khuyet": {
                        "chua_xu_ly_xong": status_by_type[SuKien.LoaiSuKien.KHIEM_KHUYET][SuKien.TrangThaiXuLy.CHUA_XU_LY_XONG],
                        "dang_xu_ly": status_by_type[SuKien.LoaiSuKien.KHIEM_KHUYET][SuKien.TrangThaiXuLy.DANG_XU_LY],
                        "xu_ly_xong": status_by_type[SuKien.LoaiSuKien.KHIEM_KHUYET][SuKien.TrangThaiXuLy.XU_LY_XONG],
                    },
                },
                "open_events": serializer.data,
            }
        )

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
