"""
Flow rate calculation functions
"""

from thuyvan_data_client import interpolate_water_volume
from .interpolation import interpolate_water_level_from_volume


def calculate_time_needed(start_level, end_level, inflow_rate=0, discharge_rate=0, reservoir="Sông Hinh"):
    """
    Calculate time needed to change water level given flow rates

    Args:
        start_level: Starting water level (m)
        end_level: Target water level (m)
        inflow_rate: Water inflow rate (m³/s), default 0
        discharge_rate: Water discharge/outflow rate (m³/s), default 0
        reservoir: Reservoir name (default: "Sông Hinh")

    Returns:
        String with time calculation
    """
    print(f"⏱️ TIME CALCULATION TOOL: {start_level}m → {end_level}m, inflow={inflow_rate} m³/s, discharge={discharge_rate} m³/s at {reservoir}", flush=True)

    try:
        start_level = float(start_level)
        end_level = float(end_level)
        inflow_rate = float(inflow_rate)
        discharge_rate = float(discharge_rate)

        # Get volumes
        start_result = interpolate_water_volume(start_level, reservoir)
        end_result = interpolate_water_volume(end_level, reservoir)

        if not start_result or not end_result:
            return "Không tìm thấy dữ liệu mực nước"

        start_volume = start_result['V']  # triệu m³
        end_volume = end_result['V']
        volume_change = end_volume - start_volume  # triệu m³

        # Net flow rate (positive = filling, negative = draining)
        net_flow_m3s = inflow_rate - discharge_rate  # m³/s

        if net_flow_m3s == 0:
            return "Lỗi: Lưu lượng thuần bằng 0 (lưu lượng về = lưu lượng xả), mực nước không thay đổi!"

        # Check if flow direction matches level change
        if (volume_change > 0 and net_flow_m3s < 0) or (volume_change < 0 and net_flow_m3s > 0):
            return "Lỗi: Hướng lưu lượng không khớp với hướng thay đổi mực nước!"

        # Calculate time
        # volume_change (triệu m³) = net_flow (m³/s) * time (s) / 1,000,000
        # time (s) = volume_change * 1,000,000 / net_flow
        time_seconds = abs(volume_change) * 1_000_000 / abs(net_flow_m3s)
        time_hours = time_seconds / 3600
        time_days = time_seconds / 86400

        # Format nicely
        if time_days >= 1:
            time_str = f"{time_days:.2f} ngày ({time_hours:.1f} giờ)"
        else:
            time_str = f"{time_hours:.1f} giờ"

        direction = "tăng" if volume_change > 0 else "giảm"

        result = f"""
### ⏱️ Tính toán thời gian {direction} mực nước hồ {reservoir}

**Yêu cầu:** Mực nước {direction} từ **{start_level}m** đến **{end_level}m**

**Điều kiện:**
- Lưu lượng về hồ: {inflow_rate:.2f} m³/s
- Lưu lượng xả: {discharge_rate:.2f} m³/s
- Lưu lượng thuần: {net_flow_m3s:.2f} m³/s

---

#### 📌 Kết quả

| Thông số | Giá trị |
|----------|---------|
| Mực nước bắt đầu | {start_level}m (V = {start_volume:.3f} triệu m³) |
| Mực nước kết thúc | {end_level}m (V = {end_volume:.3f} triệu m³) |
| Thể tích thay đổi | {abs(volume_change):.3f} triệu m³ ({direction}) |
| Lưu lượng về | {inflow_rate:.2f} m³/s |
| Lưu lượng xả | {discharge_rate:.2f} m³/s |
| Lưu lượng thuần | {abs(net_flow_m3s):.2f} m³/s |
| **Thời gian cần thiết** | **{time_str}** |

**✅ Kết luận:** Với lưu lượng thuần {abs(net_flow_m3s):.2f} m³/s, mực nước sẽ {direction} từ {start_level}m đến {end_level}m trong **{time_str}**

---

#### 📐 Công thức giải thích

**Bước 1: Thể tích cần thay đổi**

$$
\\Delta V = V_{{end}} - V_{{start}} = {end_volume:.3f} - {start_volume:.3f} = {volume_change:.3f} \\text{{ triệu m³}}
$$

**Bước 2: Tính thời gian**

$$
t = \\frac{{|\\Delta V|}}{{|Q_{{thuần}}|}} = \\frac{{{abs(volume_change):.3f} \\times 10^6}}{{{abs(net_flow_m3s):.2f}}} = {time_seconds:.0f} \\text{{ giây}} = {time_hours:.2f} \\text{{ giờ}} = {time_days:.3f} \\text{{ ngày}}
$$
""".strip()

        return result

    except Exception as e:
        return f"Lỗi khi tính toán thời gian: {str(e)}"


def calculate_level_change(qve, qcm, time_days, start_level, reservoir="Sông Hinh"):
    """
    Tính mực nước hồ sau một khoảng thời gian với Qve và Qcm cho trước.
    Trả lời câu hỏi: "Với Qve = X, Qcm = Y trong Z ngày thì mực nước từ H xuống/tăng bao nhiêu?"

    Args:
        qve: Lưu lượng về hồ (Qve) m³/s
        qcm: Lưu lượng chạy máy / xả (Qcm) m³/s
        time_days: Thời gian (ngày), có thể thập phân (vd: 5.5)
        start_level: Mực nước ban đầu (m)
        reservoir: Tên hồ (mặc định "Sông Hinh")

    Returns:
        Chuỗi báo cáo: mực nước cuối, độ giảm/tăng (m).
    """
    print(
        f"📉 LEVEL CHANGE TOOL: Qve={qve} m³/s, Qcm={qcm} m³/s, {time_days} ngày, từ {start_level}m tại {reservoir}",
        flush=True,
    )
    try:
        qve = float(qve)
        qcm = float(qcm)
        time_days = float(time_days)
        start_level = float(start_level)

        start_result = interpolate_water_volume(start_level, reservoir)
        if not start_result:
            return f"Không tìm thấy dữ liệu mực nước cho {start_level}m tại {reservoir}."

        start_volume = start_result["V"]  # triệu m³

        # Lưu lượng thuần: dương = nước vào, âm = nước ra
        net_flow_m3s = qve - qcm  # m³/s
        time_seconds = time_days * 86400
        # ΔV (triệu m³) = net_flow (m³/s) * time (s) / 1e6
        volume_change_million = net_flow_m3s * time_seconds / 1_000_000
        end_volume = start_volume + volume_change_million

        if end_volume < 0:
            return (
                f"Lỗi: Thể tích cuối âm ({end_volume:.3f} triệu m³). "
                f"Qve={qve} m³/s, Qcm={qcm} m³/s trong {time_days} ngày xả ra quá nhiều so với dung tích ban đầu."
            )

        # Tra mực nước cuối từ dung tích cuối; dùng hint_level=start_level để lấy bản ghi quanh vùng mực nước đúng
        end_level_interp = interpolate_water_level_from_volume(
            end_volume, reservoir, hint_level=start_level
        )
        if end_level_interp is None:
            return f"Không tra được mực nước tương ứng với dung tích {end_volume:.3f} triệu m³ tại {reservoir}."

        level_change_raw = end_level_interp - start_level
        # Xác định hướng theo lưu lượng thuần: Qve < Qcm → xả nhiều hơn về → mực nước giảm
        if net_flow_m3s < 0:
            direction = "giảm"
            reason = f"Do Qve ({qve}) < Qcm ({qcm}) nên lưu lượng thuần âm → mực nước hồ **giảm**."
            abs_change = abs(level_change_raw)
            end_level = start_level - abs_change
        elif net_flow_m3s > 0:
            direction = "tăng"
            reason = f"Do Qve ({qve}) > Qcm ({qcm}) nên lưu lượng thuần dương → mực nước hồ **tăng**."
            abs_change = abs(level_change_raw)
            end_level = start_level + abs_change
        else:
            direction = "không đổi"
            reason = "Qve = Qcm nên lưu lượng thuần bằng 0 → mực nước hồ không đổi."
            abs_change = 0.0
            end_level = start_level

        # Tốc độ: cm/ngày và cm/giờ (chỉ khi có thay đổi)
        time_hours = time_days * 24
        cm_per_day = (abs_change * 100) / time_days if time_days else 0
        cm_per_hour = (abs_change * 100) / time_hours if time_hours else 0

        result = f"""
### 📉 Thay đổi mực nước hồ {reservoir}

**Câu hỏi:** Với Qve = **{qve} m³/s** và Qcm = **{qcm} m³/s** trong **{time_days} ngày**, mực nước từ **{start_level}m** sẽ {direction} bao nhiêu?

**Giải thích:** {reason}

---

#### 📌 Kết quả

| Thông số | Giá trị |
|----------|---------|
| Mực nước ban đầu | {start_level}m (V = {start_volume:.3f} triệu m³) |
| Qve (lưu lượng về) | {qve:.2f} m³/s |
| Qcm (lưu lượng chạy máy) | {qcm:.2f} m³/s |
| Lưu lượng thuần | {net_flow_m3s:.2f} m³/s |
| Thời gian | {time_days} ngày |
| Thể tích thay đổi | {volume_change_million:+.3f} triệu m³ |
| Mực nước cuối | **{end_level:.2f}m** (V = {end_volume:.3f} triệu m³) |
| **Mực nước {direction}** | **{abs_change:.2f}m** |
| Mỗi ngày {direction} | **{cm_per_day:.2f} cm/ngày** |
| Mỗi giờ {direction} | **{cm_per_hour:.2f} cm/giờ** |

**✅ Kết luận:** Với Qve = {qve} m³/s và Qcm = {qcm} m³/s trong {time_days} ngày, mực nước hồ {reservoir} từ **{start_level}m** sẽ **{direction} {abs_change:.2f}m**, còn **{end_level:.2f}m** (trung bình **{cm_per_day:.2f} cm/ngày**, **{cm_per_hour:.2f} cm/giờ**).

---

#### 📐 Công thức giải thích

**Bước 1: Thể tích và lưu lượng thuần**

- Dung tích tại mực nước ban đầu **{start_level}m**: **{start_volume:.3f} triệu m³**
- Lưu lượng thuần: Qve − Qcm = {qve} − {qcm} = **{net_flow_m3s:.2f} m³/s** (âm = nước ra nhiều hơn vào → mực nước giảm)

**Bước 2: Thể tích thay đổi sau {time_days} ngày**

$$
\\Delta V = Q_{{thuần}} \\times t = {net_flow_m3s:.2f} \\times ({time_days} \\times 86400) = {volume_change_million:.3f} \\text{{ triệu m³}}
$$

- Dung tích cuối: {start_volume:.3f} + ({volume_change_million:.3f}) = **{end_volume:.3f} triệu m³**
""".strip()
        return result

    except Exception as e:
        return f"Lỗi khi tính thay đổi mực nước: {str(e)}"


def calculate_flow_rate(start_level, end_level, time_days, discharge_rate=None, reservoir="Sông Hinh"):
    """
    Calculate flow rate needed to go from start_level to end_level in given time
    Uses linear interpolation for accurate volume calculation
    Accounts for discharge/outflow if provided

    Args:
        start_level: Starting water level (m)
        end_level: Target water level (m)
        time_days: Time period in days
        discharge_rate: Optional discharge/outflow rate (m³/s)
        reservoir: Reservoir name (default: "Sông Hinh")

    Returns:
        String with flow rate calculation
    """
    discharge_info = f", discharge={discharge_rate} m³/s" if discharge_rate else ""
    print(f"🔍 FLOW RATE TOOL CALLED: {start_level}m → {end_level}m in {time_days} days{discharge_info} at {reservoir}", flush=True)

    try:
        start_level = float(start_level)
        end_level = float(end_level)
        time_days = float(time_days)

        # Get volumes using interpolation
        start_result = interpolate_water_volume(start_level, reservoir)
        end_result = interpolate_water_volume(end_level, reservoir)

        if not start_result:
            return f"Không tìm thấy dữ liệu cho mực nước bắt đầu {start_level}m"

        if not end_result:
            return f"Không tìm thấy dữ liệu cho mực nước kết thúc {end_level}m"

        start_volume = start_result['V']
        end_volume = end_result['V']

        if start_volume is None:
            return f"Không tìm thấy dữ liệu cho mực nước bắt đầu {start_level}m"

        if end_volume is None:
            return f"Không tìm thấy dữ liệu cho mực nước kết thúc {end_level}m"

        # Calculate volume difference
        volume_diff = end_volume - start_volume

        # Calculate water level change rate
        level_change = end_level - start_level  # meters
        time_hours = time_days * 24  # hours

        # Rate per hour
        rate_per_hour_m = level_change / time_hours  # m/h
        rate_per_hour_cm = rate_per_hour_m * 100  # cm/h
        rate_per_hour_mm = rate_per_hour_m * 1000  # mm/h

        # Rate per day
        rate_per_day_m = level_change / time_days  # m/day
        rate_per_day_cm = rate_per_day_m * 100  # cm/day

        # Calculate net flow rate (without discharge)
        flow_per_day_net = volume_diff / time_days  # million m³/day
        flow_per_second_net = (flow_per_day_net * 1_000_000) / 86400  # m³/s

        # Handle discharge rate if provided
        if discharge_rate is not None:
            discharge_rate = float(discharge_rate)
            # Convert discharge to million m³/day
            discharge_per_day = (discharge_rate * 86400) / 1_000_000
            discharge_total = discharge_per_day * time_days  # Total discharge volume
        else:
            discharge_rate = 0
            discharge_per_day = 0
            discharge_total = 0

        # Calculate actual inflow needed (water balance)
        # Q_in = Q_net + Q_out
        flow_per_day = flow_per_day_net + discharge_per_day
        flow_m3_per_second = flow_per_second_net + discharge_rate

        if discharge_rate > 0 and flow_m3_per_second < 0:
            action_name = "giảm" if volume_diff < 0 else "tăng"
            return f"⚠️ **Không khả thi:** Để {action_name} mực nước về {end_level}m trong {time_days} ngày, lưu lượng xả hiện tại ({discharge_rate:.2f} m³/s) là quá nhỏ so với tốc độ thay đổi mực nước yêu cầu. Cần lưu lượng xả tối thiểu là {abs(flow_per_second_net):.2f} m³/s khi lưu lượng về bằng 0. Vui lòng tăng lưu lượng xả hoặc kéo dài thời gian."

        print(f"✓ Calculation: {end_volume} - {start_volume} = {volume_diff} triệu m³", flush=True)
        if discharge_rate > 0:
            print(f"✓ Net flow: {flow_per_second_net:.2f} m³/s + Discharge: {discharge_rate:.2f} m³/s", flush=True)
            print(f"✓ Total inflow needed: {flow_m3_per_second:.2f} m³/s", flush=True)
        else:
            print(f"✓ Flow rate: {flow_m3_per_second:.2f} m³/s", flush=True)

        # Create detailed response
        if volume_diff > 0:
            action = "tăng"
            direction = "vào"
        else:
            action = "giảm"
            direction = "ra khỏi"
            volume_diff = abs(volume_diff)
            flow_per_day = abs(flow_per_day)
            flow_per_day_net = abs(flow_per_day_net)
            flow_m3_per_second = abs(flow_m3_per_second)
            flow_per_second_net = abs(flow_per_second_net)

        # Build result based on whether discharge is included
        if discharge_rate > 0:
            result = f"""
### Tính toán lưu lượng về hồ (có xả)

**Yêu cầu:** Mực nước {action} từ **{start_level}m** đến **{end_level}m** trong **{time_days} ngày**

**Điều kiện:** Lưu lượng xả (chạy máy) = **{discharge_rate:.2f} m³/s**

---

#### 📌 Kết quả

| Thông số | Giá trị |
|----------|---------|
| Mực nước bắt đầu | {start_level}m (V = {start_volume} triệu m³) |
| Mực nước kết thúc | {end_level}m (V = {end_volume} triệu m³) |
| Thể tích thay đổi | {volume_diff:.3f} triệu m³ |
| Thời gian | {time_days:.3f} ngày ({time_hours:.2f} giờ) |
| **Tốc độ {action} mực nước** | **{abs(rate_per_hour_cm):.3f} cm/giờ** ({abs(rate_per_hour_mm):.2f} mm/giờ) |
| | **{abs(rate_per_day_cm):.3f} cm/ngày** ({abs(rate_per_day_m):.4f} m/ngày) |
| Lưu lượng xả (chạy máy) | {discharge_rate:.2f} m³/s |
| Lưu lượng thuần | {flow_per_second_net:.2f} m³/s |
| **Lưu lượng về hồ cần thiết** | **{flow_m3_per_second:.2f} m³/s** |
| | **{flow_per_day:.3f} triệu m³/ngày** |

---

#### 📐 Công thức giải thích

**Bước 1: Thể tích cần thay đổi**

$$
\\Delta V = V_{{end}} - V_{{start}} = {end_volume} - {start_volume} = {volume_diff:.3f} \\text{{ triệu m³}}
$$

**Bước 2: Tốc độ thay đổi mực nước** — {abs(level_change):.3f}m trong {time_days:.3f} ngày → {abs(rate_per_hour_cm):.3f} cm/giờ, {abs(rate_per_day_cm):.3f} cm/ngày

**Bước 3: Cân bằng nước** — Q_về = Q_thuần + Q_xả

**Bước 4: Tính toán** — Q_thuần = ΔV/t = {flow_per_second_net:.2f} m³/s; Q_xả = {discharge_rate:.2f} m³/s → **Q_về = {flow_m3_per_second:.2f} m³/s**
""".strip()
        else:
            result = f"""
### Tính toán lưu lượng {direction} hồ

**Yêu cầu:** Mực nước {action} từ **{start_level}m** đến **{end_level}m** trong **{time_days} ngày**

---

#### 📌 Kết quả

| Thông số | Giá trị |
|----------|---------|
| Mực nước bắt đầu | {start_level}m (V = {start_volume} triệu m³) |
| Mực nước kết thúc | {end_level}m (V = {end_volume} triệu m³) |
| Thể tích thay đổi | **{volume_diff:.3f} triệu m³** |
| Thời gian | {time_days:.3f} ngày ({time_hours:.2f} giờ) |
| **Tốc độ {action} mực nước** | **{abs(rate_per_hour_cm):.3f} cm/giờ** ({abs(rate_per_hour_mm):.2f} mm/giờ) |
| | **{abs(rate_per_day_cm):.3f} cm/ngày** ({abs(rate_per_day_m):.4f} m/ngày) |
| **Lưu lượng {direction} hồ** | **{flow_m3_per_second:.2f} m³/s** |
| | **{flow_per_day:.3f} triệu m³/ngày** |

---

#### 📐 Công thức giải thích

**Bước 1: Thể tích cần thay đổi** — ΔV = V_end − V_start = {volume_diff:.3f} triệu m³

**Bước 2: Tốc độ thay đổi mực nước** — {abs(level_change):.3f}m trong {time_days:.3f} ngày → {abs(rate_per_hour_cm):.3f} cm/giờ, {abs(rate_per_day_cm):.3f} cm/ngày

**Bước 3: Lưu lượng trung bình** — Q = ΔV/t = {flow_per_day:.3f} triệu m³/ngày = **{flow_m3_per_second:.2f} m³/s**
""".strip()

        return result

    except Exception as e:
        error_msg = f"Lỗi khi tính toán lưu lượng: {str(e)}"
        print(f"❌ {error_msg}", flush=True)
        return error_msg



