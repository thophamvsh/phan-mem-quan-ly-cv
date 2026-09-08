from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.models import DataSyncAudit, User
from core.sync_audit import record_data_sync, uploaded_file_sha256
from .models import BoPhan, DonViToChuc, NhaMay, NhanSu
from .permissions import (
    OrganizationDirectoryPermission,
    can_access_organization_plant,
)
from .serializers import (
    BoPhanSerializer,
    DonViToChucSerializer,
    NhaMaySerializer,
    NhanSuSerializer,
)
from .excel import build_staff_workbook, staff_dataset_from_upload, workbook_response
from .resources import NhanSuResource


def _user_plant_id(user):
    return getattr(getattr(user, "profile", None), "nha_may_id", None)


def _scope_units(queryset, user):
    if user.is_superuser or getattr(
        getattr(user, "profile", None),
        "is_all_factories",
        False,
    ):
        return queryset
    plant_id = _user_plant_id(user)
    if not plant_id:
        return queryset.none()
    return queryset.filter(
        Q(nha_may_id=plant_id)
        | Q(nha_may__isnull=True, don_vi_cha__nha_may_id=plant_id)
        | Q(
            nha_may__isnull=True,
            don_vi_cha__nha_may__isnull=True,
            don_vi_cha__don_vi_cha__nha_may_id=plant_id,
        )
    ).distinct()


def _scope_staff(queryset, user):
    if user.is_superuser or getattr(
        getattr(user, "profile", None),
        "is_all_factories",
        False,
    ):
        return queryset
    plant_id = _user_plant_id(user)
    if not plant_id:
        return queryset.none()
    return queryset.filter(
        Q(don_vi__nha_may_id=plant_id)
        | Q(
            don_vi__nha_may__isnull=True,
            don_vi__don_vi_cha__nha_may_id=plant_id,
        )
        | Q(
            don_vi__nha_may__isnull=True,
            don_vi__don_vi_cha__nha_may__isnull=True,
            don_vi__don_vi_cha__don_vi_cha__nha_may_id=plant_id,
        )
    ).distinct()


class NhaMayViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NhaMaySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    queryset = NhaMay.objects.order_by("ten_nha_may")

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_superuser or getattr(
            getattr(self.request.user, "profile", None),
            "is_all_factories",
            False,
        ):
            return queryset
        plant_id = _user_plant_id(self.request.user)
        return queryset.filter(pk=plant_id) if plant_id else queryset.none()


class NhanSuViewSet(viewsets.ModelViewSet):
    serializer_class = NhanSuSerializer
    permission_classes = [OrganizationDirectoryPermission]
    pagination_class = None
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "don_vi",
        "bo_phan",
        "user",
        "dang_lam_viec",
    ]
    search_fields = ["ho_ten", "ma_nhan_vien", "chuc_danh"]
    ordering_fields = ["ho_ten", "ma_nhan_vien", "tu_ngay"]
    ordering = ["don_vi", "bo_phan", "ho_ten"]

    def _excel_units(self, request):
        queryset = _scope_units(DonViToChuc.objects.all(), request.user)
        plant_id = request.query_params.get("nha_may")
        if not plant_id:
            return queryset
        if not can_access_organization_plant(request.user, plant_id):
            raise PermissionDenied("Bạn không có quyền truy cập nhà máy đã chọn.")
        return queryset.filter(
            Q(nha_may_id=plant_id)
            | Q(don_vi_cha__nha_may_id=plant_id)
            | Q(don_vi_cha__don_vi_cha__nha_may_id=plant_id)
        ).distinct()

    def _excel_scope(self, request):
        queryset = self.get_queryset()
        plant_id = request.query_params.get("nha_may")
        if plant_id:
            if not can_access_organization_plant(request.user, plant_id):
                raise PermissionDenied("Bạn không có quyền truy cập nhà máy đã chọn.")
            queryset = queryset.filter(
                Q(don_vi__nha_may_id=plant_id)
                | Q(don_vi__don_vi_cha__nha_may_id=plant_id)
                | Q(don_vi__don_vi_cha__don_vi_cha__nha_may_id=plant_id)
            ).distinct()
        return queryset

    def get_queryset(self):
        return _scope_staff(
            NhanSu.objects.select_related("don_vi", "bo_phan", "user"),
            self.request.user,
        )

    def _ensure_unit_access(self, serializer):
        unit = serializer.validated_data.get(
            "don_vi",
            getattr(serializer.instance, "don_vi", None),
        )
        if not unit or not can_access_organization_plant(
            self.request.user,
            unit.nha_may_pham_vi_id,
        ):
            raise PermissionDenied(
                "Bạn không có quyền quản lý nhân sự trong đơn vị này."
            )

    def perform_create(self, serializer):
        self._ensure_unit_access(serializer)
        person = serializer.save()

        # Quan hệ tích hợp thuộc module lịch trực, chỉ được tạo khi nhân sự
        # được thêm qua API. Việc tạo model trực tiếp (migration/test/import)
        # không bị phát sinh dữ liệu ngoài ý muốn.
        from quanlycatruc.models import (
            ChiTietPhuongAnPhanCongCa,
            NhomLichTruc,
            PhamViNhanSuCaTruc,
            PhuongAnPhanCongCa,
        )

        plant_id = person.nha_may_id
        if not plant_id:
            return
        for group in NhomLichTruc.objects.filter(
            nha_may_id=plant_id,
            dang_hoat_dong=True,
        ):
            PhamViNhanSuCaTruc.objects.get_or_create(
                nhom_lich=group,
                nhan_su=person,
                defaults={"dang_hoat_dong": True},
            )
        for plan in PhuongAnPhanCongCa.objects.filter(
            nha_may_id=plant_id,
            trang_thai=PhuongAnPhanCongCa.TrangThai.DU_THAO,
        ):
            ChiTietPhuongAnPhanCongCa.objects.get_or_create(
                phuong_an=plan,
                nhan_su=person,
                defaults={
                    "kip_truc": None,
                    "vai_tro": "",
                    "thu_tu_hien_thi": 1,
                },
            )

    def perform_update(self, serializer):
        self._ensure_unit_access(serializer)
        serializer.save()

    def perform_destroy(self, instance):
        instance.dang_lam_viec = False
        instance.den_ngay = instance.den_ngay or max(
            date.today(),
            instance.tu_ngay,
        )
        instance.save(
            update_fields=["dang_lam_viec", "den_ngay", "updated_at"]
        )

    @action(detail=False, methods=["get"], url_path="tai-khoan-options")
    def tai_khoan_options(self, request):
        plant_id = request.query_params.get("nha_may")
        if not plant_id or not can_access_organization_plant(
            request.user,
            plant_id,
        ):
            raise PermissionDenied(
                "Bạn không có quyền xem tài khoản của nhà máy này."
            )
        queryset = User.objects.filter(
            is_active=True,
            profile__nha_may_id=plant_id,
        ).select_related("profile").order_by("username")
        return Response(
            [
                {
                    "id": item.id,
                    "username": item.username,
                    "full_name": (
                        item.profile.full_name
                        or item.get_full_name()
                        or item.username
                    ),
                }
                for item in queryset
            ]
        )

    @action(detail=False, methods=["get"], url_path="excel-template")
    def excel_template(self, request):
        staff = self._excel_scope(request)
        units = self._excel_units(request)
        departments = BoPhan.objects.filter(don_vi__in=units)
        content = build_staff_workbook(
            staff.none(),
            units.order_by("ma_don_vi"),
            departments.order_by("don_vi", "ma_bo_phan"),
            is_template=True,
        )
        return workbook_response(content, "mau-danh-muc-nhan-su.xlsx")

    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        staff = self.filter_queryset(self._excel_scope(request)).select_related(
            "don_vi", "bo_phan", "user"
        )
        units = DonViToChuc.objects.filter(pk__in=staff.values("don_vi_id"))
        departments = BoPhan.objects.filter(pk__in=staff.values("bo_phan_id"))
        content = build_staff_workbook(staff, units, departments)
        return workbook_response(content, "danh-muc-nhan-su.xlsx")

    @action(
        detail=False,
        methods=["post"],
        url_path="import-excel",
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_excel(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "Vui lòng chọn file Excel."}, status=status.HTTP_400_BAD_REQUEST)
        if not uploaded_file.name.lower().endswith(".xlsx"):
            return Response({"detail": "Chỉ hỗ trợ file Excel .xlsx."}, status=status.HTTP_400_BAD_REQUEST)
        started_at = timezone.now()
        checksum = uploaded_file_sha256(uploaded_file)
        audit_plant = getattr(getattr(request.user, "profile", None), "nha_may", None)
        dataset = None
        try:
            dataset = staff_dataset_from_upload(uploaded_file)
            allowed_units = {
                item.ma_don_vi: item
                for item in self._excel_units(request)
            }
            invalid_units = sorted({
                str(row.get("ma_don_vi") or "").strip()
                for row in dataset.dict
                if str(row.get("ma_don_vi") or "").strip() not in allowed_units
            })
            if invalid_units:
                return Response(
                    {"detail": f"Không có quyền hoặc không tồn tại đơn vị: {', '.join(invalid_units)}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            plant_ids = {
                unit.nha_may_pham_vi_id
                for unit in allowed_units.values()
                if unit.nha_may_pham_vi_id
                and any(str(row.get("ma_don_vi") or "").strip() == unit.ma_don_vi for row in dataset.dict)
            }
            if len(plant_ids) == 1:
                audit_plant = NhaMay.objects.filter(pk=next(iter(plant_ids))).first()
            usernames = {
                str(row.get("username") or "").strip()
                for row in dataset.dict
                if str(row.get("username") or "").strip()
            }
            users = {
                item.username: item
                for item in User.objects.filter(username__in=usernames).select_related("profile")
            }
            for row in dataset.dict:
                username = str(row.get("username") or "").strip()
                if not username:
                    continue
                user = users.get(username)
                if not user:
                    raise ValueError(f"Không tồn tại tài khoản: {username}.")
                unit = allowed_units[str(row.get("ma_don_vi") or "").strip()]
                if getattr(user.profile, "nha_may_id", None) != unit.nha_may_pham_vi_id:
                    raise ValueError(
                        f"Tài khoản {username} không thuộc cùng nhà máy với đơn vị {unit.ma_don_vi}."
                    )
            with transaction.atomic():
                result = NhanSuResource().import_data(
                    dataset,
                    dry_run=False,
                    raise_errors=True,
                    use_transactions=True,
                )
        except Exception as exc:
            record_data_sync(
                actor=request.user, nha_may=audit_plant,
                source=DataSyncAudit.Source.EXCEL,
                data_type="Danh mục nhân sự", status=DataSyncAudit.Status.FAILED,
                started_at=started_at,
                processed_count=dataset.height if dataset is not None else 0,
                failed_count=dataset.height if dataset is not None else 1,
                filename=uploaded_file.name, checksum_sha256=checksum,
                error_summary=str(exc),
            )
            return Response({"detail": f"Không thể nhập Excel: {exc}"}, status=status.HTTP_400_BAD_REQUEST)
        sync_status = (
            DataSyncAudit.Status.PARTIAL
            if result.totals.get("error", 0) or result.totals.get("invalid", 0)
            else DataSyncAudit.Status.SUCCESS
        )
        record_data_sync(
            actor=request.user, nha_may=audit_plant,
            source=DataSyncAudit.Source.EXCEL,
            data_type="Danh mục nhân sự", status=sync_status,
            started_at=started_at, processed_count=dataset.height,
            created_count=result.totals.get("new", 0),
            updated_count=result.totals.get("update", 0),
            skipped_count=result.totals.get("skip", 0),
            failed_count=result.totals.get("error", 0) + result.totals.get("invalid", 0),
            filename=uploaded_file.name, checksum_sha256=checksum,
        )
        return Response({
            "message": "Nhập danh mục nhân sự thành công.",
            "total": dataset.height,
            "created": result.totals.get("new", 0),
            "updated": result.totals.get("update", 0),
            "skipped": result.totals.get("skip", 0),
        })


class DonViToChucViewSet(viewsets.ModelViewSet):
    serializer_class = DonViToChucSerializer
    permission_classes = [OrganizationDirectoryPermission]
    pagination_class = None
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "nha_may",
        "don_vi_cha",
        "loai_don_vi",
        "dang_hoat_dong",
    ]
    search_fields = ["ma_don_vi", "ten_don_vi"]
    ordering_fields = ["thu_tu", "ma_don_vi", "ten_don_vi"]
    ordering = ["thu_tu", "ten_don_vi"]

    def get_queryset(self):
        return _scope_units(
            DonViToChuc.objects.select_related("nha_may", "don_vi_cha"),
            self.request.user,
        )

    def _validated_plant_id(self, serializer):
        plant = serializer.validated_data.get(
            "nha_may",
            getattr(serializer.instance, "nha_may", None),
        )
        parent = serializer.validated_data.get(
            "don_vi_cha",
            getattr(serializer.instance, "don_vi_cha", None),
        )
        return plant.id if plant else (
            parent.nha_may_pham_vi_id if parent else None
        )

    def perform_create(self, serializer):
        plant_id = self._validated_plant_id(serializer)
        if not plant_id and not self.request.user.is_superuser:
            raise PermissionDenied(
                "Chỉ quản trị viên hệ thống được tạo đơn vị cấp công ty."
            )
        if plant_id and not can_access_organization_plant(
            self.request.user,
            plant_id,
        ):
            raise PermissionDenied(
                "Bạn không có quyền tạo đơn vị trong nhà máy này."
            )
        serializer.save()

    def perform_update(self, serializer):
        plant_id = self._validated_plant_id(serializer)
        if not plant_id and not self.request.user.is_superuser:
            raise PermissionDenied(
                "Chỉ quản trị viên hệ thống được quản lý đơn vị cấp công ty."
            )
        if plant_id and not can_access_organization_plant(
            self.request.user,
            plant_id,
        ):
            raise PermissionDenied(
                "Bạn không có quyền chuyển đơn vị sang nhà máy này."
            )
        serializer.save()

    def perform_destroy(self, instance):
        instance.dang_hoat_dong = False
        instance.save(update_fields=["dang_hoat_dong", "updated_at"])

    @action(detail=False, methods=["get"], url_path="options")
    def options(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            dang_hoat_dong=True
        )
        return Response(
            [
                {"id": item.id, "label": str(item)}
                for item in queryset
            ]
        )


class BoPhanViewSet(viewsets.ModelViewSet):
    serializer_class = BoPhanSerializer
    permission_classes = [OrganizationDirectoryPermission]
    pagination_class = None
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["don_vi", "loai_bo_phan", "dang_hoat_dong"]
    search_fields = ["ma_bo_phan", "ten_bo_phan"]
    ordering_fields = ["thu_tu", "ma_bo_phan", "ten_bo_phan"]
    ordering = ["don_vi", "thu_tu", "ten_bo_phan"]

    def get_queryset(self):
        queryset = BoPhan.objects.select_related(
            "don_vi",
            "don_vi__nha_may",
        )
        if self.request.user.is_superuser or getattr(
            getattr(self.request.user, "profile", None),
            "is_all_factories",
            False,
        ):
            scoped = queryset
        else:
            plant_id = _user_plant_id(self.request.user)
            scoped = (
                queryset.filter(don_vi__nha_may_id=plant_id)
                if plant_id
                else queryset.none()
            )
        plant_id = self.request.query_params.get("nha_may")
        return (
            scoped.filter(don_vi__nha_may_id=plant_id)
            if plant_id
            else scoped
        )

    def _validate_unit_scope(self, unit):
        if not can_access_organization_plant(
            self.request.user,
            unit.nha_may_pham_vi_id,
        ):
            raise PermissionDenied(
                "Bạn không có quyền quản lý bộ phận trong đơn vị này."
            )

    def perform_create(self, serializer):
        self._validate_unit_scope(serializer.validated_data["don_vi"])
        serializer.save()

    def perform_update(self, serializer):
        unit = serializer.validated_data.get(
            "don_vi",
            serializer.instance.don_vi,
        )
        self._validate_unit_scope(unit)
        serializer.save()

    def perform_destroy(self, instance):
        instance.dang_hoat_dong = False
        instance.save(update_fields=["dang_hoat_dong", "updated_at"])

    @action(detail=False, methods=["get"], url_path="options")
    def options(self, request):
        queryset = self.filter_queryset(self.get_queryset()).filter(
            dang_hoat_dong=True
        )
        return Response(
            [
                {"id": item.id, "label": item.ten_bo_phan}
                for item in queryset
            ]
        )
