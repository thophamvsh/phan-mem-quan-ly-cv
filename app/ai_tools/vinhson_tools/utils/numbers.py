"""
Number parsing utilities
"""

import re
from typing import Any, Optional


def parse_float_loose(value: Any) -> Optional[float]:
    """
    Parse float accepting:
    - decimal comma: "12,34"
    - thousands comma: "1,234" or "470,000,000"
    - "1,234.56" or "1.234,56" not fully supported; handle common cases for your sheets.
    Rule:
    - If contains both ',' and '.', we remove thousands separators by heuristics:
      * if ',' occurs before '.' -> treat ',' as thousands sep -> remove ALL commas
      * else -> treat '.' as thousands sep -> remove ALL dots and replace last comma with dot
    - If only ',' -> check if it's thousands separator (multiple commas) or decimal:
      * If multiple commas (e.g., "470,000,000") -> remove ALL commas
      * If single comma -> treat as decimal separator -> replace with '.'
    - If only '.' -> float as is
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "-":
        return None

    try:
        if "," in s and "." in s:
            # Both comma and dot present
            comma_pos = s.find(",")
            dot_pos = s.find(".")
            if comma_pos < dot_pos:
                # Comma before dot: comma is thousands separator, dot is decimal
                # Remove ALL commas
                s = s.replace(",", "")
            else:
                # Dot before comma: dot is thousands separator, comma is decimal
                # Remove ALL dots, replace comma with dot
                s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            # Only comma present - need to determine if thousands or decimal separator
            comma_count = s.count(",")
            if comma_count > 1:
                # Multiple commas = thousands separator (e.g., "470,000,000")
                s = s.replace(",", "")
            else:
                # Single comma - could be decimal or thousands separator
                # Check if there are 3 digits after comma (thousands separator pattern)
                parts = s.split(",")
                if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
                    # Pattern like "123,456" (likely thousands) or "12,345" (could be either)
                    # For safety, if right part has 3 digits and left part <= 3 digits, treat as thousands
                    s = s.replace(",", "")
                else:
                    # Likely decimal separator
                    s = s.replace(",", ".")
        # else '.' or plain digits - no change needed
        return float(s)
    except Exception:
        return None


def parse_number(value) -> Optional[float]:
    """
    Robust parse number:
    - "1.234,56" -> 1234.56
    - "1,234.56" -> 1234.56
    - "12,34" -> 12.34
    - "12.34" -> 12.34
    - "470,000,000" -> 470000000.0 (multiple commas as thousands separator)
    - "45,007,551" -> 45007551.0 (multiple commas as thousands separator)
    - "340.000.000" -> 340000000.0 (multiple dots as thousands separator)
    - "31.039.570" -> 31039570.0 (multiple dots as thousands separator)
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "-":
        return None

    try:
        if "," in s and "." in s:
            # Both comma and dot present
            comma_pos = s.find(",")
            dot_pos = s.find(".")
            if comma_pos < dot_pos:
                # Comma before dot: comma is thousands separator, dot is decimal
                # Remove ALL commas
                s = s.replace(",", "")
            else:
                # Dot before comma: dot is thousands separator, comma is decimal
                # Remove ALL dots, replace comma with dot
                s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            # Only comma present - need to determine if thousands or decimal separator
            comma_count = s.count(",")
            if comma_count > 1:
                # Multiple commas = thousands separator (e.g., "470,000,000")
                s = s.replace(",", "")
            else:
                # Single comma - could be decimal or thousands separator
                # Check if there are 3 digits after comma (thousands separator pattern)
                parts = s.split(",")
                if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
                    # Pattern like "123,456" (likely thousands) or "12,345" (could be either)
                    # For safety, if right part has 3 digits and left part <= 3 digits, treat as thousands
                    s = s.replace(",", "")
                else:
                    # Likely decimal separator
                    s = s.replace(",", ".")
        elif "." in s:
            # Only dot present - need to determine if thousands or decimal separator
            dot_count = s.count(".")
            if dot_count > 1:
                # Multiple dots = thousands separator (e.g., "340.000.000", "31.039.570")
                s = s.replace(".", "")
            else:
                # Single dot - could be decimal or thousands separator
                # Check if there are 3 digits after dot (thousands separator pattern)
                parts = s.split(".")
                if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) <= 3:
                    # Pattern like "123.456" (likely thousands) or "12.345" (could be either)
                    # For safety, if right part has 3 digits and left part <= 3 digits, treat as thousands
                    s = s.replace(".", "")
                # else single dot with different pattern - treat as decimal separator (no change)
        # else plain digits - no change needed
        return float(s)
    except (ValueError, Exception) as e:
        print(f"[DEBUG] parse_number failed for '{value}': {e}", flush=True)
        return None


def parse_number_stats(value: Any, max_reasonable: float = 1000) -> Optional[float]:
    """
    Parse số từ sheet thống kê (TV VS 2023, v.v.) khi dấu chấm/phẩy lộn xộn.
    - Dấu phẩy thập phân: "769,35" -> 769.35 (parse_number xử lý).
    - Dấu chấm thập phân: "768.32" -> 768.32 (parse_number xử lý).
    - Lỗi dạng XX.YYY bị hiểu thành hàng nghìn: "77.337" (ý 773.37 m) -> 77337;
      nếu result > max_reasonable thì hiểu lại là XX*10 + YYY/100 (773.37).
    - Khi API trả về số (77337.0) không còn chuỗi "77.337": nếu max_reasonable=1000 và
      600 <= result/100 <= 1000 thì coi là MNH bị nhân nhầm 100 lần -> trả về result/100.
    - max_reasonable: MNH dùng 1000; Qve dùng 10000.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "-":
        return None
    result = parse_number(value)
    if result is None:
        return None
    if result <= max_reasonable:
        return result
    # Sửa lỗi chuỗi "77.337" -> 77337 thành 773.37; "12.345" -> 12345 thành 123.45
    if re.match(r"^\d{2}\.\d{3}$", s):
        parts = s.split(".", 1)
        try:
            result = int(parts[0]) * 10 + int(parts[1]) / 100
            return result
        except (ValueError, TypeError):
            pass
    # Sửa lỗi khi sheet/API trả về số 77337 (không còn chuỗi "77.337"): MNH hợp lý 600–1000 m
    if max_reasonable == 1000 and result >= 60000 and result <= 100000:
        candidate = result / 100
        if 600 <= candidate <= 1000:
            return candidate
    return result


def parse_number_for_mnh(value: Any) -> Optional[float]:
    """Parse số cho cột MNH (mực nước hồ); max_reasonable=1000 (m)."""
    return parse_number_stats(value, max_reasonable=1000)


def parse_number_for_qve(value: Any) -> Optional[float]:
    """Parse số cho cột Qve (lưu lượng) từ sheet thống kê; max_reasonable=10000 (m³/s)."""
    return parse_number_stats(value, max_reasonable=10000)


def parse_kwh_integer(value: Any) -> Optional[float]:
    """
    Parse Sản lượng tự dùng (kWh) từ cột X. Ở Vĩnh Sơn dùng dấu chấm cho tất cả các ô:
    cột X có thể ghi "1.843" (dấu chấm hàng nghìn) hoặc "1,843"/"1843". Loại bỏ cả dấu chấm
    và dấu phẩy để luôn ra số nguyên kWh.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "-":
        return None
    s = s.replace(",", "").replace(".", "")
    try:
        return float(s)
    except Exception:
        return None


def safe_cell(row: list, idx: int, default: str = "") -> str:
    """Safely get cell value from row"""
    if idx < 0 or idx >= len(row):
        return default
    return str(row[idx]).strip()
