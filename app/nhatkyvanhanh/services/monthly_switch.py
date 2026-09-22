from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q


class MonthlySwitchCalculationService:
    """Single source of truth for monthly-switch calculations and carry-forward."""

    ZERO = Decimal("0.000")

    @classmethod
    def calculate(cls, detail, previous_luy_ke=None):
        dau_nam = detail.dau_nam or cls.ZERO
        dau_thang = detail.dau_thang or cls.ZERO
        nhap = detail.nhap_trong_thang or cls.ZERO
        cuoi_thang = detail.cuoi_thang or cls.ZERO
        base_luy_ke = (
            detail.luy_ke_truoc_so_hoa or cls.ZERO
            if previous_luy_ke is None
            else previous_luy_ke
        )

        if detail.loai_tinh_toan == "fuel":
            thuc_hien = dau_thang + nhap - cuoi_thang
            if thuc_hien < 0:
                raise ValidationError("Lượng nhiên liệu tiêu hao không được âm.")
            luy_ke_nam = base_luy_ke + thuc_hien
        else:
            thuc_hien = cuoi_thang - dau_thang
            if thuc_hien < 0:
                raise ValidationError(
                    "Chỉ số cuối tháng không được nhỏ hơn chỉ số đầu tháng."
                )
            luy_ke_nam = cuoi_thang - dau_nam
            if luy_ke_nam < 0:
                raise ValidationError(
                    "Chỉ số cuối tháng không được nhỏ hơn chỉ số đầu năm."
                )
        return thuc_hien, luy_ke_nam

    @classmethod
    def apply(cls, detail, previous_luy_ke=None):
        detail.thuc_hien, detail.luy_ke_nam = cls.calculate(
            detail, previous_luy_ke=previous_luy_ke
        )
        return detail

    @classmethod
    def propagate_from(cls, source_log):
        """Carry revised closing values through later unlocked logs.

        Caller must already be inside ``transaction.atomic()``. Logs are locked in
        chronological order, and propagation stops before the first approved log.
        """
        from nhatkyvanhanh.models import SoChuyenDoiTBThang

        previous_by_identity = {
            row.ma_dinh_danh: row
            for row in source_log.chi_tiets.select_for_update().all()
        }
        future_logs = (
            SoChuyenDoiTBThang.objects.select_for_update()
            .filter(nha_may=source_log.nha_may)
            .filter(
                Q(nam__gt=source_log.nam)
                | Q(nam=source_log.nam, thang__gt=source_log.thang)
            )
            .order_by("nam", "thang", "created_at")
        )

        updated_months = []
        blocked_month = None
        for log in future_logs:
            if log.da_khoa:
                blocked_month = {"nam": log.nam, "thang": log.thang}
                break

            current_rows = list(log.chi_tiets.select_for_update().all())
            for row in current_rows:
                previous = previous_by_identity.get(row.ma_dinh_danh)
                if previous is None:
                    continue
                row.dau_thang = previous.cuoi_thang
                if log.thang == 1:
                    row.dau_nam = previous.cuoi_thang
                    row.luy_ke_truoc_so_hoa = cls.ZERO
                else:
                    row.dau_nam = previous.dau_nam
                    row.luy_ke_truoc_so_hoa = previous.luy_ke_nam

                if row.loai_tinh_toan == "fuel":
                    maximum_closing = row.dau_thang + row.nhap_trong_thang
                    if row.cuoi_thang > maximum_closing:
                        row.cuoi_thang = maximum_closing
                elif row.cuoi_thang < row.dau_thang:
                    row.cuoi_thang = row.dau_thang
                row.save()

            previous_by_identity = {row.ma_dinh_danh: row for row in current_rows}
            updated_months.append({"nam": log.nam, "thang": log.thang})

        if blocked_month:
            message = (
                f"Đã cập nhật lũy kế đến trước tháng {blocked_month['thang']}/"
                f"{blocked_month['nam']}. Tháng này đã được duyệt nên không thể "
                "tự động sửa đổi."
            )
        else:
            message = "Đã cập nhật và lan truyền số liệu sang các sổ chưa khóa."
        return {
            "updated_months": updated_months,
            "blocked_month": blocked_month,
            "message": message,
        }

    @classmethod
    def update_rows_and_propagate(cls, log, updates, serializer_context=None):
        """Atomically update a set of rows and propagate their new baselines."""
        from nhatkyvanhanh.models import ChiTietChuyenDoiTBThang
        from nhatkyvanhanh.models import SoChuyenDoiTBThang
        from nhatkyvanhanh.serializers import ChiTietChuyenDoiTBThangSerializer

        updates_by_id = {str(item.get("id")): item for item in updates if item.get("id")}
        with transaction.atomic():
            locked_log = SoChuyenDoiTBThang.objects.select_for_update().get(pk=log.pk)
            locked_rows = list(
                ChiTietChuyenDoiTBThang.objects.select_for_update().filter(
                    so=locked_log, id__in=updates_by_id
                )
            )
            if len(locked_rows) != len(updates_by_id):
                raise ValidationError("Có chi tiết không thuộc sổ đang cập nhật.")
            for row in locked_rows:
                payload = updates_by_id[str(row.id)]
                serializer = ChiTietChuyenDoiTBThangSerializer(
                    row,
                    data=payload,
                    partial=True,
                    context=serializer_context or {},
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
            propagation = cls.propagate_from(locked_log)
        return propagation
