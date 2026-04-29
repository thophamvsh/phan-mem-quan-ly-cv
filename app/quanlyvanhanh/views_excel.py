import os
import io
from django.http import HttpResponse, JsonResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
import pandas as pd
from datetime import datetime
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from core.factory_scope import filter_queryset_by_factory, get_user_factory_name
from .models import ThongSoVanHanh, ThietBi


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def excel_template(request):
    """
    Tạo template Excel cho thông số vận hành điện
    """
    try:
        # Tạo workbook mới
        wb = Workbook()
        ws = wb.active
        ws.title = "ThongSoVanHanhDien"

        # Tạo header 3 tầng
        # Tầng 1: Tên thiết bị (không bao gồm cột "Ngày" và "Thời điểm")
        device_headers = [
            # TỔ MÁY H1 (7 thông số)
            "TỔ MÁY H1", "", "", "", "", "", "",
            # TỔ MÁY H2 (7 thông số)
            "TỔ MÁY H2", "", "", "", "", "", "",
            # TRẠM PHÂN PHỐI (19 thông số)
            "TRẠM PHÂN PHỐI", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
        ]

        # Tầng 2: Tên thông số
        parameter_headers = [
            # TỔ MÁY H1 (7 thông số)
            "Điện áp kích từ", "Dòng điện kích từ", "Điện áp", "Dòng điện",
            "Công suất tác dụng", "Công suất phản kháng", "Tần số",
            # TỔ MÁY H2 (7 thông số)
            "Điện áp kích từ", "Dòng điện kích từ", "Điện áp", "Dòng điện",
            "Công suất tác dụng", "Công suất phản kháng", "Tần số",
            # TRẠM PHÂN PHỐI (19 thông số)
            "Tổng P máy phát", "Tổng Q máy phát", "Điện áp ĐZ 172", "Dòng điện ĐZ 172",
            "Công suất tác dụng ĐZ 172", "Công suất phản kháng ĐZ 172", "Điện áp ĐZ 174",
            "Dòng điện ĐZ 174", "Công suất tác dụng ĐZ 174", "Công suất phản kháng ĐZ 174",
            "Điện áp ĐZ 471", "Dòng điện ĐZ 471", "Công suất tác dụng ĐZ 471",
            "Công suất phản kháng ĐZ 471", "Điện áp ĐZ 472", "Dòng điện ĐZ 472",
            "Công suất tác dụng ĐZ 472", "Công suất phản kháng ĐZ 472", "Tổng P 22kV"
        ]

        # Tầng 3: Đơn vị
        unit_headers = [
            # TỔ MÁY H1 (7 thông số)
            "V", "A", "kV", "A", "MW", "MVar", "Hz",
            # TỔ MÁY H2 (7 thông số)
            "V", "A", "kV", "A", "MW", "MVar", "Hz",
            # TRẠM PHÂN PHỐI (19 thông số)
            "MW", "MVar", "kV", "A", "MW", "MVar", "kV", "A", "MW", "MVar",
            "kV", "A", "MW", "MVar", "kV", "A", "MW", "MVar", "MW"
        ]

        # Tạo header row 1: Tên thiết bị
        for col, header in enumerate(device_headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
            cell.fill = PatternFill(start_color='90EE90', end_color='90EE90', fill_type='solid')

        # Tạo header row 2: Tên thông số
        for col, header in enumerate(parameter_headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
            cell.fill = PatternFill(start_color='87CEEB', end_color='87CEEB', fill_type='solid')

        # Tạo header row 3: Đơn vị
        for col, header in enumerate(unit_headers, 1):
            cell = ws.cell(row=3, column=col, value=header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center')
            cell.fill = PatternFill(start_color='DDA0DD', end_color='DDA0DD', fill_type='solid')

        # Tạo dữ liệu mẫu cho 48 chu kỳ (00:00 - 23:30) - KHÔNG có Min/Max
        from datetime import datetime, timedelta

        current_date = datetime.now()

        # Tạo 48 chu kỳ (00:30 - 24:00) - chỉ có thông số, không có cột Ngày và Thời điểm
        row_index = 4  # Bắt đầu từ hàng 4 (sau 3 hàng header)

        # Tạo đúng 48 dòng từ 00:00 đến 23:30
        slots = []
        for hour in range(24):
            # Mỗi giờ có 2 slot: XX:00 và XX:30
            slots.append(f"{hour:02d}:00")
            slots.append(f"{hour:02d}:30")

        # Đảm bảo có đúng 48 slots
        if len(slots) != 48:
            if len(slots) == 47:
                slots.append("23:30")

        # Tạo 48 dòng dữ liệu
        for slot in slots:
            for col in range(1, 34):  # 33 thông số
                ws.cell(row=row_index, column=col, value="")
            row_index += 1

        # Điều chỉnh độ rộng cột cho 33 thông số (không có cột Ngày và Thời điểm)
        column_widths = [15] * 33  # 33 thông số
        for i, width in enumerate(column_widths, 1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

        # Tạo response với buffer
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="ThongSoVanHanhDien_Template.xlsx"'
        response['Content-Length'] = len(buffer.getvalue())

        return response

    except Exception as e:
        import traceback
        error_msg = f"Lỗi tạo template Excel: {str(e)}\n{traceback.format_exc()}"
        return JsonResponse({'error': error_msg}, status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def excel_import(request):
    """
    Import dữ liệu từ file Excel
    """
    try:
        if 'file' not in request.FILES:
            return JsonResponse({'error': 'Không có file được upload'}, status=400)

        file = request.FILES['file']

        # Lấy ngày và thời điểm từ form
        request_data = getattr(request, "data", request.POST)
        import_date = request_data.get('selected_date')
        time_slots_json = request_data.get('time_slots', '[]')

        if not import_date:
            return JsonResponse({'error': 'Vui lòng chọn ngày import'}, status=400)

        # Parse time slots
        import json
        try:
            time_slots = json.loads(time_slots_json)
        except:
            time_slots = []

        # Tạo time cycles list trước khi đọc Excel
        if time_slots:
            time_cycles_list = [slot['time'] for slot in time_slots if slot.get('selected', True)]
        else:
            # Tạo thời điểm mặc định cho 48 chu kỳ (00:00 đến 23:30)
            time_cycles_list = []
            # 00:00 → 23:30 (48 slot) - backend đồng bộ với frontend
            for hour in range(24):
                # Mỗi giờ có 2 slot: XX:00 và XX:30
                time_cycles_list.append(f"{hour:02d}:00")
                time_cycles_list.append(f"{hour:02d}:30")

            # Đảm bảo có đúng 48 slots
            if len(time_cycles_list) != 48:
                if len(time_cycles_list) == 47:
                    time_cycles_list.append("23:30")

            # Đảm bảo chỉ có 48 slot
            time_cycles_list = time_cycles_list[:48]

        # Đọc file Excel: Template có 3 hàng header (row 1-3), dữ liệu bắt đầu từ hàng 4
        try:
            df = pd.read_excel(
                file,
                header=None,     # không lấy hàng đầu làm header
                skiprows=3,      # bỏ 3 hàng header, bắt đầu từ hàng 4 (A4)
                nrows=48,        # chỉ đọc 48 chu kỳ (A4-A51)
                usecols=list(range(0, 33)),  # 33 cột thông số (A-AG)
                engine="openpyxl",
            )
        except Exception as e:
            # Log error internally without printing
            return JsonResponse({'error': f'Lỗi đọc file Excel: {str(e)}'}, status=400)

        # Lấy dữ liệu từ các cột cụ thể (48 giờ, chỉ lấy 24 giờ đầu)
        imported_count = 0

        # Mapping cột Excel với thông số và thiết bị (33 thông số)
        # Dựa trên vị trí cột trong Excel (A=0, B=1, C=2, ...)
        column_mapping = [
            # TỔ MÁY H1 (7 thông số đầu - cột A-G)
            {'name': 'Điện áp kích từ', 'device': 'SH.TB.H1', 'field': 'dien_ap_kich_tu_h1', 'unit': 'V'},
            {'name': 'Dòng điện kích từ', 'device': 'SH.TB.H1', 'field': 'dong_dien_kich_tu_h1', 'unit': 'A'},
            {'name': 'Điện áp', 'device': 'SH.TB.H1', 'field': 'dien_ap_h1', 'unit': 'kV'},
            {'name': 'Dòng điện', 'device': 'SH.TB.H1', 'field': 'dong_dien_h1', 'unit': 'A'},
            {'name': 'Công suất tác dụng', 'device': 'SH.TB.H1', 'field': 'cong_suat_tac_dung_h1', 'unit': 'MW'},
            {'name': 'Công suất phản kháng', 'device': 'SH.TB.H1', 'field': 'cong_suat_phan_khang_h1', 'unit': 'MVar'},
            {'name': 'Tần số', 'device': 'SH.TB.H1', 'field': 'tan_so_h1', 'unit': 'Hz'},
            # TỔ MÁY H2 (7 thông số tiếp theo - cột H-N)
            {'name': 'Điện áp kích từ', 'device': 'SH.TB.H2', 'field': 'dien_ap_kich_tu_h2', 'unit': 'V'},
            {'name': 'Dòng điện kích từ', 'device': 'SH.TB.H2', 'field': 'dong_dien_kich_tu_h2', 'unit': 'A'},
            {'name': 'Điện áp', 'device': 'SH.TB.H2', 'field': 'dien_ap_h2', 'unit': 'kV'},
            {'name': 'Dòng điện', 'device': 'SH.TB.H2', 'field': 'dong_dien_h2', 'unit': 'A'},
            {'name': 'Công suất tác dụng', 'device': 'SH.TB.H2', 'field': 'cong_suat_tac_dung_h2', 'unit': 'MW'},
            {'name': 'Công suất phản kháng', 'device': 'SH.TB.H2', 'field': 'cong_suat_phan_khang_h2', 'unit': 'MVar'},
            {'name': 'Tần số', 'device': 'SH.TB.H2', 'field': 'tan_so_h2', 'unit': 'Hz'},
            # TRẠM PHÂN PHỐI (19 thông số cuối - cột O-AG)
            {'name': 'Tổng P máy phát', 'device': 'SH.TB.TPP', 'field': 'tong_p_may_phat', 'unit': 'MW'},
            {'name': 'Tổng Q máy phát', 'device': 'SH.TB.TPP', 'field': 'tong_q_may_phat', 'unit': 'MVar'},
            {'name': 'Điện áp ĐZ 172', 'device': 'SH.TB.TPP', 'field': 'dien_ap_172', 'unit': 'kV'},
            {'name': 'Dòng điện ĐZ 172', 'device': 'SH.TB.TPP', 'field': 'dong_dien_172', 'unit': 'A'},
            {'name': 'Công suất tác dụng ĐZ 172', 'device': 'SH.TB.TPP', 'field': 'cong_suat_tac_dung_172', 'unit': 'MW'},
            {'name': 'Công suất phản kháng ĐZ 172', 'device': 'SH.TB.TPP', 'field': 'cong_suat_phan_khang_172', 'unit': 'MVar'},
            {'name': 'Điện áp ĐZ 174', 'device': 'SH.TB.TPP', 'field': 'dien_ap_174', 'unit': 'kV'},
            {'name': 'Dòng điện ĐZ 174', 'device': 'SH.TB.TPP', 'field': 'dong_dien_174', 'unit': 'A'},
            {'name': 'Công suất tác dụng ĐZ 174', 'device': 'SH.TB.TPP', 'field': 'cong_suat_tac_dung_174', 'unit': 'MW'},
            {'name': 'Công suất phản kháng ĐZ 174', 'device': 'SH.TB.TPP', 'field': 'cong_suat_phan_khang_174', 'unit': 'MVar'},
            {'name': 'Điện áp ĐZ 471', 'device': 'SH.TB.TPP', 'field': 'dien_ap_471', 'unit': 'kV'},
            {'name': 'Dòng điện ĐZ 471', 'device': 'SH.TB.TPP', 'field': 'dong_dien_471', 'unit': 'A'},
            {'name': 'Công suất tác dụng ĐZ 471', 'device': 'SH.TB.TPP', 'field': 'cong_suat_tac_dung_471', 'unit': 'MW'},
            {'name': 'Công suất phản kháng ĐZ 471', 'device': 'SH.TB.TPP', 'field': 'cong_suat_phan_khang_471', 'unit': 'MVar'},
            {'name': 'Điện áp ĐZ 472', 'device': 'SH.TB.TPP', 'field': 'dien_ap_472', 'unit': 'kV'},
            {'name': 'Dòng điện ĐZ 472', 'device': 'SH.TB.TPP', 'field': 'dong_dien_472', 'unit': 'A'},
            {'name': 'Công suất tác dụng ĐZ 472', 'device': 'SH.TB.TPP', 'field': 'cong_suat_tac_dung_472', 'unit': 'MW'},
            {'name': 'Công suất phản kháng ĐZ 472', 'device': 'SH.TB.TPP', 'field': 'cong_suat_phan_khang_472', 'unit': 'MVar'},
            {'name': 'Tổng P 22kV', 'device': 'SH.TB.TPP', 'field': 'tong_p_22kv', 'unit': 'MW'}
        ]

        # Lấy danh sách thiết bị cần thiết
        # Tìm hoặc tạo thiết bị theo mã
        thiet_bi_map = {}
        device_names = {
            'SH.TB.H1': 'Tổ máy H1',
            'SH.TB.H2': 'Tổ máy H2',
            'SH.TB.TPP': 'Trạm phân phối'
        }
        scoped_thiet_bi = filter_queryset_by_factory(
            ThietBi.objects.all(),
            request.user,
            'nha_may',
            'string',
        )

        for ma_thiet_bi in ['SH.TB.H1', 'SH.TB.H2', 'SH.TB.TPP']:
            try:
                thiet_bi = scoped_thiet_bi.get(ma_day_du=ma_thiet_bi)
                thiet_bi_map[ma_thiet_bi] = thiet_bi
            except ThietBi.DoesNotExist:
                continue

        if not thiet_bi_map:
            return JsonResponse({'error': 'Không tìm thấy thiết bị trong phạm vi nhà máy được phân quyền'}, status=403)

        # Xử lý từng dòng (48 chu kỳ)
        for index, row in df.iterrows():
            try:
                # Sử dụng ngày từ form và thời điểm từ chu kỳ
                ngay = import_date
                thoi_diem = time_cycles_list[index] if index < len(time_cycles_list) else f"{index:02d}:00"

                # Tạo timezone-aware datetime với Vietnam timezone
                datetime_str = f"{ngay} {thoi_diem}:00"

                naive_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
                # Sử dụng Asia/Ho_Chi_Minh timezone cụ thể thay vì get_current_timezone()
                import pytz
                vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                timezone_aware_datetime = vietnam_tz.localize(naive_datetime)

                # Xử lý từng thông số (33 cột)
                row_imported = 0

                for col_index, mapping_info in enumerate(column_mapping):
                    # Lấy giá trị từ cột tương ứng
                    value = row.iloc[col_index] if col_index < len(row) else None

                    # Lấy thông tin thiết bị từ mapping
                    device_code = mapping_info['device']
                    field_name = mapping_info['field']
                    unit = mapping_info['unit']
                    param_name = mapping_info['name']

                    # Xử lý cả ô có giá trị và ô trống
                    # Ô trống sẽ được lưu với giá trị NULL
                    if pd.isna(value) or value == '' or value is None:
                        value = None  # Lưu NULL cho ô trống

                    # Kiểm tra thiết bị có tồn tại không
                    if device_code not in thiet_bi_map:
                        continue

                    thiet_bi = thiet_bi_map[device_code]

                    # Tạo hoặc cập nhật bản ghi
                    try:
                        # Lookup gồm cả thời điểm để mỗi chu kỳ tạo bản ghi riêng
                        # Xử lý giá trị NULL cho ô trống
                        gia_tri_str = str(value) if value is not None else None

                        thong_so, created = ThongSoVanHanh.objects.get_or_create(
                            thiet_bi=thiet_bi,
                            ma_thong_so=field_name,
                            thoi_diem_nhap=timezone_aware_datetime,
                            defaults={
                                'gia_tri': gia_tri_str,
                                'don_vi': unit,
                                'ten_thong_so': param_name,
                                'ngay_nhap': ngay,
                                'nha_may': get_user_factory_name(request.user) or thiet_bi.nha_may,
                            }
                        )

                        if not created:
                            thong_so.gia_tri = gia_tri_str
                            thong_so.don_vi = unit
                            thong_so.ten_thong_so = param_name
                            thong_so.ngay_nhap = ngay
                            thong_so.nha_may = get_user_factory_name(request.user) or thiet_bi.nha_may
                            thong_so.save()

                        imported_count += 1
                        row_imported += 1

                    except Exception as e:
                        continue

            except Exception as e:
                continue

        return JsonResponse({
            'message': 'Import thành công',
            'imported_count': imported_count
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
