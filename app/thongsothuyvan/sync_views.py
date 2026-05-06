import os
import gspread
from google.oauth2.service_account import Credentials
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from .models import ThongsoSanxuat, ThongsoGioPhat
from .serializers import ThongsoSanxuatSerializer
from .plants import normalize_plant_code

def get_env_value(name):
    value = os.environ.get(name)
    if value:
        return value

    env_path = os.path.join(settings.BASE_DIR.parent, '.env')
    if not os.path.exists(env_path):
        return None

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, raw_value = line.split('=', 1)
            if key.strip() == name:
                return raw_value.strip().strip('"').strip("'")

    return None

# Định nghĩa hàm lấy credentials an toàn
def get_gspread_client(nhamay='songhinh'):
    nhamay = normalize_plant_code(nhamay)
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

    credential_file = get_env_value(f'{nhamay.upper()}_GOOGLE_CREDENTIALS')
    if not credential_file:
        credential_file = (
            'vinhson-account-key.json'
            if nhamay == 'vinhson'
            else 'ai-project-484022-8239457b26bb.json'
        )
    creds_path = os.path.join(settings.BASE_DIR, credential_file)
    
    if not os.path.exists(creds_path):
        raise FileNotFoundError(f"Không tìm thấy file credentials tại {creds_path}")
        
    creds = Credentials.from_service_account_file(creds_path, scopes=scope)
    client = gspread.authorize(creds)
    return client

def parse_date(date_str):
    if not date_str:
        return None
        
    date_str = date_str.strip()
    
    # Thử các định dạng có thể có trong Sheet
    formats = [
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y',
        '%Y-%m-%d',
        '%m/%d/%Y'
    ]
    
    for fmt in formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            if timezone.is_naive(parsed_date):
                return timezone.make_aware(parsed_date)
            return parsed_date
        except ValueError:
            pass
            
    return None

def parse_filter_date(date_str):
    if not date_str:
        return None

    try:
        return datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
    except ValueError:
        return None

def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.strip().replace(' ', '')
            if not val:
                return None

            has_comma = ',' in val
            has_dot = '.' in val

            if has_comma and has_dot:
                if val.rfind(',') > val.rfind('.'):
                    val = val.replace('.', '').replace(',', '.')
                else:
                    val = val.replace(',', '')
            elif has_comma:
                parts = val.split(',')
                if len(parts) == 2 and len(parts[1]) in (1, 2):
                    val = val.replace(',', '.')
                else:
                    val = val.replace(',', '')
            elif has_dot:
                parts = val.split('.')
                if len(parts) > 2:
                    val = val.replace('.', '')
                elif len(parts) == 2 and len(parts[1]) == 3:
                    val = val.replace('.', '')
        return float(val)
    except:
        return None

def parse_to_may(val):
    text = str(val or '').strip().upper()
    if text.startswith('H'):
        text = text[1:]
    return int(text) if text.isdigit() else None

def parse_cot_c(val, nhamay):
    nhamay = normalize_plant_code(nhamay)
    if nhamay == 'vinhson':
        return 'vinhson'

    if val is None:
        return None

    val = str(val).strip()
    return val or None

def get_spreadsheet_id(nhamay):
    nhamay = normalize_plant_code(nhamay)
    if nhamay == 'songhinh':
        return get_env_value('SONGHINH_SPREADSHEET_ID')
    if nhamay == 'vinhson':
        return get_env_value('VINHSON_SPREADSHEET_ID')
    return get_env_value(f'{nhamay.upper()}_SPREADSHEET_ID')

class PreviewGoogleSheetAPIView(APIView):
    """API đọc dữ liệu từ Google Sheet để hiển thị (chưa lưu vào DB)"""
    
    def get(self, request):
        try:
            nhamay = normalize_plant_code(request.query_params.get('nhamay', 'songhinh'))
            filter_date_str = request.query_params.get('date')
            filter_date = parse_filter_date(filter_date_str)

            if filter_date_str and not filter_date:
                return Response({'error': 'Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD'}, status=400)
            
            sheet_id = get_spreadsheet_id(nhamay)
                
            if not sheet_id:
                return Response({'error': f'Chưa cấu hình SPREADSHEET_ID cho {nhamay} trong .env'}, status=400)
                
            client = get_gspread_client(nhamay)
            sheet = client.open_by_key(sheet_id)
            
            # Tab Sản lượng
            worksheet_san_luong = sheet.worksheet('Sản lượng')
            # Lấy tất cả giá trị. Dữ liệu bắt đầu từ Cột B -> X (index 1 -> 23)
            all_records = worksheet_san_luong.get_all_values()
            
            parsed_data = []
            
            # Giả sử dòng 1 là Header, bắt đầu từ dòng 2
            for row in all_records[1:]:
                # Đảm bảo row có đủ độ dài tới cột X (index 23)
                padded_row = row + [''] * (24 - len(row))
                
                thoi_gian_str = padded_row[1] # Cột B
                if not thoi_gian_str:
                    continue
                    
                thoi_gian = parse_date(thoi_gian_str)
                if not thoi_gian:
                    continue # Bỏ qua dòng có thời gian không hợp lệ
                    
                # Chỉ lấy dữ liệu từ 01/01/2023 đến ngày hiện tại
                if thoi_gian.year < 2023 or thoi_gian.date() > timezone.localdate():
                    continue

                if filter_date and thoi_gian.date() != filter_date:
                    continue
                    
                record = {
                    'thoi_gian': thoi_gian,
                    'thoi_gian_str': thoi_gian_str,
                    'cot_c': parse_cot_c(padded_row[2], nhamay),
                    'cot_d': safe_float(padded_row[3]),
                    # Bỏ qua cột E (index 4)
                    'cot_f': safe_float(padded_row[5]),
                    'cot_g': safe_float(padded_row[6]),
                    'cot_h': safe_float(padded_row[7]),
                    'cot_i': safe_float(padded_row[8]),
                    'cot_j': safe_float(padded_row[9]),
                    'cot_k': safe_float(padded_row[10]),
                    'cot_l': safe_float(padded_row[11]),
                    'cot_m': safe_float(padded_row[12]),
                    'cot_n': safe_float(padded_row[13]),
                    'cot_o': safe_float(padded_row[14]),
                    'cot_p': safe_float(padded_row[15]),
                    'cot_q': safe_float(padded_row[16]),
                    'cot_r': safe_float(padded_row[17]),
                    'cot_s': safe_float(padded_row[18]),
                    'cot_t': safe_float(padded_row[19]),
                    'cot_u': safe_float(padded_row[20]),
                    'cot_v': safe_float(padded_row[21]),
                    'cot_w': safe_float(padded_row[22]),
                    'cot_x': safe_float(padded_row[23]),
                }
                parsed_data.append(record)
                
            return Response({
                'success': True,
                'data': parsed_data,
                'message': f'Đã lấy dữ liệu thành công từ tab Sản lượng ({nhamay})'
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class SaveGoogleSheetDataAPIView(APIView):
    """API lưu dữ liệu đã xem trước vào database"""
    
    def post(self, request):
        data_list = request.data.get('data', [])
        nhamay = normalize_plant_code(request.query_params.get('nhamay', 'songhinh'))
        
        if not data_list:
            return Response({'error': 'Không có dữ liệu để lưu'}, status=400)
            
        saved_count = 0
        updated_count = 0
        
        for item in data_list:
            thoi_gian = item.get('thoi_gian')
            if not thoi_gian:
                continue
                
            # Tạo hoặc Cập nhật dựa trên khóa chính là thoi_gian và nha_may
            obj, created = ThongsoSanxuat.objects.update_or_create(
                thoi_gian=thoi_gian,
                nha_may=nhamay,
                defaults={
                    'cot_c': item.get('cot_c'),
                    'cot_d': item.get('cot_d'),
                    'cot_f': item.get('cot_f'),
                    'cot_g': item.get('cot_g'),
                    'cot_h': item.get('cot_h'),
                    'cot_i': item.get('cot_i'),
                    'cot_j': item.get('cot_j'),
                    'cot_k': item.get('cot_k'),
                    'cot_l': item.get('cot_l'),
                    'cot_m': item.get('cot_m'),
                    'cot_n': item.get('cot_n'),
                    'cot_o': item.get('cot_o'),
                    'cot_p': item.get('cot_p'),
                    'cot_q': item.get('cot_q'),
                    'cot_r': item.get('cot_r'),
                    'cot_s': item.get('cot_s'),
                    'cot_t': item.get('cot_t'),
                    'cot_u': item.get('cot_u'),
                    'cot_v': item.get('cot_v'),
                    'cot_w': item.get('cot_w'),
                    'cot_x': item.get('cot_x'),
                }
            )
            if created:
                saved_count += 1
            else:
                updated_count += 1
                
        return Response({
            'success': True,
            'message': f'Đã lưu thành công. Tạo mới: {saved_count}, Cập nhật: {updated_count}'
        })


class PreviewGioPhatAPIView(APIView):
    """API đọc dữ liệu từ tab Giờ phát"""
    
    def get(self, request):
        try:
            nhamay = normalize_plant_code(request.query_params.get('nhamay', 'songhinh'))
            filter_date_str = request.query_params.get('date')
            filter_date = parse_filter_date(filter_date_str)

            if filter_date_str and not filter_date:
                return Response({'error': 'Dinh dang ngay khong hop le. Vui long dung YYYY-MM-DD'}, status=400)
            
            sheet_id = get_spreadsheet_id(nhamay)
                
            if not sheet_id:
                return Response({'error': f'Chưa cấu hình SPREADSHEET_ID cho {nhamay} trong .env'}, status=400)
                
            client = get_gspread_client(nhamay)
            sheet = client.open_by_key(sheet_id)
            
            # Tab Giờ phát
            worksheet_gio_phat = sheet.worksheet('Giờ phát')
            all_records = worksheet_gio_phat.get_all_values()
            
            parsed_data = []
            
            # Dòng 1, 2 là Header/Instruction, dữ liệu thường bắt đầu từ dòng 3 (index 2)
            # Ta quét qua để tìm dòng có chứa date hợp lệ
            for row in all_records:
                # Đảm bảo row có đủ cột tới E (index 4)
                padded_row = row + [''] * (5 - len(row))
                
                ngay_str = padded_row[1] # Cột B
                
                # Check nếu B không phải là ngày hợp lệ (ví dụ: dd/mm/yyyy)
                if not ngay_str or '/' not in ngay_str:
                    continue
                
                try:
                    ngay = datetime.strptime(ngay_str, '%d/%m/%Y').date()
                except ValueError:
                    continue # Bỏ qua header

                if ngay.year < 2023 or ngay > timezone.localdate():
                    continue

                if filter_date and ngay != filter_date:
                    continue
                
                # Cột C: Tổ máy
                to_may = parse_to_may(padded_row[2])
                if to_may is None:
                    continue
                    
                record = {
                    'ngay': str(ngay), # format yyyy-mm-dd cho JSON response
                    'ngay_str': ngay_str,
                    'to_may': to_may,
                    'gio_phat_dien': safe_float(padded_row[3]), # Cột D
                    'gio_ngung': safe_float(padded_row[4]), # Cột E
                }
                parsed_data.append(record)
                
            return Response({
                'success': True,
                'data': parsed_data,
                'message': 'Đã lấy dữ liệu thành công từ tab Giờ phát'
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class SaveGioPhatAPIView(APIView):
    """API lưu dữ liệu Giờ phát vào database"""
    
    def post(self, request):
        from .models import ThongsoGioPhat
        data_list = request.data.get('data', [])
        nhamay = normalize_plant_code(request.query_params.get('nhamay', 'songhinh'))
        
        if not data_list:
            return Response({'error': 'Không có dữ liệu để lưu'}, status=400)
            
        saved_count = 0
        updated_count = 0
        
        for item in data_list:
            ngay = item.get('ngay')
            to_may = item.get('to_may')
            
            if not ngay or to_may is None:
                continue
                
            # Tạo hoặc Cập nhật dựa trên unique_together (ngay, to_may, nha_may)
            obj, created = ThongsoGioPhat.objects.update_or_create(
                ngay=ngay,
                to_may=to_may,
                nha_may=nhamay,
                defaults={
                    'gio_phat_dien': item.get('gio_phat_dien'),
                    'gio_ngung': item.get('gio_ngung'),
                }
            )
            if created:
                saved_count += 1
            else:
                updated_count += 1
                
        return Response({
            'success': True,
            'message': f'Đã lưu thành công. Tạo mới: {saved_count}, Cập nhật: {updated_count}'
        })
