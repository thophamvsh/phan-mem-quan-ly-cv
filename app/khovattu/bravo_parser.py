"""
Bravo Code Parser - Trích xuất thông tin vị trí từ mã Bravo

Phân tích cấu trúc mã Bravo để tự động điền thông tin vị trí khi import vật tư.

Ví dụ mã Bravo: 1.26.46.001.000.A8.000
Cấu trúc có thể được hiểu như sau:
- Segment 1: Hệ thống/Danh mục (1)
- Segment 2: Loại thiết bị (26)
- Segment 3: Phân loại (46)
- Segment 4: Số thứ tự (001)
- Segment 5: Phụ thuộc (000)
- Segment 6: Vị trí - Kệ + Ngăn (A8)
- Segment 7: Tầng (000)
"""

import re
from typing import Dict, Optional, Tuple
from .models import Bang_vi_tri


class BravoCodeParser:
    """Parser để trích xuất thông tin vị trí từ mã Bravo"""

    def __init__(self):
        # Các pattern regex để nhận dạng mã vị trí trong Bravo code
        self.patterns = {
            # Pattern 1: X.X.X.X.X.A8.X (Kệ + Ngăn trong segment thứ 6)
            'standard': re.compile(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)\.(\d+)\.([A-Z]\d+)\.(\d+)$'),

            # Pattern 2: X.X.X.X.X.A.8.X (Kệ và Ngăn tách riêng)
            'separated': re.compile(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)\.(\d+)\.([A-Z])\.(\d+)\.(\d+)$'),

            # Pattern 3: X.X.X.X.X.93.X (Số thuần túy - cần map sang kệ/ngăn)
            'numeric_position': re.compile(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)\.(\d+)\.(\d+)\.(\d+)$'),

            # Pattern 4: Có thể có thêm các pattern khác
            'extended': re.compile(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)\.(\d+)\.([A-Z])(\d+)\.(\d+)$'),
        }

        # Mapping hệ thống theo segment đầu tiên
        self.he_thong_mapping = {
            '1': 'Đập tràn',
            '2': 'Nhà máy',
            '3': 'Trạm biến áp',
            '4': 'Hệ thống điện',
            '5': 'Kho vật tư',
            # Có thể mở rộng thêm
        }

    def parse_bravo_code(self, ma_bravo: str) -> Optional[Dict[str, str]]:
        """
        Phân tích mã Bravo và trích xuất thông tin vị trí

        Args:
            ma_bravo: Mã Bravo cần phân tích (VD: "1.26.46.001.000.A8.000")

        Returns:
            Dict chứa thông tin vị trí hoặc None nếu không parse được
            {
                'ma_he_thong': str,
                'kho': str,
                'ke': str,
                'ngan': str,
                'tang': str,
                'ma_vi_tri': str  # Mã rút gọn như "A8"
            }
        """
        if not ma_bravo:
            return None

        ma_bravo = ma_bravo.strip()

        # Thử từng pattern
        for pattern_name, pattern in self.patterns.items():
            match = pattern.match(ma_bravo)
            if match:
                return self._extract_position_info(match, pattern_name)

        # Nếu không match pattern nào, thử phương pháp heuristic
        return self._heuristic_parse(ma_bravo)

    def _extract_position_info(self, match: re.Match, pattern_name: str) -> Dict[str, str]:
        """Trích xuất thông tin vị trí từ regex match"""
        groups = match.groups()

        if pattern_name == 'standard':
            # Pattern: 1.26.46.001.000.A8.000
            he_thong_code = groups[0]
            kho = groups[1]  # Có thể dùng segment 2 làm kho
            ke_ngan = groups[5]  # "A8"
            tang = groups[6]

            # Tách kệ và ngăn từ "A8"
            ke_match = re.match(r'^([A-Z]+)(\d+)$', ke_ngan)
            if ke_match:
                ke = ke_match.group(1)  # "A"
                ngan = ke_match.group(2)  # "8"
            else:
                ke = ke_ngan[:1] if ke_ngan else ""
                ngan = ke_ngan[1:] if len(ke_ngan) > 1 else ""

        elif pattern_name == 'separated':
            # Pattern: 1.26.46.001.000.A.8.000
            he_thong_code = groups[0]
            kho = groups[1]
            ke = groups[5]  # "A"
            ngan = groups[6]  # "8"
            tang = groups[7]

        elif pattern_name == 'numeric_position':
            # Pattern: 3.30.14.008.000.93.000 (Số thuần túy)
            he_thong_code = groups[0]
            kho = groups[1]
            position_code = groups[5]  # "93", "00", "50"
            tang = groups[6]

            # Map số thành kệ/ngăn
            ke, ngan = self._map_numeric_to_position(position_code)

        else:
            # Pattern khác hoặc extended
            he_thong_code = groups[0] if len(groups) > 0 else ""
            kho = groups[1] if len(groups) > 1 else ""
            ke = groups[5] if len(groups) > 5 else ""
            ngan = groups[6] if len(groups) > 6 else ""
            tang = groups[7] if len(groups) > 7 else ""

        # Ánh xạ mã hệ thống
        ma_he_thong = self.he_thong_mapping.get(he_thong_code, f"Hệ thống {he_thong_code}")

        # Tạo mã vị trí rút gọn
        ma_vi_tri = f"{ke}{ngan}" if ke and ngan else ""

        return {
            'ma_he_thong': ma_he_thong,
            'kho': kho,
            'ke': ke,
            'ngan': ngan,
            'tang': tang,
            'ma_vi_tri': ma_vi_tri
        }

    def _map_numeric_to_position(self, position_code: str) -> Tuple[str, str]:
        """
        Map mã số thành kệ và ngăn

        Ví dụ:
        - 93 → Kệ I, Ngăn 3 (9 = I, 3 = 3)
        - 00 → Kệ A, Ngăn 0
        - 50 → Kệ E, Ngăn 0 (5 = E, 0 = 0)
        """
        if not position_code or len(position_code) < 2:
            return "A", "1"  # Default

        # Lấy 2 chữ số cuối
        position_code = position_code.zfill(2)  # Đảm bảo có 2 chữ số
        ke_num = int(position_code[0]) if position_code[0].isdigit() else 0
        ngan_num = position_code[1] if position_code[1].isdigit() else "1"

        # Map số thành chữ cái (0=A, 1=B, 2=C, ..., 9=J)
        alphabet = "ABCDEFGHIJ"
        ke = alphabet[ke_num] if ke_num < len(alphabet) else "A"

        # Ngăn giữ nguyên số, nhưng 0 thành 1
        ngan = ngan_num if ngan_num != "0" else "1"

        return ke, ngan

    def _heuristic_parse(self, ma_bravo: str) -> Optional[Dict[str, str]]:
        """
        Phương pháp heuristic để parse các mã không theo pattern chuẩn
        """
        # Tách theo dấu chấm
        segments = ma_bravo.split('.')
        if len(segments) < 6:
            return None

        # Logic mới: Xác định position code dựa trên cấu trúc
        # Format: X.X.X.X.COUNTRY.POSITION.X
        # hoặc:   X.X.X.X.000.POSITION.X

        position_segment = None
        country_segment = None

        if len(segments) >= 7:
            # Có thể có country code ở index 4
            potential_country = segments[4]
            potential_position = segments[5]

            # Kiểm tra xem có phải country code không (3 ký tự uppercase)
            if len(potential_country) == 3 and potential_country.isupper() and potential_country.isalpha():
                country_segment = potential_country
                position_segment = potential_position
                print(f"🔍 Heuristic: Country '{country_segment}', Position '{position_segment}'")
            else:
                # Không có country code, position ở index 4
                position_segment = potential_country
                print(f"🔍 Heuristic: No country, Position '{position_segment}'")
        elif len(segments) >= 6:
            # Format ngắn hơn
            position_segment = segments[4]
            print(f"🔍 Heuristic: Short format, Position '{position_segment}'")

        if not position_segment:
            return None

        # Trích xuất kệ và ngăn từ position segment
        pos_match = re.match(r'^([A-Z]+)(\d+)$', position_segment)
        if pos_match:
            ke = pos_match.group(1)
            ngan = pos_match.group(2)
        else:
            ke = position_segment[:1] if position_segment else ""
            ngan = position_segment[1:] if len(position_segment) > 1 else ""

        # Dự đoán các thông tin khác
        he_thong_code = segments[0] if segments else "1"
        ma_he_thong = self.he_thong_mapping.get(he_thong_code, f"Hệ thống {he_thong_code}")
        kho = segments[1] if len(segments) > 1 else "1"
        tang = segments[-1] if len(segments) > 6 else "1"  # Tầng ở cuối
        ma_vi_tri = f"{ke}{ngan}" if ke and ngan else ""

        return {
            'ma_he_thong': ma_he_thong,
            'kho': kho,
            'ke': ke,
            'ngan': ngan,
            'tang': tang,
            'ma_vi_tri': ma_vi_tri
        }

    def create_or_get_vi_tri(self, position_info: Dict[str, str]) -> Optional['Bang_vi_tri']:
        """
        Tạo hoặc lấy đối tượng Bang_vi_tri từ thông tin vị trí đã parse
        """
        if not position_info or not position_info.get('ma_vi_tri'):
            return None

        try:
            # Thử lấy vị trí đã có
            vi_tri = Bang_vi_tri.objects.get(ma_vi_tri=position_info['ma_vi_tri'])
            return vi_tri
        except Bang_vi_tri.DoesNotExist:
            # Tạo mới nếu chưa có
            try:
                vi_tri = Bang_vi_tri.objects.create(
                    ma_vi_tri=position_info['ma_vi_tri'],
                    ma_he_thong=position_info.get('ma_he_thong', ''),
                    kho=position_info.get('kho', ''),
                    ke=position_info.get('ke', ''),
                    ngan=position_info.get('ngan', ''),
                    tang=position_info.get('tang', ''),
                    mo_ta=f"Auto-generated from Bravo code parsing"
                )
                return vi_tri
            except Exception as e:
                return None


# Singleton instance
bravo_parser = BravoCodeParser()


def extract_position_from_bravo(ma_bravo: str) -> Optional[Dict[str, str]]:
    """
    Hàm tiện ích để trích xuất thông tin vị trí từ mã Bravo

    Args:
        ma_bravo: Mã Bravo cần phân tích

    Returns:
        Dict chứa thông tin vị trí hoặc None
    """
    return bravo_parser.parse_bravo_code(ma_bravo)


def get_vi_tri_from_bravo(ma_bravo: str) -> Optional['Bang_vi_tri']:
    """
    Hàm tiện ích để lấy/tạo đối tượng Bang_vi_tri từ mã Bravo

    Args:
        ma_bravo: Mã Bravo cần phân tích

    Returns:
        Bang_vi_tri object hoặc None
    """
    position_info = extract_position_from_bravo(ma_bravo)
    if position_info:
        return bravo_parser.create_or_get_vi_tri(position_info)
    return None


# Test function
def test_bravo_parsing():
    """Test function để kiểm tra parsing"""
    test_codes = [
        "1.26.46.001.000.A8.000",
        "2.15.30.002.100.B5.001",
        "3.40.20.005.000.C12.002",
        "1.26.46.001.000.A.8.000",  # Separated format
        "4.TEST.A9",  # Irregular format
    ]

    # Test function - logs removed for production
    for code in test_codes:
        result = extract_position_from_bravo(code)


if __name__ == "__main__":
    test_bravo_parsing()
