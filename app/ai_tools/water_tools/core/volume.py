"""
Volume calculation functions
"""

from thuyvan_data_client import interpolate_water_volume


# Reservoir water level specifications (MNC and MNDBT)
RESERVOIR_SPECS = {
    "Sông Hinh": {"MNC": 196.0, "MNDBT": 209.0},
    "Vĩnh Sơn A": {"MNC": 765.0, "MNDBT": 775.0},
    "Vĩnh Sơn B": {"MNC": 813.6, "MNDBT": 826.0},
    "Vĩnh Sơn C": {"MNC": 971.3, "MNDBT": 981.0},
}


def get_flood_control_volume(water_level, reservoir="Sông Hinh"):
    """
    Calculate flood control volume at a given water level
    Flood control volume = V(MNDBT) - V(current_level)

    When user asks:
    - "dung tich phong lu cua hồ X"
    - "với mực nước Y dung tích phòng lũ bao nhiêu"

    Args:
        water_level: Current water level in meters
        reservoir: Reservoir name (e.g., "Sông Hinh", "Vĩnh Sơn A")

    Returns:
        String with flood control volume information (markdown formatted)
    """
    # Normalize reservoir name
    normalized = reservoir.lower().strip()
    if "vĩnh sơn" in normalized or "vinh son" in normalized:
        if "a" in normalized or " ho a" in normalized:
            reservoir = "Vĩnh Sơn A"
        elif "b" in normalized or " ho b" in normalized:
            reservoir = "Vĩnh Sơn B"
        elif "c" in normalized or " ho c" in normalized:
            reservoir = "Vĩnh Sơn C"
        else:
            reservoir = "Vĩnh Sơn A"  # Default to A

    print(f"📊 FLOOD CONTROL VOLUME TOOL: Calculating for water level {water_level}m at {reservoir}", flush=True)

    if reservoir not in RESERVOIR_SPECS:
        return f"Không tìm thấy thông số cho hồ {reservoir}"

    spec = RESERVOIR_SPECS[reservoir]
    MNDBT = spec["MNDBT"]

    # Get volume at current water level
    current_result = interpolate_water_volume(float(water_level), reservoir)

    # Get volume at MNDBT
    mndbt_result = interpolate_water_volume(MNDBT, reservoir)

    if not current_result:
        return f"Không tìm thấy dữ liệu cho mực nước {water_level}m"

    if not mndbt_result:
        return f"Không tìm thấy dữ liệu cho mực nước {MNDBT}m"

    V_current = current_result['V']
    V_mndbt = mndbt_result['V']
    flood_volume = V_mndbt - V_current

    print(f"✓ V(level={water_level}m) = {V_current:.3f} triệu m³, V(MNDBT={MNDBT}m) = {V_mndbt:.3f} triệu m³", flush=True)
    print(f"✓ Dung tích phòng lũ = {flood_volume:.3f} triệu m³", flush=True)

    response = f"""
### Dung tích phòng lũ hồ {reservoir}

#### Thông số:
| Thông số | Giá trị |
|----------|---------|
| **Mực nước hiện tại** | {water_level}m |
| **MNDBT** | {MNDBT}m |
| **Chênh lệch mực nước** | {MNDBT - float(water_level):.1f}m |

---

#### Tra cứu dung tích:

| Mực nước | Dung tích |
|-----------|----------|
| Hiện tại ({water_level}m) | **{V_current:.3f} triệu m³** |
| MNDBT ({MNDBT}m) | **{V_mndbt:.3f} triệu m³** |

---

#### 📌 Kết quả: Dung tích phòng lũ

**Dung tích phòng lũ = V(MNDBT) - V(mực nước hiện tại)**
**= {V_mndbt:.3f} - {V_current:.3f} = {flood_volume:.3f} triệu m³**

---

**Dung tích phòng lũ tại mực nước {water_level}m: {flood_volume:.3f} triệu m³**
*(Tương đương {flood_volume * 1_000_000:.0f} m³)*

📝 **Ý nghĩa:** Đây là lượng nước còn có thể chứa thêm được trước khi đạt MNDBT.
""".strip()

    return response


def get_useful_volume(reservoir="Sông Hinh"):
    """
    Calculate total useful volume of a reservoir (between dead water level and normal water level)

    When user asks:
    - "tổng dung tích hữu ích của hồ Sông Hinh"
    - "dung tích hữu ích Vĩnh Sơn"

    Args:
        reservoir: Reservoir name (e.g., "Sông Hinh", "Vĩnh Sơn A")

    Returns:
        String with useful volume information (markdown formatted)
    """
    # Normalize reservoir name
    normalized = reservoir.lower().strip()
    if "vĩnh sơn" in normalized or "vinh son" in normalized:
        if "a" in normalized or " ho a" in normalized:
            reservoir = "Vĩnh Sơn A"
        elif "b" in normalized or " ho b" in normalized:
            reservoir = "Vĩnh Sơn B"
        elif "c" in normalized or " ho c" in normalized:
            reservoir = "Vĩnh Sơn C"
        else:
            reservoir = "Vĩnh Sơn A"  # Default to A

    print(f"📊 USEFUL VOLUME TOOL: Calculating for {reservoir}", flush=True)

    if reservoir not in RESERVOIR_SPECS:
        return f"Không tìm thấy thông số cho hồ {reservoir}"

    spec = RESERVOIR_SPECS[reservoir]
    MNC = spec["MNC"]
    MNDBT = spec["MNDBT"]

    # Dead/normal water levels are water levels (m). Their interpolated values are volumes (million m³).
    mnc_result = interpolate_water_volume(MNC, reservoir)
    mndbt_result = interpolate_water_volume(MNDBT, reservoir)

    if not mnc_result:
        return f"Không tìm thấy dữ liệu cho mực nước {MNC}m"

    if not mndbt_result:
        return f"Không tìm thấy dữ liệu cho mực nước {MNDBT}m"

    V_mnc = mnc_result['V']
    V_mndbt = mndbt_result['V']
    useful_volume = V_mndbt - V_mnc

    print(f"✓ V(dead level={MNC} m) = {V_mnc:.3f} triệu m³, V(normal level={MNDBT} m) = {V_mndbt:.3f} triệu m³", flush=True)
    print(f"✓ Dung tích hữu ích = {useful_volume:.3f} triệu m³", flush=True)

    response = f"""
### Tổng dung tích hữu ích hồ {reservoir}

#### Thông số mực nước:

- **Mực nước chết: {MNC} m**
- **Mực nước dâng bình thường: {MNDBT} m**
- **Chênh lệch mực nước: {MNDBT - MNC:.1f} m**

**Lưu ý:** Mực nước chết là **mực nước/cao trình**, đơn vị là **m**. Dung tích tại mực nước chết có đơn vị **triệu m³**.

---

#### Tra cứu dung tích tại các mực nước:

| Mực nước | Dung tích |
|-----------|----------|
| Mực nước chết ({MNC} m) | **{V_mnc:.3f} triệu m³** |
| Mực nước dâng bình thường ({MNDBT} m) | **{V_mndbt:.3f} triệu m³** |

---

#### 📌 Kết quả: Dung tích hữu ích

**Dung tích hữu ích = V(mực nước dâng bình thường) - V(mực nước chết)**
**= {V_mndbt:.3f} - {V_mnc:.3f} = {useful_volume:.3f} triệu m³**

---

**Tổng dung tích hữu ích hồ {reservoir}: {useful_volume:.3f} triệu m³**
*(Tương đương {useful_volume * 1_000_000:.0f} m³)*
""".strip()

    return response


def get_water_volume(water_level, reservoir="Sông Hinh"):
    """
    Query internal hydrological data to get volume based on water level using linear interpolation
    (Hydrological Standard Method)

    Args:
        water_level: The water level (Mực nước) to query
        reservoir: Reservoir name (default: "Sông Hinh")

    Returns:
        String with volume information (markdown formatted)
    """
    print(f"🔍 DATABASE TOOL CALLED: Getting volume for water level {water_level}m at {reservoir}", flush=True)

    try:
        target_level = float(water_level)

        # Use linear interpolation (hydrological standard)
        result = interpolate_water_volume(target_level, reservoir)

        if not result:
            return "Không có dữ liệu mực nước trong database"

        H = result['H']
        V = result['V']
        H1 = result['H1']
        V1 = result['V1']
        H2 = result['H2']
        V2 = result['V2']
        method = result['method']

        print(f"✓ Method: {method}, H={H}m, V={V:.3f} triệu m³", flush=True)

        # Format response based on method
        if method == 'exact':
            response = f"""
### Tra cứu dung tích hồ {reservoir}

**Mực nước:** {H}m

**Kết quả:** {V} triệu m³ (giá trị chính xác từ bảng quan hệ)
""".strip()

        elif method == 'interpolated':
            response = f"""
### Tra cứu dung tích hồ {reservoir} - Nội suy tuyến tính

**Mực nước tra cứu:** H = {H}m

---

#### 📊 Phương pháp: Nội suy tuyến tính (Chuẩn Thủy văn)

**Dữ liệu bảng quan hệ:**
- Điểm dưới: H₁ = {H1}m → V₁ = {V1} triệu m³
- Điểm trên: H₂ = {H2}m → V₂ = {V2} triệu m³

**Công thức nội suy:**

$$
V = V_1 + (V_2 - V_1) \\times \\frac{{H - H_1}}{{H_2 - H_1}}
$$

**Áp dụng:**

$$
V = {V1} + ({V2} - {V1}) \\times \\frac{{{H} - {H1}}}{{{H2} - {H1}}}
$$

$$
V = {V1} + {V2 - V1:.3f} \\times \\frac{{{H - H1:.2f}}}{{{H2 - H1:.2f}}}
$$

$$
V = {V:.3f} \\text{{ triệu m³}}
$$

---

#### 📌 Kết quả

**Dung tích tại mực nước {H}m: {V:.3f} triệu m³**

*(Nội suy tuyến tính giữa {H1}m và {H2}m)*
""".strip()

        else:  # nearest
            response = f"""
### Tra cứu dung tích hồ {reservoir}

**Mực nước:** {H}m

**Lưu ý:** Không thể nội suy (chỉ có điểm ở một phía). Sử dụng giá trị gần nhất.

**Kết quả:** {V} triệu m³ (từ mực nước {H1}m)
""".strip()

        return response

    except Exception as e:
        error_msg = f"Error querying water level: {str(e)}"
        print(f"❌ {error_msg}", flush=True)
        return error_msg


def calculate_volume_difference(start_level, end_level, reservoir="Sông Hinh"):
    """
    Calculate volume difference between two water levels

    Args:
        start_level: Starting water level (m)
        end_level: Ending water level (m)
        reservoir: Reservoir name (default: "Sông Hinh")

    Returns:
        String with volume difference calculation (markdown formatted)
    """
    print(f"📊 VOLUME DIFFERENCE TOOL: {start_level}m → {end_level}m at {reservoir}", flush=True)

    try:
        start_level = float(start_level)
        end_level = float(end_level)

        # Get volumes for both levels
        start_result = interpolate_water_volume(start_level, reservoir)
        end_result = interpolate_water_volume(end_level, reservoir)

        if not start_result:
            return f"Không tìm thấy dữ liệu cho mực nước {start_level}m"

        if not end_result:
            return f"Không tìm thấy dữ liệu cho mực nước {end_level}m"

        V_start = start_result['V']
        V_end = end_result['V']
        volume_diff = V_end - V_start

        method_start = start_result['method']
        method_end = end_result['method']

        print(f"✓ V({start_level}m) = {V_start:.3f} triệu m³, V({end_level}m) = {V_end:.3f} triệu m³, ΔV = {volume_diff:.3f} triệu m³", flush=True)

        # Determine direction
        if volume_diff > 0:
            direction = "tăng"
            action = "cần thêm"
        else:
            direction = "giảm"
            action = "cần xả"
            volume_diff = abs(volume_diff)

        result = f"""
### Tính chênh lệch dung tích hồ {reservoir}

**Yêu cầu:** Tính dung tích giữa hai mực nước **{start_level}m** và **{end_level}m**

---

#### 📊 Bước 1: Tra cứu dung tích từng mực nước

**Mực nước {start_level}m:**
- Dung tích: **{V_start} triệu m³**
- Phương pháp: {method_start}

**Mực nước {end_level}m:**
- Dung tích: **{V_end} triệu m³**
- Phương pháp: {method_end}

---

#### ⚖️ Bước 2: Tính chênh lệch

**Công thức:**

$$
\\Delta V = V_{{end}} - V_{{start}}
$$

**Thay số:**

$$
\\Delta V = {V_end} - {V_start} = {volume_diff if V_end >= V_start else -volume_diff:.3f} \\text{{ triệu m³}}
$$

---

#### 📌 Kết quả

| Thông số | Giá trị |
|----------|---------|
| **Mực nước bắt đầu** | {start_level}m |
| **Dung tích tại {start_level}m** | **{V_start} triệu m³** |
| **Mực nước kết thúc** | {end_level}m |
| **Dung tích tại {end_level}m** | **{V_end} triệu m³** |
| **Chênh lệch mực nước** | {abs(end_level - start_level):.2f}m ({direction}) |
| **Chênh lệch dung tích (ΔV)** | **{volume_diff:.3f} triệu m³** |

**✅ Kết luận:** Để mực nước {direction} từ {start_level}m đến {end_level}m, {action} **{volume_diff:.3f} triệu m³** nước.

**📝 Lưu ý:**
- 1 triệu m³ = 1,000,000 m³
- Thể tích này tương đương với: {volume_diff * 1000:.0f} ngàn m³ = {volume_diff * 1_000_000:.0f} m³
""".strip()

        return result

    except Exception as e:
        return f"Lỗi khi tính chênh lệch dung tích: {str(e)}"
