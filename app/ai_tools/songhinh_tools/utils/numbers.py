"""
Number parsing utilities
"""

from typing import Optional, Any


def parse_float_loose(value: Any) -> Optional[float]:
    """
    Parse float accepting dấu chấm và dấu phẩy (Sheet Sông Hinh: MNH có thể "208,957" = 208.957 m).
    - decimal comma: "12,34" hoặc "208,957" (MNH mét)
    - thousands comma: "1,234" hoặc "470,000,000"
    - Cùng có ',' và '.': heuristic theo vị trí (phẩy trước chấm → phẩy là hàng nghìn; ngược lại → chấm là hàng nghìn).
    - Chỉ một dấu phẩy: nếu hiểu là hàng nghìn ra số rất lớn (>10000) mà hiểu là thập phân ra 0..1000 (vd MNH) → dùng thập phân (208,957 → 208.957).
    - Chỉ dấu chấm hoặc số thuần → float như bình thường.
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
            # Only comma present - determine if thousands or decimal separator
            comma_count = s.count(",")
            if comma_count > 1:
                # Multiple commas = thousands separator (e.g., "470,000,000")
                s = s.replace(",", "")
            else:
                # Single comma: "208,957" (MNH 208.957 m) vs "1,234" (1234)
                # Try both: if thousands interpretation is huge (>10000) and decimal is plausible (0..1000), use decimal (European MNH)
                parts = s.split(",")
                if len(parts) == 2 and parts[0].replace("-", "").isdigit() and parts[1].replace("-", "").isdigit():
                    try:
                        val_thousands = float(s.replace(",", ""))
                        val_decimal = float(s.replace(",", "."))
                        # Nếu hiểu là hàng nghìn ra số >= 1000 mà hiểu thập phân ra 0..1000 (vd Qve m³/s, MNH m) → dùng thập phân. 9,931 → 9.931; 43,820 → 43.82
                        if val_thousands >= 1000 and 0 <= val_decimal <= 1000:
                            return val_decimal
                        if val_thousands < 1000:
                            # e.g. 1,234 → 1234 hoặc 1.234 tùy ngữ cảnh; giữ cách cũ (thousands)
                            s = s.replace(",", "")
                        else:
                            s = s.replace(",", ".")
                    except Exception:
                        s = s.replace(",", ".")
                else:
                    s = s.replace(",", ".")
        # else '.' or plain digits - no change needed
        return float(s)
    except Exception:
        return None


def parse_number(value) -> Optional[float]:
    """Alias for parse_float_loose for consistency with vinhson_tools"""
    return parse_float_loose(value)


def parse_kwh_integer(value: Any) -> Optional[float]:
    """
    Parse Sản lượng tự dùng (kWh) từ cột X. Sheet có thể ghi "4,710" (dấu phẩy hàng nghìn)
    hoặc "4710". Luôn coi dấu phẩy là hàng nghìn, không dùng heuristic thập phân.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "-":
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None


def normalize_mnh_value(value: Optional[float]) -> Optional[float]:
    """
    Chuẩn hóa giá trị MNH (mực nước hồ, đơn vị m). Sheet đôi khi lưu 208,957 thành 208957.
    Nếu value nằm trong khoảng "sai lệch" (vd 208957) và chia 1000 ra khoảng MNH hợp lý (50..500 m), trả về value/1000.
    """
    if value is None:
        return None
    if value >= 10000 and value < 1_000_000:
        scaled = value / 1000.0
        if 50 <= scaled <= 500:
            return scaled
    return value


def fmt_pct(value: Optional[float], digits: int = 2) -> str:
    """Format percentage"""
    if value is None:
        return "-"
    return f"{value:.{digits}f}%"


def safe_cell(row: list, idx: int, default: str = "") -> str:
    """Safely get cell value from row"""
    if idx < 0 or idx >= len(row):
        return default
    return str(row[idx]).strip()
