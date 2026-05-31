import io
import pandas as pd
from datetime import datetime
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from ..models import MucnuocQuytrinh
from ..serializers import MucnuocQuytrinhSerializer
from .views_sanxuat import user_can_access_plant, user_can_modify_hydrology_object


MUCNUOC_QUYTRINH_EXPORT_COLUMNS = {
    "ngay_bat_dau": "Ngày bắt đầu",
    "ngay_ket_thuc": "Ngày kết thúc",
    "muc_nuoc_bat_dau": "Mực nước hồ từ",
    "muc_nuoc_ket_thuc": "Mực nước hồ kết thúc",
}

MUCNUOC_QUYTRINH_IMPORT_COLUMNS = {
    "ngay_bat_dau": "ngay_bat_dau",
    "ngày bắt đầu": "ngay_bat_dau",
    "ngay bat dau": "ngay_bat_dau",
    "ngay_ket_thuc": "ngay_ket_thuc",
    "ngày kết thúc": "ngay_ket_thuc",
    "ngay ket thuc": "ngay_ket_thuc",
    "muc_nuoc_bat_dau": "muc_nuoc_bat_dau",
    "mực nước hồ từ": "muc_nuoc_bat_dau",
    "muc nuoc ho tu": "muc_nuoc_bat_dau",
    "muc_nuoc_ket_thuc": "muc_nuoc_ket_thuc",
    "mực nước hồ kết thúc": "muc_nuoc_ket_thuc",
    "muc nuoc ho ket thuc": "muc_nuoc_ket_thuc",
}


def normalize_excel_header(value):
    return str(value or "").strip().lower()


def parse_excel_month_day(value):
    if value in (None, "") or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.strftime("%d/%m")

    parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if not pd.isna(parsed):
        return parsed.strftime("%d/%m")

    for date_format in ("%d/%m", "%d-%m", "%d-%b", "%d-%B"):
        try:
            return datetime.strptime(str(value).strip(), date_format).strftime("%d/%m")
        except ValueError:
            continue
    return None


def parse_excel_float(value):
    if value in (None, "") or pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(" ", "")
        if value in {"", "-", "--", "nan", "NaN", "None"}:
            return None
        if "," in value and "." in value:
            if value.rfind(",") > value.rfind("."):
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", "")
        elif "," in value:
            value = value.replace(",", ".")
    return float(value)


class MucnuocQuytrinhViewSet(viewsets.ModelViewSet):
    serializer_class = MucnuocQuytrinhSerializer
    pagination_class = None
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Mặc định quy trình hồ chứa cho Sông Hinh
        if not user_can_access_plant(self.request.user, "songhinh"):
            raise PermissionDenied("Bạn không có quyền truy cập dữ liệu quy trình của nhà máy Sông Hinh.")

        queryset = MucnuocQuytrinh.objects.filter(nha_may="songhinh")
        ngay_bat_dau = self.request.query_params.get("ngay_bat_dau")
        ngay_ket_thuc = self.request.query_params.get("ngay_ket_thuc")
        if ngay_bat_dau:
            queryset = queryset.filter(ngay_ket_thuc__gte=ngay_bat_dau)
        if ngay_ket_thuc:
            queryset = queryset.filter(ngay_bat_dau__lte=ngay_ket_thuc)
        return queryset.order_by("ngay_bat_dau", "ngay_ket_thuc")

    def perform_create(self, serializer):
        if not user_can_access_plant(self.request.user, "songhinh"):
            raise PermissionDenied("Bạn không có quyền tạo dữ liệu quy trình của nhà máy Sông Hinh.")
        serializer.save(
            nha_may="songhinh",
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        obj = self.get_object()
        if not user_can_access_plant(self.request.user, "songhinh"):
            raise PermissionDenied("Bạn không có quyền cập nhật dữ liệu quy trình của nhà máy Sông Hinh.")
        if not user_can_modify_hydrology_object(self.request.user, obj):
            raise PermissionDenied("Ban chi duoc sua du lieu do chinh ban cap nhat.")
        
        save_kwargs = {"nha_may": "songhinh", "updated_by": self.request.user}
        if obj.created_by_id is None:
            save_kwargs["created_by"] = self.request.user
        serializer.save(**save_kwargs)

    def perform_destroy(self, instance):
        if not user_can_access_plant(self.request.user, "songhinh"):
            raise PermissionDenied("Bạn không có quyền xóa dữ liệu quy trình của nhà máy Sông Hinh.")
        if not user_can_modify_hydrology_object(self.request.user, instance):
            raise PermissionDenied("Ban chi duoc xoa du lieu do chinh ban cap nhat.")
        instance.delete()

    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        if not user_can_access_plant(request.user, "songhinh"):
            raise PermissionDenied("Bạn không có quyền export dữ liệu quy trình của nhà máy Sông Hinh.")

        rows = []
        for item in self.get_queryset():
            rows.append(
                {
                    "ngay_bat_dau": item.ngay_bat_dau,
                    "ngay_ket_thuc": item.ngay_ket_thuc,
                    "muc_nuoc_bat_dau": item.muc_nuoc_bat_dau,
                    "muc_nuoc_ket_thuc": item.muc_nuoc_ket_thuc,
                }
            )

        df = pd.DataFrame(rows, columns=MUCNUOC_QUYTRINH_EXPORT_COLUMNS.keys())
        df = df.rename(columns=MUCNUOC_QUYTRINH_EXPORT_COLUMNS)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Muc nuoc quy trinh")

        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            'attachment; filename="mucnuoc_quytrinh_songhinh.xlsx"'
        )
        return response

    @action(detail=False, methods=["post"], url_path="import-excel")
    def import_excel(self, request):
        if not user_can_access_plant(request.user, "songhinh"):
            raise PermissionDenied("Bạn không có quyền import dữ liệu quy trình của nhà máy Sông Hinh.")

        excel_file = request.FILES.get("file")
        if not excel_file:
            return Response(
                {"error": "Vui long chon file Excel voi field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            df = pd.read_excel(excel_file)
        except Exception as exc:
            return Response(
                {"error": f"Khong doc duoc file Excel: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_columns = {}
        for column in df.columns:
            key = normalize_excel_header(column)
            normalized_columns[column] = MUCNUOC_QUYTRINH_IMPORT_COLUMNS.get(key, key)
        df = df.rename(columns=normalized_columns)

        required_fields = (
            "ngay_bat_dau",
            "ngay_ket_thuc",
            "muc_nuoc_bat_dau",
            "muc_nuoc_ket_thuc",
        )
        missing_fields = [field for field in required_fields if field not in df.columns]
        if missing_fields:
            return Response(
                {"error": "Thieu cot bat buoc: " + ", ".join(missing_fields)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        imported_count = 0
        updated_count = 0
        errors = []

        for index, row in df.iterrows():
            row_number = index + 2
            if all(pd.isna(row.get(field)) for field in required_fields):
                continue

            try:
                ngay_bat_dau = parse_excel_month_day(row.get("ngay_bat_dau"))
                ngay_ket_thuc = parse_excel_month_day(row.get("ngay_ket_thuc"))
                muc_nuoc_bat_dau = parse_excel_float(row.get("muc_nuoc_bat_dau"))
                muc_nuoc_ket_thuc = parse_excel_float(row.get("muc_nuoc_ket_thuc"))

                if not ngay_bat_dau or not ngay_ket_thuc:
                    raise ValueError("Ngay bat dau/ngay ket thuc khong hop le")
                if muc_nuoc_bat_dau is None or muc_nuoc_ket_thuc is None:
                    raise ValueError("Muc nuoc bat dau/ket thuc khong hop le")

                obj, created = MucnuocQuytrinh.objects.get_or_create(
                    nha_may="songhinh",
                    ngay_bat_dau=ngay_bat_dau,
                    ngay_ket_thuc=ngay_ket_thuc,
                    defaults={"created_by": request.user},
                )
                obj.muc_nuoc_bat_dau = muc_nuoc_bat_dau
                obj.muc_nuoc_ket_thuc = muc_nuoc_ket_thuc
                obj.updated_by = request.user
                if obj.created_by_id is None:
                    obj.created_by = request.user
                obj.save()
                if created:
                    imported_count += 1
                else:
                    updated_count += 1
            except Exception as exc:
                errors.append({"row": row_number, "error": str(exc)})

        response_status = (
            status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        )
        return Response(
            {
                "message": "Import Excel muc nuoc quy trinh hoan tat",
                "imported_count": imported_count,
                "updated_count": updated_count,
                "errors": errors,
            },
            status=response_status,
        )
