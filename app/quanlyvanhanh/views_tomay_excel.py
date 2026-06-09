import io
import pandas as pd
from datetime import datetime, time
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from core.factory_scope import (
    filter_queryset_by_factory,
    get_user_factory_name,
    get_user_factory_code,
    has_profile_permission,
)
from .models import ThietBi, ThongSoToMay
from .services.thongso_tomay_service import get_specific_thiet_bi


def _excel_template_tomay(request, device_type):
    """Logic cốt lõi tạo template Excel cho thông số tổ máy H1 hoặc H2"""
    try:
        # Tạo 24 chu kỳ từ 00:00 đến 23:00 (mỗi giờ)
        time_cycles = []
        for hour in range(24):
            time_cycles.append(time(hour, 0).strftime("%H:%M"))

        # Định nghĩa các thông số tổ máy theo hình
        thong_so_to_may = [
            {"ten": "Áp lực nước", "ma": "ap_luc_nuoc", "don_vi": "bar"},
            {"ten": "Áp lực chèn trục", "ma": "ap_luc_chen_truc", "don_vi": "bar"},
            {"ten": "Lưu lượng chèn trục", "ma": "luu_luong_chen_truc", "don_vi": "l/p"},
            {"ten": "Lưu lượng ổ hướng tuabin", "ma": "luu_luong_o_huong_tuabin", "don_vi": "l/p"},
            {"ten": "Nhiệt độ ổ hướng tuabin", "ma": "nhiet_do_o_huong_tuabin", "don_vi": "°C"},
            {"ten": "Lưu lượng ổ hướng máy phát", "ma": "luu_luong_o_huong_may_phat", "don_vi": "l/p"},
            {"ten": "Nhiệt độ ổ hướng máy phát", "ma": "nhiet_do_o_huong_may_phat", "don_vi": "°C"},
            {"ten": "Lưu lượng ổ đỡ máy phát", "ma": "luu_luong_o_do_may_phat", "don_vi": "l/p"},
            {"ten": "Nhiệt độ ổ đỡ", "ma": "nhiet_do_o_do", "don_vi": "°C"},
            {"ten": "Nhiệt độ ổ hướng - ổ đỡ", "ma": "nhiet_do_o_huong_o_do", "don_vi": "°C"},
            {"ten": "Nhiệt độ đầu ổ đỡ", "ma": "nhiet_do_dau_o_do", "don_vi": "°C"},
            {"ten": "Lưu lượng làm mát máy phát", "ma": "luu_luong_lam_mat_may_phat", "don_vi": "l/p"},
            {"ten": "Nhiệt độ nước làm mát máy phát", "ma": "nhiet_do_nuoc_lam_mat_may_phat", "don_vi": "°C"},
            {"ten": "Nhiệt độ khí mát", "ma": "nhiet_do_khi_mat", "don_vi": "°C"},
            {"ten": "Nhiệt độ khí nóng", "ma": "nhiet_do_khi_nong", "don_vi": "°C"},
            {"ten": "Nhiệt độ cuộn dây stato", "ma": "nhiet_do_cuon_day_stato", "don_vi": "°C"},
            {"ten": "Tốc độ", "ma": "toc_do", "don_vi": "v/ph"},
            {"ten": "Giới hạn độ mở cánh hướng", "ma": "gioi_han_do_mo_canh_huong", "don_vi": "%"},
            {"ten": "Độ mở cánh hướng", "ma": "do_mo_canh_huong", "don_vi": "%"},
            {"ten": "Độ rơi tốc", "ma": "do_roi_toc", "don_vi": "%"},
        ]

        # Tạo DataFrame
        data = []

        # Header rows
        header_row1 = [f"THÔNG SỐ {device_type}"] + [""] * (len(thong_so_to_may) - 1)  # A1:T1
        header_row2 = [ts["ten"] for ts in thong_so_to_may]  # A2:T2
        header_row3 = [ts["don_vi"] for ts in thong_so_to_may]  # A3:T3

        data.append(header_row1)
        data.append(header_row2)
        data.append(header_row3)

        # Data rows (24 chu kỳ)
        for i in range(len(time_cycles)):
            row = ["-"] * len(thong_so_to_may)
            data.append(row)

        df = pd.DataFrame(data)

        # Tạo Excel file
        output = io.BytesIO()
        sheet_name = f"Thông số {device_type}"
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)

            # Lấy workbook và worksheet để format
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            # Merge cells cho header
            from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

            worksheet.merge_cells("A1:T1")

            # Style cho header
            header_font = Font(bold=True, size=14)
            header_fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")  # Light green
            header_alignment = Alignment(horizontal="center", vertical="center")

            # Apply style to A1
            worksheet["A1"].font = header_font
            worksheet["A1"].fill = header_fill
            worksheet["A1"].alignment = header_alignment

            # Style cho row 2 (tên thông số)
            for col in range(1, len(thong_so_to_may) + 1):
                cell = worksheet.cell(row=2, column=col)
                cell.font = Font(bold=True, size=12)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")

            # Style cho row 3 (đơn vị)
            for col in range(1, len(thong_so_to_may) + 1):
                cell = worksheet.cell(row=3, column=col)
                cell.font = Font(size=10)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")

            # Style cho time column (A) - để trống
            for row in range(4, 28):
                cell = worksheet.cell(row=row, column=1)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center", vertical="center")

            # Set column widths
            worksheet.column_dimensions["A"].width = 12
            for col in range(1, len(thong_so_to_may) + 1):
                worksheet.column_dimensions[chr(64 + col)].width = 15

            # Add borders
            thin_border = Border(
                left=Side(style="thin"),
                right=Side(style="thin"),
                top=Side(style="thin"),
                bottom=Side(style="thin"),
            )

            for row in range(1, 28):
                for col in range(1, len(thong_so_to_may) + 1):
                    worksheet.cell(row=row, column=col).border = thin_border

        file_content = output.getvalue()

        # Giữ tính tương thích tên file cũ
        filename = "ThongSoToMay_Template.xlsx" if device_type == "H1" else "ThongSoToMayH2_Template.xlsx"

        response = HttpResponse(
            file_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type"

        return response

    except Exception as e:
        return HttpResponse(f"Lỗi khi tạo template: {str(e)}", status=500)


def _import_excel_tomay(request, device_type=None):
    """Logic cốt lõi import dữ liệu từ Excel cho thông số tổ máy H1/H2"""
    try:
        excel_file = request.FILES.get("file")
        if not excel_file:
            return HttpResponse("Không có file Excel", status=400)

        request_data = getattr(request, "data", request.POST)
        selected_date = request_data.get("selected_date")
        if not selected_date:
            return HttpResponse("Không có ngày được chọn", status=400)

        try:
            target_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            return HttpResponse("Định dạng ngày không hợp lệ", status=400)

        df = pd.read_excel(excel_file, header=None)

        # Validation cơ bản
        if len(df) < 3:
            return JsonResponse(
                {
                    "error": (
                        f"File Excel không hợp lệ: File phải có ít nhất 3 hàng header. "
                        f"File hiện tại có {len(df)} hàng."
                    ),
                    "status": "error",
                    "expected_rows": 3,
                    "actual_rows": len(df),
                },
                status=400,
            )

        if len(df.columns) < 20:
            return JsonResponse(
                {
                    "error": (
                        f"File Excel không hợp lệ: File thông số tổ máy phải có ít nhất 20 cột (A đến T). "
                        f"File hiện tại có {len(df.columns)} cột."
                    ),
                    "status": "error",
                    "expected_columns": 20,
                    "actual_columns": len(df.columns),
                },
                status=400,
            )

        # Đọc A1 để xác định H1 hay H2
        header_row1 = df.iloc[0, 0] if len(df) > 0 and len(df.columns) > 0 else None
        if pd.isna(header_row1) or not isinstance(header_row1, str):
            header_row1 = ""

        header_row1_upper = str(header_row1).upper()
        if "VẬN HÀNH" in header_row1_upper:
            return JsonResponse(
                {
                    "error": (
                        "File Excel không hợp lệ: Đây là file Thông số Vận hành, không phải file Thông số Tổ máy. "
                        "Vui lòng sử dụng file template Thông số Tổ máy."
                    ),
                    "status": "error",
                    "detected_type": "thong_so_van_hanh",
                },
                status=400,
            )

        # Nhận diện tổ máy từ A1
        detected_type = None
        if "H1" in header_row1_upper:
            detected_type = "H1"
        elif "H2" in header_row1_upper:
            detected_type = "H2"

        if not detected_type:
            return JsonResponse(
                {
                    "error": (
                        f'File Excel không hợp lệ: Tiêu đề ô A1 phải chứa "H1" hoặc "H2". '
                        f'Giá trị hiện tại: "{header_row1}".'
                    ),
                    "status": "error",
                },
                status=400,
            )

        # Kiểm tra device_type từ wrapper nếu được chỉ định
        if device_type and detected_type != device_type:
            return JsonResponse(
                {
                    "error": (
                        f"File Excel tải lên ({detected_type}) không khớp với "
                        f"tổ máy được chọn trên giao diện ({device_type})."
                    ),
                    "status": "error",
                },
                status=400,
            )

        # Kiểm tra tham số device_code từ client gửi lên nếu có (Cross-Validation)
        factory_code = get_user_factory_code(request.user) or "SH"
        device_code = request_data.get("device_code")

        if device_code:
            # Xác định expected_type từ device_code
            if ".H1." in device_code:
                expected_type = "H1"
            elif ".H2." in device_code:
                expected_type = "H2"
            else:
                expected_type = None

            if expected_type and detected_type != expected_type:
                return JsonResponse(
                    {
                        "error": (
                            f"File Excel tải lên ({detected_type}) không khớp với "
                            f"tổ máy được chọn trên giao diện ({expected_type})."
                        ),
                        "status": "error",
                    },
                    status=400,
                )
        else:
            # Nếu client không truyền device_code, tự tạo dựa vào detected_type
            device_code = f"{factory_code}.TB.{detected_type}.GE"

        # Tên các thông số mong đợi
        expected_params = [
            "Áp lực nước",
            "Áp lực chèn trục",
            "Lưu lượng chèn trục",
            "Lưu lượng ổ hướng tuabin",
            "Nhiệt độ ổ hướng tuabin",
            "Lưu lượng ổ hướng máy phát",
            "Nhiệt độ ổ hướng máy phát",
            "Lưu lượng ổ đỡ máy phát",
            "Nhiệt độ ổ đỡ",
            "Nhiệt độ ổ hướng - ổ đỡ",
            "Nhiệt độ đầu ổ đỡ",
            "Lưu lượng làm mát máy phát",
            "Nhiệt độ nước làm mát máy phát",
            "Nhiệt độ khí mát",
            "Nhiệt độ khí nóng",
            "Nhiệt độ cuộn dây stato",
            "Tốc độ",
            "Giới hạn độ mở cánh hướng",
            "Độ mở cánh hướng",
            "Độ rơi tốc",
        ]

        header_row2 = df.iloc[1, :20].fillna("").astype(str).tolist()

        # Kiểm tra từng cột
        missing_params = []
        for idx, expected_param in enumerate(expected_params):
            if idx >= len(header_row2):
                missing_params.append(f'Cột {chr(65 + idx)}: Thiếu "{expected_param}"')
                continue

            actual_value = str(header_row2[idx]).strip()
            if not actual_value:
                missing_params.append(f'Cột {chr(65 + idx)}: Trống, mong đợi "{expected_param}"')
                continue

            expected_normalized = " ".join(expected_param.lower().strip().split())
            actual_normalized = " ".join(actual_value.lower().strip().split())

            if expected_normalized == actual_normalized or expected_normalized in actual_normalized or actual_normalized in expected_normalized:
                continue

            # Fuzzy matching: Cho phép lỗi đánh máy nhỏ (ví dụ: "đầu" vs "dầu") hoặc không dấu
            expected_words = expected_normalized.split()
            actual_words = actual_normalized.split()

            def simple_edit_distance(word1, word2):
                if abs(len(word1) - len(word2)) > 2:
                    return float('inf')
                if word1 == word2:
                    return 0
                min_len = min(len(word1), len(word2))
                max_len = max(len(word1), len(word2))
                diff = 0
                for i in range(min_len):
                    if word1[i] != word2[i]:
                        diff += 1
                diff += (max_len - min_len)
                return diff

            words_match = 0
            total_words = len(expected_words)
            if total_words > 0:
                for exp_word in expected_words:
                    best_match = min(
                        [simple_edit_distance(exp_word, act_word) for act_word in actual_words],
                        default=float('inf')
                    )
                    if best_match <= 2:
                        words_match += 1
                if words_match / total_words >= 0.8:
                    continue

            missing_params.append(f'Cột {chr(65 + idx)}: Mong đợi "{expected_param}" nhưng có "{actual_value}"')

        if missing_params:
            return JsonResponse(
                {
                    "error": (
                        f"File Excel không hợp lệ: Các cột không khớp với template {detected_type}.\n"
                        + "\n".join(missing_params[:5])
                        + (f"\n... và {len(missing_params) - 5} cột khác" if len(missing_params) > 5 else "")
                    ),
                    "status": "error",
                    "missing_params": missing_params[:10],
                },
                status=400,
            )

        data_row_count = len(df) - 3
        if data_row_count >= 48:
            return JsonResponse(
                {
                    "error": (
                        f"File Excel không hợp lệ: File có {data_row_count} hàng dữ liệu (>48). "
                        f"Có thể đây là file Thông số Vận hành điện (48 slots). Vui lòng sử dụng template tổ máy."
                    ),
                    "status": "error",
                    "suggestion": "Có thể bạn đang import nhầm file Thông số Vận hành",
                },
                status=400,
            )

        # Lấy thiết bị gốc
        try:
            thiet_bi = filter_queryset_by_factory(
                ThietBi.objects.all(),
                request.user,
                "nha_may",
                "string",
            ).get(ma_day_du=device_code)
        except ThietBi.DoesNotExist:
            return HttpResponse(f"Không tìm thấy thiết bị gốc {device_code} trong quyền hạn", status=400)

        # Cấu trúc cột
        column_mapping = {
            i: {"ten": p, "ma": m, "don_vi": d}
            for i, (p, m, d) in enumerate(
                [
                    ("Áp lực nước", "ap_luc_nuoc", "bar"),
                    ("Áp lực chèn trục", "ap_luc_chen_truc", "bar"),
                    ("Lưu lượng chèn trục", "luu_luong_chen_truc", "l/p"),
                    ("Lưu lượng ổ hướng tuabin", "luu_luong_o_huong_tuabin", "l/p"),
                    ("Nhiệt độ ổ hướng tuabin", "nhiet_do_o_huong_tuabin", "°C"),
                    ("Lưu lượng ổ hướng máy phát", "luu_luong_o_huong_may_phat", "l/p"),
                    ("Nhiệt độ ổ hướng máy phát", "nhiet_do_o_huong_may_phat", "°C"),
                    ("Lưu lượng ổ đỡ máy phát", "luu_luong_o_do_may_phat", "l/p"),
                    ("Nhiệt độ ổ đỡ", "nhiet_do_o_do", "°C"),
                    ("Nhiệt độ ổ hướng - ổ đỡ", "nhiet_do_o_huong_o_do", "°C"),
                    ("Nhiệt độ đầu ổ đỡ", "nhiet_do_dau_o_do", "°C"),
                    ("Lưu lượng làm mát máy phát", "luu_luong_lam_mat_may_phat", "l/p"),
                    ("Nhiệt độ nước làm mát máy phát", "nhiet_do_nuoc_lam_mat_may_phat", "°C"),
                    ("Nhiệt độ khí mát", "nhiet_do_khi_mat", "°C"),
                    ("Nhiệt độ khí nóng", "nhiet_do_khi_nong", "°C"),
                    ("Nhiệt độ cuộn dây stato", "nhiet_do_cuon_day_stato", "°C"),
                    ("Tốc độ", "toc_do", "v/ph"),
                    ("Giới hạn độ mở cánh hướng", "gioi_han_do_mo_canh_huong", "%"),
                    ("Độ mở cánh hướng", "do_mo_canh_huong", "%"),
                    ("Độ rơi tốc", "do_roi_toc", "%"),
                ]
            )
        }

        # 24 chu kỳ
        import pytz

        vietnam_tz = pytz.timezone("Asia/Ho_Chi_Minh")
        time_cycles = []
        for hour in range(24):
            naive_dt = datetime.combine(target_date, time(hour, 0))
            time_cycles.append(vietnam_tz.localize(naive_dt))

        imported_count = 0

        # Lấy trước các bản ghi hiện có
        prefix = ".".join(thiet_bi.ma_day_du.split(".")[:3])  # E.g., "SH.TB.H1" hoặc "SH.TB.H2"
        existing_records = ThongSoToMay.objects.filter(
            thiet_bi__ma_day_du__startswith=prefix, ngay_nhap=target_date
        )
        existing_lookup = {
            (rec.ten_thong_so, rec.thoi_diem_nhap): rec for rec in existing_records
        }

        to_create = []
        to_update = []

        # Xử lý A4 đến T27
        for row_idx in range(3, 27):
            time_cycle = time_cycles[row_idx - 3] if row_idx - 3 < len(time_cycles) else None
            if not time_cycle:
                continue

            for col_idx in range(0, 20):
                if col_idx not in column_mapping:
                    continue

                mapping = column_mapping[col_idx]
                value = df.iloc[row_idx, col_idx] if row_idx < len(df) else None

                if pd.isna(value) or value == "" or value == "-":
                    numeric_value = None
                else:
                    try:
                        numeric_value = float(value)
                    except (ValueError, TypeError):
                        numeric_value = None

                try:
                    nha_may_val = get_user_factory_name(request.user) or thiet_bi.nha_may
                    lookup_key = (mapping["ten"], time_cycle)

                    target_tb = get_specific_thiet_bi(thiet_bi, mapping["ma"])

                    if lookup_key in existing_lookup:
                        obj = existing_lookup[lookup_key]
                        if obj.gia_tri != numeric_value or obj.nha_may != nha_may_val or obj.thiet_bi_id != target_tb.id:
                            obj.gia_tri = numeric_value
                            obj.nha_may = nha_may_val
                            obj.thiet_bi = target_tb
                            to_update.append(obj)
                    else:
                        obj = ThongSoToMay(
                            thiet_bi=target_tb,
                            ten_thong_so=mapping["ten"],
                            thoi_diem_nhap=time_cycle,
                            ngay_nhap=target_date,
                            ma_thong_so=mapping["ma"],
                            don_vi=mapping["don_vi"],
                            gia_tri=numeric_value,
                            nha_may=nha_may_val,
                            ky_hieu_van_hanh=f'{device_code.split(".")[-2]}_{mapping["ma"]}',
                            ghi_chu=f"Import từ Excel - {target_date}",
                        )
                        to_create.append(obj)
                        existing_lookup[lookup_key] = obj

                    imported_count += 1
                except Exception:
                    continue

        if to_create:
            ThongSoToMay.objects.bulk_create(to_create)
        if to_update:
            ThongSoToMay.objects.bulk_update(to_update, ["gia_tri", "nha_may", "thiet_bi"])

        return JsonResponse(
            {
                "message": f"Import thành công {imported_count} bản ghi thông số tổ máy {detected_type}",
                "imported_count": imported_count,
                "status": "success",
            },
            status=200,
        )

    except Exception as e:
        return JsonResponse({"error": f"Lỗi khi import: {str(e)}", "status": "error"}, status=500)


# ==========================================
# PUBLIC API ENDPOINTS (DECORATED WITH DRF)
# ==========================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def excel_template_tomay(request):
    """Tạo template Excel chung cho H1/H2, nhận diện qua param ?type=H1|H2"""
    if not has_profile_permission(request.user, "can_export_excel"):
        return JsonResponse(
            {
                "error": (
                    "Tài khoản của bạn chưa được cấp quyền xuất dữ liệu "
                    "hoặc tải template Excel. Vui lòng liên hệ quản trị viên."
                )
            },
            status=403,
        )
    device_type = request.query_params.get("type", "H1").upper()
    if device_type not in ["H1", "H2"]:
        return JsonResponse(
            {"error": "Tổ máy không hợp lệ (chỉ hỗ trợ H1 hoặc H2)"},
            status=400,
        )
    return _excel_template_tomay(request, device_type)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def excel_template_h1(request):
    """Wrapper tương thích ngược cho template H1"""
    if not has_profile_permission(request.user, "can_export_excel"):
        return JsonResponse(
            {
                "error": (
                    "Tài khoản của bạn chưa được cấp quyền xuất dữ liệu "
                    "hoặc tải template Excel. Vui lòng liên hệ quản trị viên."
                )
            },
            status=403,
        )
    return _excel_template_tomay(request, "H1")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def excel_template_h2(request):
    """Wrapper tương thích ngược cho template H2"""
    if not has_profile_permission(request.user, "can_export_excel"):
        return JsonResponse(
            {
                "error": (
                    "Tài khoản của bạn chưa được cấp quyền xuất dữ liệu "
                    "hoặc tải template Excel. Vui lòng liên hệ quản trị viên."
                )
            },
            status=403,
        )
    return _excel_template_tomay(request, "H2")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_excel_tomay(request):
    """Import dữ liệu từ Excel cho thông số tổ máy (Tự động nhận diện H1/H2)"""
    if not has_profile_permission(request.user, "can_import_excel"):
        return JsonResponse(
            {
                "error": (
                    "Tài khoản của bạn chưa được cấp quyền import dữ liệu từ Excel. "
                    "Vui lòng liên hệ quản trị viên."
                )
            },
            status=403,
        )
    return _import_excel_tomay(request)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_excel_h1(request):
    """Wrapper tương thích ngược cho import H1"""
    if not has_profile_permission(request.user, "can_import_excel"):
        return JsonResponse(
            {
                "error": (
                    "Tài khoản của bạn chưa được cấp quyền import dữ liệu từ Excel. "
                    "Vui lòng liên hệ quản trị viên."
                )
            },
            status=403,
        )
    return _import_excel_tomay(request, device_type="H1")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def import_excel_h2(request):
    """Wrapper tương thích ngược cho import H2"""
    if not has_profile_permission(request.user, "can_import_excel"):
        return JsonResponse(
            {
                "error": (
                    "Tài khoản của bạn chưa được cấp quyền import dữ liệu từ Excel. "
                    "Vui lòng liên hệ quản trị viên."
                )
            },
            status=403,
        )
    return _import_excel_tomay(request, device_type="H2")
