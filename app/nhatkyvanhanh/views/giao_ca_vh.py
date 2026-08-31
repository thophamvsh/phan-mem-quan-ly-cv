from django.utils import timezone
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from datetime import date

from core.factory_scope import apply_request_factory_to_serializer, filter_queryset_by_factory
from nhatkyvanhanh.models import (
    SogiaonhancaVH,
    ChiTietSoGiaoNhanCaVH,
    NhanSuSoGiaoNhanCaVH,
    LuuYChiDaoSoGiaoNhanCaVH,
    AnhSoGiaoNhanCaVH,
)
from nhatkyvanhanh.serializers import (
    SogiaonhancaVHSerializer,
    ChiTietSoGiaoNhanCaVHSerializer,
    NhanSuSoGiaoNhanCaVHSerializer,
    LuuYChiDaoSoGiaoNhanCaVHSerializer,
    AnhSoGiaoNhanCaVHSerializer,
)
from quanlycatruc.models import LichTrucCa, NgayTrucCa
from quanlycatruc.permissions import can_access_plant
from quanlycatruc.services import actual_shift_staff


def _sync_legacy_shift_staff(shift_log):
    shift_log._prefetched_objects_cache.pop("nhan_su_ca", None)
    staff = list(shift_log.nhan_su_ca.all())
    primary = next(
        (
            person.ten_nhan_su
            for person in staff
            if person.vai_tro == NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_CHINH
        ),
        "",
    )
    assistants = ", ".join(
        person.ten_nhan_su
        for person in staff
        if person.vai_tro == NhanSuSoGiaoNhanCaVH.VaiTro.TRUC_PHU
    )
    SogiaonhancaVH.objects.filter(pk=shift_log.pk).update(
        truc_chinh=primary,
        truc_phu=assistants,
    )
    shift_log.truc_chinh = primary
    shift_log.truc_phu = assistants
from nhatkyvanhanh.permissions import (
    CanViewShiftHandoverLogs,
    CanCreateShiftHandoverLogs,
    CanReceiveShiftHandoverLogs,
    CanEditShiftHandoverLogs,
    CanDeleteShiftHandoverLogs,
    IsShiftLogCreator,
    IsNotShiftLogCreator,
)
from .helpers import (
    _dong_bo_chu_ky_so_giao_nhan,
    _shift_log_locked,
    _can_edit_shift_log,
    _can_delete_shift_log,
    _is_creator_of_shift_log,
    _can_create_shift_detail,
    _can_update_shift_detail,
    _can_create_shift_directive,
    _can_view_shift_directives,
    _can_update_shift_directive,
)


class SogiaonhancaVHFilterSet(django_filters.FilterSet):
    ngay_truc_tu = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="gte")
    ngay_truc_den = django_filters.DateFilter(field_name="ngay_truc", lookup_expr="lte")

    class Meta:
        model = SogiaonhancaVH
        fields = [
            "nha_may",
            "ca_truc",
            "trang_thai",
            "ngay_truc",
            "ngay_truc_tu",
            "ngay_truc_den",
            "user_giao_ca",
            "user_nhan_ca",
        ]


class SogiaonhancaVHViewSet(viewsets.ModelViewSet):
    serializer_class = SogiaonhancaVHSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SogiaonhancaVHFilterSet
    search_fields = [
        "dia_diem",
        "truc_chinh",
        "truc_phu",
        "nhan_su_ca__ten_nhan_su",
        "truc_ktvh",
        "noi_dung_chi_tiets__tieu_de",
        "noi_dung_chi_tiets__noi_dung",
        "luu_y",
        "user_giao_ca__email",
        "user_giao_ca__username",
        "user_nhan_ca__email",
        "user_nhan_ca__username",
    ]
    ordering_fields = [
        "ngay_truc",
        "thoi_gian_bat_dau_ca",
        "thoi_gian_giao_ca",
        "created_at",
        "updated_at",
    ]
    ordering = ["-ngay_truc", "-thoi_gian_bat_dau_ca", "-thoi_gian_giao_ca", "-created_at"]

    def get_permissions(self):
        permission_classes = [CanViewShiftHandoverLogs]
        if self.action == "create":
            permission_classes = [CanCreateShiftHandoverLogs]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [CanEditShiftHandoverLogs]
        elif self.action == "destroy":
            permission_classes = [CanDeleteShiftHandoverLogs]
        elif self.action in ["tao_nhan_su_ca", "cap_nhat_nhan_su_ca"]:
            permission_classes = [CanEditShiftHandoverLogs]
        elif self.action == "ky_nhan_ca":
            permission_classes = [CanReceiveShiftHandoverLogs, IsNotShiftLogCreator]
        elif self.action == "ky_giao_ca":
            permission_classes = [CanViewShiftHandoverLogs, IsShiftLogCreator]

        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = SogiaonhancaVH.objects.select_related(
            "nha_may",
            "user_giao_ca",
            "user_nhan_ca",
            "nguoi_tao",
        ).prefetch_related(
            "noi_dung_chi_tiets__nguoi_tao",
            "nhan_su_ca__nguoi_tao",
            "luu_y_chi_daos__nguoi_tao",
        ).all()
        return filter_queryset_by_factory(queryset, self.request.user, "nha_may", "fk")

    def _ensure_staff_editable(self, request, shift_log):
        if _shift_log_locked(shift_log):
            raise PermissionDenied(
                "Sổ giao nhận ca đã được nhận ca, không được sửa nhân sự."
            )
        if not _can_edit_shift_log(request.user, shift_log):
            raise PermissionDenied("User không có quyền cập nhật nhân sự ca.")

    def perform_create(self, serializer):
        source_schedule = serializer.validated_data.get("lich_truc_nguon")
        factory_values = apply_request_factory_to_serializer(
            self.request.user, serializer, "nha_may", "fk"
        )
        target_plant = factory_values.get("nha_may") or serializer.validated_data.get("nha_may")
        target_date = serializer.validated_data.get("ngay_truc")
        target_shift = serializer.validated_data.get("ca_truc")
        if target_plant and target_date and target_shift and SogiaonhancaVH.objects.filter(
            nha_may=target_plant, ngay_truc=target_date, ca_truc=target_shift
        ).exists():
            raise ValidationError(
                {"ca_truc": ["Nhà máy này đã có sổ giao nhận ca vận hành cho ca trực này trong ngày đã chọn."]}
            )
        if source_schedule and target_plant and source_schedule.nha_may_id != target_plant.id:
            raise PermissionDenied("Lịch trực nguồn không thuộc nhà máy của sổ.")
        try:
            so = serializer.save(
                user_giao_ca=self.request.user,
                nguoi_tao=self.request.user,
                phien_ban_lich_nguon=source_schedule.phien_ban if source_schedule else None,
                dong_bo_bien_che_at=timezone.now() if source_schedule else None,
                dong_bo_truc_ktvh_at=(
                    timezone.now()
                    if serializer.validated_data.get("so_giao_nhan_ca_hc_nguon")
                    else None
                ),
                **factory_values
            )
            _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
            so.save()
        except DjangoValidationError as exc:
            msg = (
                {"ca_truc": ["Nhà máy này đã có sổ giao nhận ca vận hành cho ca trực này trong ngày đã chọn."]}
                if "already exists" in str(exc)
                else (exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            )
            raise ValidationError(msg)

    def perform_update(self, serializer):
        if _shift_log_locked(serializer.instance):
            raise PermissionDenied("Sổ giao nhận ca đã được nhận ca, không được chỉnh sửa.")
        if not _can_edit_shift_log(self.request.user, serializer.instance):
            raise PermissionDenied("User khong co quyen cap nhat so giao nhan ca.")
        source_schedule = serializer.validated_data.get(
            "lich_truc_nguon", serializer.instance.lich_truc_nguon
        )
        factory_values = apply_request_factory_to_serializer(
            self.request.user, serializer, "nha_may", "fk"
        )
        target_plant = factory_values.get("nha_may") or serializer.validated_data.get(
            "nha_may", serializer.instance.nha_may
        )
        target_date = serializer.validated_data.get("ngay_truc", serializer.instance.ngay_truc)
        target_shift = serializer.validated_data.get("ca_truc", serializer.instance.ca_truc)
        if target_plant and target_date and target_shift and SogiaonhancaVH.objects.filter(
            nha_may=target_plant, ngay_truc=target_date, ca_truc=target_shift
        ).exclude(pk=serializer.instance.pk).exists():
            raise ValidationError(
                {"ca_truc": ["Nhà máy này đã có sổ giao nhận ca vận hành cho ca trực này trong ngày đã chọn."]}
            )
        if source_schedule and source_schedule.nha_may_id != target_plant.id:
            raise PermissionDenied("Lịch trực nguồn không thuộc nhà máy của sổ.")
        try:
            so = serializer.save(
                phien_ban_lich_nguon=source_schedule.phien_ban if source_schedule else None,
                dong_bo_bien_che_at=timezone.now() if source_schedule else serializer.instance.dong_bo_bien_che_at,
                dong_bo_truc_ktvh_at=(
                    timezone.now()
                    if serializer.validated_data.get("so_giao_nhan_ca_hc_nguon")
                    else (
                        None
                        if "so_giao_nhan_ca_hc_nguon" in serializer.validated_data
                        else serializer.instance.dong_bo_truc_ktvh_at
                    )
                ),
                **factory_values
            )
            _dong_bo_chu_ky_so_giao_nhan(so, self.request.user)
            so.save()
        except DjangoValidationError as exc:
            msg = (
                {"ca_truc": ["Nhà máy này đã có sổ giao nhận ca vận hành cho ca trực này trong ngày đã chọn."]}
                if "already exists" in str(exc)
                else (exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
            )
            raise ValidationError(msg)

    @action(detail=False, methods=["get"], url_path="bien-che-lich-truc")
    def bien_che_lich_truc(self, request):
        try:
            plant_id = int(request.query_params.get("nha_may", ""))
            shift_date = date.fromisoformat(request.query_params.get("ngay_truc", ""))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Nhà máy hoặc ngày trực không hợp lệ."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        shift_code = (request.query_params.get("ca_truc") or "").strip().upper()
        shift_period = request.query_params.get("loai_thoi_gian_truc") or ""
        if shift_period not in {"ngay", "dem", "sang", "chieu"} or not shift_code:
            return Response(
                {"detail": "Yêu cầu chọn ca trực và loại thời gian trực."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not can_access_plant(request.user, plant_id):
            raise PermissionDenied("Bạn không có quyền xem lịch trực của nhà máy này.")

        period = "ca_dem" if shift_period in {"dem", "sang"} else "ca_ngay"
        team_field = "kip_ca_dem__ma_kip" if period == "ca_dem" else "kip_ca_ngay__ma_kip"
        eligible_days = NgayTrucCa.objects.filter(
            lich_truc__nha_may_id=plant_id,
            lich_truc__trang_thai__in=[
                LichTrucCa.TrangThai.DA_DUYET,
                LichTrucCa.TrangThai.DANG_AP_DUNG,
                LichTrucCa.TrangThai.DA_KHOA,
            ],
            ngay=shift_date,
        ).select_related(
            "lich_truc", "kip_ca_ngay", "kip_ca_dem"
        ).prefetch_related(
            "dieu_chinh_nhan_su__nhan_su_vang",
            "dieu_chinh_nhan_su__nhan_su_thay",
            "dieu_chinh_doi_den__nhan_su_vang",
            "dieu_chinh_doi_den__nhan_su_thay",
        )
        candidates = list(eligible_days.filter(**{team_field: shift_code}))
        auto_adjusted_shift = False
        if not candidates:
            eligible_candidates = list(eligible_days)
            available_shift_codes = {
                (day.kip_ca_dem if period == "ca_dem" else day.kip_ca_ngay).ma_kip.upper()
                for day in eligible_candidates
            }
            if len(available_shift_codes) == 1:
                shift_code = available_shift_codes.pop()
                candidates = eligible_candidates
                auto_adjusted_shift = True
        priority = {
            LichTrucCa.TrangThai.DANG_AP_DUNG: 3,
            LichTrucCa.TrangThai.DA_KHOA: 2,
            LichTrucCa.TrangThai.DA_DUYET: 1,
        }
        candidates.sort(
            key=lambda day: (priority.get(day.lich_truc.trang_thai, 0), day.lich_truc.phien_ban),
            reverse=True,
        )
        if not candidates:
            return Response(
                {"detail": "Không tìm thấy lịch đã duyệt, đang áp dụng hoặc đã khóa phù hợp với ngày và ca đã chọn."},
                status=status.HTTP_404_NOT_FOUND,
            )
        selected = candidates[0]
        staff = actual_shift_staff(selected, period)
        leaders = [item for item in staff if item.get("vai_tro") == "truong_ca"]
        operation_staff = [
            {
                "nhan_su_id": item.get("nhan_su_id"),
                "user_id": item.get("user_id"),
                "ho_ten": item.get("ho_ten"),
                "vai_tro": item.get("vai_tro"),
                "nguon": item.get("nguon"),
            }
            for item in staff
            if item.get("vai_tro") in {"truc_chinh", "truc_phu"}
        ]
        linked_leaders = [leader for leader in leaders if leader.get("user_id")]
        leader_match = (
            any(leader["user_id"] == request.user.id for leader in linked_leaders)
            if linked_leaders else None
        )
        return Response({
            "lich_truc_id": selected.lich_truc_id,
            "ngay_truc_id": selected.id,
            "phien_ban": selected.lich_truc.phien_ban,
            "trang_thai": selected.lich_truc.trang_thai,
            "ca_truc": shift_code,
            "ca_truc_tu_dong_dieu_chinh": auto_adjusted_shift,
            "loai_ca": period,
            "truong_ca": leaders,
            "truong_ca_khop_nguoi_tao": leader_match,
            "nhan_su": operation_staff,
        })

    def perform_destroy(self, instance):
        if _shift_log_locked(instance):
            raise PermissionDenied("Sổ giao nhận ca đã được nhận ca, không được xóa.")
        if not _can_delete_shift_log(self.request.user, instance):
            raise PermissionDenied("User khong co quyen xoa so giao nhan ca.")
        return super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def ky_giao_ca(self, request, pk=None):
        so = self.get_object()
        if not so.nhan_ca_ky_at:
            return Response(
                {"detail": "Can ky nhan ca truoc khi ky giao ca."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not so.giao_ca_ky_at:
            so.giao_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="noi-dung-chi-tiet")
    def tao_noi_dung_chi_tiet(self, request, pk=None):
        so = self.get_object()
        if _shift_log_locked(so):
            return Response(
                {"detail": "Sổ giao nhận ca đã được nhận ca, không được thêm nội dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not _can_create_shift_detail(request.user, so):
            return Response(
                {"detail": "Chi user giao ca moi duoc them noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ChiTietSoGiaoNhanCaVHSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"noi-dung-chi-tiet/(?P<chi_tiet_id>[^/.]+)",
    )
    def cap_nhat_noi_dung_chi_tiet(self, request, pk=None, chi_tiet_id=None):
        so = self.get_object()
        if _shift_log_locked(so):
            return Response(
                {"detail": "Sổ giao nhận ca đã được nhận ca, không được cập nhật nội dung."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            chi_tiet = so.noi_dung_chi_tiets.get(pk=chi_tiet_id)
        except ChiTietSoGiaoNhanCaVH.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay noi dung chi tiet."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _can_update_shift_detail(request.user, so, chi_tiet):
            return Response(
                {"detail": "Chi user giao ca tao noi dung moi duoc cap nhat noi dung chi tiet."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            chi_tiet.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = ChiTietSoGiaoNhanCaVHSerializer(
            chi_tiet,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="nhan-su-ca")
    def tao_nhan_su_ca(self, request, pk=None):
        shift_log = self.get_object()
        self._ensure_staff_editable(request, shift_log)
        context = {**self.get_serializer_context(), "shift_log": shift_log}
        serializer = NhanSuSoGiaoNhanCaVHSerializer(
            data=request.data,
            context=context,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=shift_log, nguoi_tao=request.user)
        _sync_legacy_shift_staff(shift_log)
        return Response(self.get_serializer(shift_log).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"nhan-su-ca/(?P<nhan_su_id>[^/.]+)",
    )
    def cap_nhat_nhan_su_ca(self, request, pk=None, nhan_su_id=None):
        shift_log = self.get_object()
        self._ensure_staff_editable(request, shift_log)
        try:
            staff_member = shift_log.nhan_su_ca.get(pk=nhan_su_id)
        except NhanSuSoGiaoNhanCaVH.DoesNotExist:
            return Response(
                {"detail": "Không tìm thấy nhân sự ca."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.method == "DELETE":
            staff_member.delete()
        else:
            context = {**self.get_serializer_context(), "shift_log": shift_log}
            serializer = NhanSuSoGiaoNhanCaVHSerializer(
                staff_member,
                data=request.data,
                partial=True,
                context=context,
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

        _sync_legacy_shift_staff(shift_log)
        return Response(self.get_serializer(shift_log).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="luu-y-chi-dao")
    def tao_luu_y_chi_dao(self, request, pk=None):
        so = self.get_object()
        if _shift_log_locked(so):
            raise PermissionDenied("Sổ đã được nhận ca, không được thêm lưu ý chỉ đạo.")
        if not _can_create_shift_directive(request.user, so):
            return Response(
                {"detail": "User khong co quyen tao luu y chi dao."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = LuuYChiDaoSoGiaoNhanCaVHSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(so_giao_nhan_ca=so, nguoi_tao=request.user)
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"luu-y-chi-dao/(?P<directive_id>[^/.]+)",
    )
    def cap_nhat_luu_y_chi_dao(self, request, pk=None, directive_id=None):
        so = self.get_object()
        if _shift_log_locked(so):
            raise PermissionDenied("Sổ đã được nhận ca, không được sửa hoặc xóa lưu ý chỉ đạo.")
        if not _can_view_shift_directives(request.user):
            return Response(
                {"detail": "User khong co quyen xem luu y chi dao."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            directive = so.luu_y_chi_daos.get(pk=directive_id)
        except LuuYChiDaoSoGiaoNhanCaVH.DoesNotExist:
            return Response(
                {"detail": "Khong tim thay luu y chi dao."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not _can_update_shift_directive(request.user, directive):
            return Response(
                {"detail": "Chi user tao luu y chi dao moi duoc cap nhat hoac xoa."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "DELETE":
            directive.delete()
            response_serializer = self.get_serializer(so)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        serializer = LuuYChiDaoSoGiaoNhanCaVHSerializer(
            directive,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_serializer = self.get_serializer(so)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="ca-truoc")
    def ca_truoc(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        factory_id = request.query_params.get("nha_may")
        current_date = request.query_params.get("ngay_truc")
        if factory_id:
            queryset = queryset.filter(nha_may_id=factory_id)
        if current_date:
            queryset = queryset.filter(ngay_truc__lt=current_date)
        previous = queryset.order_by("-ngay_truc", "-thoi_gian_giao_ca").first()
        if not previous:
            return Response({"detail": "Chưa có ca trước."}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(previous).data)

    @action(detail=True, methods=["post"], url_path="hinh-anh")
    def them_hinh_anh(self, request, pk=None):
        so = self.get_object()
        if _shift_log_locked(so) or not _can_edit_shift_log(request.user, so):
            raise PermissionDenied("Sổ đã được nhận ca hoặc bạn không có quyền thêm ảnh.")
        files = request.FILES.getlist("hinh_anh")
        if not files:
            return Response({"hinh_anh": ["Yêu cầu chọn ít nhất một ảnh."]}, status=400)
        if so.hinh_anh_bo_sung.count() + len(files) > 10:
            return Response({"hinh_anh": ["Mỗi sổ được tải tối đa 10 ảnh."]}, status=400)
        allowed = {"image/jpeg", "image/png", "image/webp"}
        for image in files:
            if image.content_type not in allowed or image.size > 25 * 1024 * 1024:
                return Response(
                    {"hinh_anh": ["Ảnh phải là JPG, PNG hoặc WebP và không vượt quá 25 MB."]},
                    status=400,
                )
        created = []
        for index, image in enumerate(files, start=so.hinh_anh_bo_sung.count() + 1):
            created.append(
                AnhSoGiaoNhanCaVH.objects.create(
                    so_giao_nhan_ca=so,
                    hinh_anh=image,
                    thu_tu=index,
                    nguoi_tao=request.user,
                )
            )
        return Response(
            AnhSoGiaoNhanCaVHSerializer(
                created, many=True, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def ky_nhan_ca(self, request, pk=None):
        so = self.get_object()
        if so.user_nhan_ca_id and so.user_nhan_ca_id != request.user.id:
            return Response(
                {"detail": "So da duoc gan user nhan ca khac."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not so.nhan_ca_ky_at:
            if not so.user_nhan_ca_id:
                so.user_nhan_ca = request.user
            so.nhan_ca_ky_at = timezone.now()
            _dong_bo_chu_ky_so_giao_nhan(so, request.user)
            so.save()
        serializer = self.get_serializer(so)
        return Response(serializer.data, status=status.HTTP_200_OK)
