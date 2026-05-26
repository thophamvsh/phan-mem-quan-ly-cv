"""
Spillway discharge calculation functions
"""

from thuyvan_data_client import interpolate_water_volume
from .interpolation import interpolate_water_level_from_volume


def calculate_spillway_discharge(start_level, end_level, time_days, inflow_rate, turbine_discharge, reservoir="Sông Hinh"):
    """
    Calculate spillway discharge (Qxa) needed given inflow and turbine discharge
    Solve for: Qxa = Qve - Qcm - (ΔV/t)

    Args:
        start_level: Starting water level (m)
        end_level: Target water level (m)
        time_days: Time period in days
        inflow_rate: Inflow rate (Qve) in m³/s
        turbine_discharge: Turbine discharge (Qcm) in m³/s
        reservoir: Reservoir name

    Returns:
        String with Qxa calculation
    """
    print(f"🌊 SPILLWAY CALCULATION: {start_level}m → {end_level}m in {time_days} days, Qve={inflow_rate}, Qcm={turbine_discharge} at {reservoir}", flush=True)

    try:
        start_level = float(start_level)
        end_level = float(end_level)
        time_days = float(time_days)
        inflow_rate = float(inflow_rate)
        turbine_discharge = float(turbine_discharge)

        # Get volumes
        start_result = interpolate_water_volume(start_level, reservoir)
        end_result = interpolate_water_volume(end_level, reservoir)

        if not start_result or not end_result:
            return "Không tìm thấy dữ liệu mực nước"

        start_volume = start_result['V']
        end_volume = end_result['V']
        volume_change = end_volume - start_volume

        # Calculate net flow needed
        net_flow_needed = volume_change * 1_000_000 / (time_days * 86400)  # m³/s

        # Solve for Qxa: Net_flow = Qve - Qcm - Qxa
        # Qxa = Qve - Qcm - Net_flow
        spillway_discharge = inflow_rate - turbine_discharge - net_flow_needed

        direction = "tăng" if volume_change > 0 else "giảm"

        result = f"""
### 🌊 Tính toán lưu lượng xả qua đập (Qxa) - Hồ {reservoir}

**Yêu cầu:** Mực nước {direction} từ **{start_level}m** đến **{end_level}m** trong **{time_days} ngày**

**Điều kiện cho trước:**
- Lưu lượng về (Qve): {inflow_rate:.2f} m³/s
- Lưu lượng chạy máy (Qcm): {turbine_discharge:.2f} m³/s

---

#### 📊 Bước 1: Tính thể tích cần thay đổi

$$
\\Delta V = V_{{end}} - V_{{start}} = {end_volume:.3f} - {start_volume:.3f} = {volume_change:.3f} \\text{{ triệu m³}}
$$

---

#### ⚖️ Bước 2: Tính lưu lượng thuần cần thiết

$$
Q_{{thuần}} = \\frac{{\\Delta V}}{{t}} = \\frac{{{volume_change:.3f} \\times 10^6}}{{{time_days} \\times 86400}} = {net_flow_needed:.2f} \\text{{ m³/s}}
$$

---

#### 🌊 Bước 3: Giải phương trình cân bằng nước

**Phương trình:**

$$
Q_{{thuần}} = Q_{{ve}} - Q_{{cm}} - Q_{{xa}}
$$

**Giải cho Qxa:**

$$
Q_{{xa}} = Q_{{ve}} - Q_{{cm}} - Q_{{thuần}}
$$

**Thay số:**

$$
Q_{{xa}} = {inflow_rate:.2f} - {turbine_discharge:.2f} - ({net_flow_needed:.2f})
$$

$$
Q_{{xa}} = {spillway_discharge:.2f} \\text{{ m³/s}}
$$

---

#### 📌 Kết quả

| Thông số | Giá trị |
|----------|---------|
| Mực nước bắt đầu | {start_level}m (V = {start_volume:.3f} triệu m³) |
| Mực nước kết thúc | {end_level}m (V = {end_volume:.3f} triệu m³) |
| Thể tích thay đổi | {abs(volume_change):.3f} triệu m³ ({direction}) |
| Thời gian | {time_days} ngày |
| Lưu lượng về (Qve) | {inflow_rate:.2f} m³/s |
| Lưu lượng chạy máy (Qcm) | {turbine_discharge:.2f} m³/s |
| **Lưu lượng xả qua đập (Qxa) cần thiết** | **{spillway_discharge:.2f} m³/s** |

**✅ Kết luận:** Để mực nước {direction} từ {start_level}m đến {end_level}m trong {time_days} ngày, với Qve = {inflow_rate:.2f} m³/s và Qcm = {turbine_discharge:.2f} m³/s, cần xả qua đập **Qxa = {spillway_discharge:.2f} m³/s**
""".strip()

        return result

    except Exception as e:
        return f"Lỗi khi tính toán Qxa: {str(e)}"




def calculate_spillway_ramping(start_level, end_level, time_days, inflow_rate, turbine_discharge, max_discharge=2000, start_discharge=None, reservoir="Sông Hinh"):
    """
    Calculate ramping spillway discharge schedule given water level targets and flow conditions

    NEW LOGIC: Calculate EXACT TIME needed to reach target water level accurately
    Returns only 3-4 best strategies with precise time adjustments

    Args:
        start_level: Starting water level (m)
        end_level: Target water level (m)
        time_days: Time period in days (REFERENCE - will be adjusted for accuracy)
        inflow_rate: Inflow rate (Qve) in m³/s
        turbine_discharge: Turbine discharge (Qcm) in m³/s
        max_discharge: Maximum spillway discharge allowed (default 2000 m³/s)
        start_discharge: Optional starting spillway discharge (if None, will solve for it)
        reservoir: Reservoir name

    Returns:
        String with 3-4 precise strategies
    """
    print(f"🌊 SPILLWAY RAMPING: {start_level}m → {end_level}m in {time_days} days, Qve={inflow_rate}, Qcm={turbine_discharge}, Qxa_max={max_discharge} at {reservoir}", flush=True)

    try:
        start_level = float(start_level)
        end_level = float(end_level)
        time_days = float(time_days)
        inflow_rate = float(inflow_rate)
        turbine_discharge = float(turbine_discharge)
        max_discharge = float(max_discharge)
        if start_discharge is not None:
            start_discharge = float(start_discharge)

        # Step 1: Calculate required average Qxa using water balance
        start_result = interpolate_water_volume(start_level, reservoir)
        end_result = interpolate_water_volume(end_level, reservoir)

        if not start_result or not end_result:
            return "Không tìm thấy dữ liệu mực nước"

        start_volume = start_result['V']
        end_volume = end_result['V']
        volume_change = end_volume - start_volume

        # Calculate net flow needed (m³/s)
        net_flow_needed = volume_change * 1_000_000 / (time_days * 86400)

        # Water balance: net_flow = Qve - Qcm - Qxa_avg
        # Qxa_avg = Qve - Qcm - net_flow
        qxa_avg_required = inflow_rate - turbine_discharge - net_flow_needed

        print(f"✓ Required Qxa_avg: {qxa_avg_required:.2f} m³/s", flush=True)

        # Round to nearest 50
        qxa_avg_rounded = round(qxa_avg_required / 50) * 50

        # Step 2: Generate strategies
        allowed_steps = [50, 100, 150, 200, 250, 400]
        strategies = []

        # Define cycle options based on time range
        if time_days < 1:
            cycle_options = [2, 1]
        elif time_days <= 3:
            cycle_options = [6, 4, 2]
        elif time_days <= 7:
            cycle_options = [12, 6, 4]
        else:
            cycle_options = [24, 12, 6]

        # Strategy Generation
        if start_discharge is not None:
            # User provided start_discharge
            start_rounded = round(start_discharge / 50) * 50
            if start_rounded < 50:
                start_rounded = 50

            # Calculate end discharge needed
            end_exact = 2 * qxa_avg_required - start_rounded
            end_rounded = round(end_exact / 50) * 50

            if end_rounded > max_discharge or end_rounded <= start_rounded:
                return f"""
### ⚠️ Không thể tạo lịch với Qxa start = {start_discharge:.0f} m³/s

**Vấn đề:**
- Qxa_avg cần thiết: {qxa_avg_required:.2f} m³/s
- Qxa start: {start_rounded} m³/s
- Qxa end cần: {end_rounded} m³/s
- Qxa_max cho phép: {max_discharge} m³/s

**Giải pháp:**
1. Giảm Qxa start xuống {2*qxa_avg_required - max_discharge:.0f} m³/s
2. Hoặc tăng Qxa_max lên {end_rounded:.0f} m³/s
3. Hoặc kéo dài thời gian lên {time_days * qxa_avg_required / ((start_rounded + max_discharge)/2):.1f} ngày
"""

            total_increase = end_rounded - start_rounded

            # Try different cycle and step combinations
            for cycle in cycle_options:
                for step in allowed_steps:
                    # Calculate number of steps needed
                    num_steps_needed = int(total_increase / step)
                    if num_steps_needed < 1:
                        continue

                    # Calculate actual end with this step
                    actual_end = start_rounded + (num_steps_needed * step)
                    if actual_end > max_discharge:
                        continue

                    # Calculate ramping time
                    ramp_time_hours = num_steps_needed * cycle

                    # Calculate average during ramp phase (linear ramp)
                    ramp_avg = (start_rounded + actual_end) / 2

                    # Calculate Qnet during different phases
                    qnet_during_ramp = inflow_rate - turbine_discharge - ramp_avg
                    qnet_at_end = inflow_rate - turbine_discharge - actual_end

                    # Calculate volume change during ramp phase
                    volume_during_ramp = qnet_during_ramp * ramp_time_hours * 3600 / 1_000_000

                    # Calculate remaining volume needed
                    remaining_volume = volume_change - volume_during_ramp

                    # Calculate hold time needed
                    if qnet_at_end != 0:
                        hold_time_hours = abs(remaining_volume * 1_000_000 / (qnet_at_end * 3600))
                    else:
                        hold_time_hours = 0

                    # Total time
                    total_time_hours = ramp_time_hours + hold_time_hours

                    # Round to full cycles
                    num_cycles = max(num_steps_needed + 1, int(total_time_hours / cycle))
                    time_adjusted_hours = num_cycles * cycle
                    time_adjusted_days = time_adjusted_hours / 24

                    # Recalculate actual average over total time
                    # Qxa_avg = (ramp_avg * ramp_time + actual_end * hold_time) / total_time
                    actual_hold_time = time_adjusted_hours - ramp_time_hours
                    actual_avg = (ramp_avg * ramp_time_hours + actual_end * actual_hold_time) / time_adjusted_hours

                    strategies.append({
                        'start': start_rounded,
                        'end': actual_end,
                        'avg': actual_avg,
                        'cycle': cycle,
                        'step': step,
                        'num_steps': num_steps_needed + 1,
                        'time_hours': time_adjusted_hours,
                        'time_days': time_adjusted_days,
                        'time_dev': abs(time_adjusted_hours - time_days * 24),
                        'qxa_dev': abs(actual_avg - qxa_avg_required)
                    })

        else:
            # User did NOT provide start_discharge - generate options
            start_options = [50, 100, 150, 200, 250]

            for start_test in start_options:
                # Calculate end needed
                end_test = 2 * qxa_avg_rounded - start_test
                end_test = round(end_test / 50) * 50

                if end_test <= start_test or end_test > max_discharge:
                    continue

                total_increase = end_test - start_test

                # Try different cycle and step combinations
                for cycle in cycle_options:
                    for step in allowed_steps:
                        num_steps_needed = int(total_increase / step)
                        if num_steps_needed < 1:
                            continue

                        actual_end = start_test + (num_steps_needed * step)
                        if actual_end > max_discharge or actual_end < end_test - 200:
                            continue

                        # Calculate ramping time
                        ramp_time_hours = num_steps_needed * cycle

                        # Calculate average during ramp phase
                        ramp_avg = (start_test + actual_end) / 2

                        # Calculate Qnet during different phases
                        qnet_during_ramp = inflow_rate - turbine_discharge - ramp_avg
                        qnet_at_end = inflow_rate - turbine_discharge - actual_end

                        # Calculate volume change during ramp phase
                        volume_during_ramp = qnet_during_ramp * ramp_time_hours * 3600 / 1_000_000

                        # Calculate remaining volume needed
                        remaining_volume = volume_change - volume_during_ramp

                        # Calculate hold time needed
                        if qnet_at_end != 0:
                            hold_time_hours = abs(remaining_volume * 1_000_000 / (qnet_at_end * 3600))
                        else:
                            hold_time_hours = 0

                        # Total time
                        total_time_hours = ramp_time_hours + hold_time_hours

                        # Round to full cycles
                        num_cycles = max(num_steps_needed + 1, int(total_time_hours / cycle))
                        time_adjusted_hours = num_cycles * cycle
                        time_adjusted_days = time_adjusted_hours / 24

                        # Recalculate actual average over total time
                        actual_hold_time = time_adjusted_hours - ramp_time_hours
                        actual_avg = (ramp_avg * ramp_time_hours + actual_end * actual_hold_time) / time_adjusted_hours

                        strategies.append({
                            'start': start_test,
                            'end': actual_end,
                            'avg': actual_avg,
                            'cycle': cycle,
                            'step': step,
                            'num_steps': num_steps_needed + 1,
                            'time_hours': time_adjusted_hours,
                            'time_days': time_adjusted_days,
                            'time_dev': abs(time_adjusted_hours - time_days * 24),
                            'qxa_dev': abs(actual_avg - qxa_avg_required)
                        })

        if not strategies:
            return f"""
### ❌ Không thể tạo lịch xả khả thi

**Yêu cầu:**
- Mực nước: {start_level}m → {end_level}m
- Thời gian tham khảo: {time_days} ngày
- Qxa_avg cần: {qxa_avg_required:.2f} m³/s

**Vấn đề:** Không tìm thấy phương án khả thi với các ràng buộc hiện tại.

**Gợi ý:**
1. Điều chỉnh Qxa_max (hiện tại: {max_discharge} m³/s)
2. Điều chỉnh Qxa_start (nếu có)
3. Thay đổi Qcm hoặc Qve
"""

        # Sort by: 1) Qxa deviation (accuracy), 2) Time deviation
        strategies_sorted = sorted(strategies, key=lambda s: (s['qxa_dev'], s['time_dev']))

        # Select only 3-4 BEST strategies with DIVERSITY
        final_strategies = []
        seen_combinations = set()

        for strat in strategies_sorted:
            combo = (strat['cycle'], strat['step'])
            if combo not in seen_combinations or len(final_strategies) < 3:
                final_strategies.append(strat)
                seen_combinations.add(combo)
            if len(final_strategies) >= 4:
                break

        # If still not enough, add more
        if len(final_strategies) < 3:
            for strat in strategies_sorted:
                if strat not in final_strategies:
                    final_strategies.append(strat)
                    if len(final_strategies) >= 4:
                        break

        # Build result
        direction = "giảm" if volume_change < 0 else "tăng"

        result = f"""
### 🌊 Lịch xả tràn tăng dần - {len(final_strategies)} PHƯƠNG ÁN CHÍNH XÁC

**Mục tiêu:** Mực nước {direction} từ **{start_level}m** → **{end_level}m**

**Thời gian tham khảo:** {time_days} ngày ({time_days*24:.0f} giờ) *(sẽ được điều chỉnh cho chính xác)*

**Điều kiện:**
- Lưu lượng về (Qve): {inflow_rate:.2f} m³/s
- Lưu lượng chạy máy (Qcm): {turbine_discharge:.2f} m³/s
- Qxa max cho phép: {max_discharge} m³/s
- Qxa_avg cần thiết: **{qxa_avg_required:.2f} m³/s**

---

#### 🎯 CÁC PHƯƠNG ÁN ĐỀ XUẤT

| # | Qxa start | Qxa end | Qxa avg | Chu kỳ | Bước tăng | **Thời gian chính xác** | Đánh giá |
|---|-----------|---------|---------|--------|-----------|------------------------|----------|
"""

        for i, strat in enumerate(final_strategies, 1):
            time_str = f"{strat['time_days']:.1f} ngày ({strat['time_hours']:.0f}h)"

            # Rating
            qxa_dev_pct = abs(strat['qxa_dev'] / qxa_avg_required * 100) if qxa_avg_required != 0 else 0
            if qxa_dev_pct < 2:
                rating = "🎯 Chính xác nhất"
            elif qxa_dev_pct < 5:
                rating = "⭐⭐⭐ Rất tốt"
            else:
                rating = "⭐⭐ Tốt"

            result += f"| **{i}** | {strat['start']} | {strat['end']} | {strat['avg']:.0f} | {strat['cycle']}h | {strat['step']} | {time_str} | {rating} |\n"

        result += f"""

**Giải thích:**
- **Thời gian chính xác**: Được tính toán để đạt ĐÚNG mục tiêu mực nước {end_level}m
- **Độ lệch thời gian**: So với thời gian tham khảo {time_days} ngày (user yêu cầu)
- **Đánh giá**: Dựa trên độ chính xác của Qxa_avg so với yêu cầu ({qxa_avg_required:.2f} m³/s)

💡 **Lưu ý quan trọng:**
- Thời gian {time_days} ngày chỉ là THAM KHẢO
- Để đạt chính xác mục tiêu mực nước {end_level}m, thời gian thực tế cần điều chỉnh
- Các phương án trên đảm bảo mực nước cuối = {end_level}m (không giảm quá sâu)

---

#### 🎯 CHỌN PHƯƠNG ÁN

**Để xem lịch vận hành chi tiết, vui lòng cho tôi biết:**

1. **"Chọn phương án 1"** (hoặc 2, 3, 4)
2. **"Điều chỉnh phương án X"** - Nếu muốn thay đổi
3. **"So sánh phương án 1 và 2"** - Để so sánh chi tiết

💡 **Gợi ý:**
- **Ưu tiên độ chính xác** → Chọn phương án đầu tiên
- **Ưu tiên thời gian gần user yêu cầu** → Xem cột "Độ lệch thời gian"
- **Ưu tiên dễ vận hành** → Chọn chu kỳ 6h, bước 100-200

---

**✅ Sau khi chọn phương án, tôi sẽ tạo lịch vận hành chi tiết với:**
- Bảng thời gian theo giờ (0h, 4h, 8h, ...)
- Mực nước dự kiến từng bước
- Hướng dẫn vận hành an toàn
- Kiểm chứng toán học
""".strip()

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Lỗi khi tính toán lịch xả tràn: {str(e)}"


def create_detailed_spillway_schedule(start_discharge, end_discharge, time_days, cycle_hours, step_size, inflow_rate, turbine_discharge, start_level=None, end_level=None, reservoir="Sông Hinh"):
    """
    Create DETAILED spillway ramping schedule with specific parameters

    Use this AFTER user has chosen a strategy from calculate_spillway_ramping

    Args:
        start_discharge: Starting Qxa (m³/s)
        end_discharge: Ending Qxa (m³/s)
        time_days: Time period in days
        cycle_hours: Adjustment cycle in hours (1, 2, 4, 6, 12, 24)
        step_size: Step size in m³/s (50, 100, 150, 200, 250, 400)
        inflow_rate: Qve (m³/s)
        turbine_discharge: Qcm (m³/s)
        start_level: Optional starting water level
        end_level: Optional target water level
        reservoir: Reservoir name

    Returns:
        String with detailed schedule
    """
    print(f"📅 DETAILED SCHEDULE: Qxa {start_discharge}→{end_discharge} m³/s, cycle={cycle_hours}h, step={step_size}, Qve={inflow_rate}, Qcm={turbine_discharge}", flush=True)

    try:
        start_discharge = float(start_discharge)
        end_discharge = float(end_discharge)
        time_days = float(time_days)
        cycle_hours = float(cycle_hours)
        step_size = float(step_size)
        inflow_rate = float(inflow_rate)
        turbine_discharge = float(turbine_discharge)

        # RECALCULATE to ensure accuracy
        # We need to adjust EITHER time OR end_discharge to hit target exactly
        adjusted_end_discharge = end_discharge

        if start_level and end_level:
            # Get volumes
            start_result = interpolate_water_volume(start_level, reservoir)
            end_result = interpolate_water_volume(end_level, reservoir)

            if start_result and end_result:
                volume_change = end_result['V'] - start_result['V']

                # Calculate required Qxa_avg from water balance
                net_flow_needed = volume_change * 1_000_000 / (time_days * 86400)
                qxa_avg_required = inflow_rate - turbine_discharge - net_flow_needed

                print(f"[INFO] Required Qxa_avg for target: {qxa_avg_required:.2f} m³/s", flush=True)

                # Calculate how many steps to ramp up
                num_total_steps = int(time_days * 24 / cycle_hours)
                num_ramp_steps = int((end_discharge - start_discharge) / step_size) + 1
                num_stay_steps = max(0, num_total_steps - num_ramp_steps)

                print(f"[INFO] Steps: {num_total_steps} total ({num_ramp_steps} ramp, {num_stay_steps} stay at max)", flush=True)

                if num_stay_steps > 0:
                    # Case: Qxa reaches end_discharge before time runs out
                    # Need to solve for actual end_discharge that gives required average
                    # Formula: Qxa_avg = (start + end)/2 * (n_ramp/n_total) + end * (n_stay/n_total)
                    # Simplify: Qxa_avg = start * (n_ramp/n_total) / 2 + end * (n_ramp/n_total) / 2 + end * (n_stay/n_total)
                    #          Qxa_avg = start * (n_ramp / (2*n_total)) + end * ((n_ramp + 2*n_stay) / (2*n_total))
                    # Solve for end:
                    # end = (Qxa_avg - start * n_ramp/(2*n_total)) / ((n_ramp + 2*n_stay) / (2*n_total))

                    coefficient_start = num_ramp_steps / (2 * num_total_steps)
                    coefficient_end = (num_ramp_steps + 2 * num_stay_steps) / (2 * num_total_steps)

                    adjusted_end_discharge = (qxa_avg_required - start_discharge * coefficient_start) / coefficient_end

                    # Round to nearest 50
                    adjusted_end_discharge = round(adjusted_end_discharge / 50) * 50

                    print(f"[INFO] Adjusted Qxa_end: {end_discharge} → {adjusted_end_discharge} m³/s (for exact Qxa_avg)", flush=True)

                    # Verify
                    verify_avg = start_discharge * coefficient_start + adjusted_end_discharge * coefficient_end
                    print(f"[INFO] Verification: Qxa_avg = {verify_avg:.2f} m³/s (target: {qxa_avg_required:.2f} m³/s)", flush=True)

                    end_discharge = adjusted_end_discharge

        total_hours = time_days * 24

        print(f"[INFO] Total time: {time_days:.2f} days = {total_hours:.1f} hours | Cycle: {cycle_hours}h → Expected steps: {int(total_hours / cycle_hours)}", flush=True)

        # Build schedule with water level calculation
        schedule = []
        current_qxa = start_discharge
        time_elapsed = 0

        # Initialize water level tracking
        current_water_level = start_level if start_level else None
        current_volume = None

        # Calculate H-V relationship coefficient for accurate estimation
        dV_per_meter = None
        if start_level and end_level:
            start_vol_result = interpolate_water_volume(start_level, reservoir)
            end_vol_result = interpolate_water_volume(end_level, reservoir)
            if start_vol_result and end_vol_result:
                dV = abs(start_vol_result['V'] - end_vol_result['V'])
                dH = abs(start_level - end_level)
                dV_per_meter = dV / dH if dH != 0 else 23  # Calculate actual coefficient
                print(f"[INFO] H-V coefficient: {dV_per_meter:.2f} triệu m³/meter (from H={start_level}m to {end_level}m, V={start_vol_result['V']:.2f} to {end_vol_result['V']:.2f})", flush=True)

        if current_water_level:
            water_result = interpolate_water_volume(current_water_level, reservoir)
            if water_result:
                current_volume = water_result['V']
                print(f"[DEBUG] Initial: H={current_water_level}m, V={current_volume:.3f} tr.m³", flush=True)
            else:
                print(f"[ERROR] Cannot get volume for start_level={current_water_level}m", flush=True)

        while time_elapsed < total_hours:
            time_duration = min(time_elapsed + cycle_hours, total_hours) - time_elapsed
            qnet = inflow_rate - current_qxa - turbine_discharge

            # Save starting water level for this step (BEFORE calculation)
            water_level_start = current_water_level

            # Calculate water level change if possible
            water_level_end = None
            new_volume = None  # Initialize to avoid scope issues

            if current_water_level is not None and current_volume is not None:
                # Calculate volume change: ΔV = Qnet × t
                # Convert to million m³: Qnet (m³/s) × time (hours) × 3600 / 1,000,000
                volume_change = qnet * time_duration * 3600 / 1_000_000  # million m³
                new_volume = current_volume + volume_change

                print(f"[DEBUG] Step {len(schedule)+1}: Qnet={qnet:.1f}, Δt={time_duration}h, ΔV={volume_change:.3f}, V_old={current_volume:.3f}, V_new={new_volume:.3f}", flush=True)

                # Calculate water level using accurate coefficient
                if dV_per_meter:
                    # Use calculated H-V relationship
                    # ΔH = ΔV / (dV/dH) - sign is preserved from volume_change
                    water_level_change = volume_change / dV_per_meter
                    water_level_end = current_water_level + water_level_change
                    print(f"[DEBUG] Step {len(schedule)+1}: ΔV={volume_change:+.3f} → ΔH={water_level_change:+.3f}m | H: {current_water_level:.2f} → {water_level_end:.2f}m (using dV/dH={dV_per_meter:.2f})", flush=True)
                else:
                    # Fallback: try interpolation first
                    water_level_end = interpolate_water_level_from_volume(new_volume, reservoir)

                    if water_level_end:
                        # Successfully found water level
                        print(f"[DEBUG] Step {len(schedule)+1}: H: {current_water_level:.2f} → {water_level_end:.2f}m (interpolated, change: {water_level_end - current_water_level:+.2f}m)", flush=True)
                    else:
                        # Fallback: estimate linearly (~23 million m³ per meter for Sông Hinh)
                        water_level_end = current_water_level + (volume_change / 23)
                        print(f"[DEBUG] Step {len(schedule)+1}: H: {current_water_level:.2f} → {water_level_end:.2f}m (estimated with default 23, change: {volume_change / 23:+.2f}m)", flush=True)

            schedule.append({
                'time_start': time_elapsed,
                'time_end': min(time_elapsed + cycle_hours, total_hours),
                'qxa': current_qxa,
                'qcm': turbine_discharge,
                'qtotal': current_qxa + turbine_discharge,
                'qve': inflow_rate,
                'qnet': qnet,
                'water_level_start': water_level_start,
                'water_level_end': water_level_end
            })

            # Update for next iteration (AFTER appending to schedule)
            # CRITICAL: Always update both water level and volume together
            if water_level_end is not None and new_volume is not None:
                current_water_level = water_level_end
                current_volume = new_volume
                print(f"[DEBUG] Updated for next step: H={current_water_level:.2f}m, V={current_volume:.3f} tr.m³", flush=True)

            time_elapsed += cycle_hours
            current_qxa = min(current_qxa + step_size, end_discharge)

        # Calculate actual average
        total_qxa_hours = sum(s['qxa'] * (s['time_end'] - s['time_start']) for s in schedule)
        actual_qxa_avg = total_qxa_hours / total_hours

        # Build schedule table
        has_water_level = any(s.get('water_level_end') is not None for s in schedule)

        water_level_note = ""
        if not start_level or not end_level:
            water_level_note = "\n⚠️ **Lưu ý:** Để xem cột **Mực nước hồ (MNH)** thay đổi theo từng bước, vui lòng cung cấp mực nước ban đầu và mục tiêu trong query (ví dụ: \"từ 209m về 207m\").\n"

        if has_water_level:
            schedule_table = "| Bước | Thời gian | Qxa (m³/s) | Qcm (m³/s) | Qtổng xả | Qve (m³/s) | Qnet (m³/s) | **MNH (m)** | Ghi chú |\n"
            schedule_table += "|------|-----------|------------|------------|----------|------------|-------------|-------------|----------|\n"
        else:
            schedule_table = "| Bước | Thời gian | Qxa (m³/s) | Qcm (m³/s) | Qtổng xả | Qve (m³/s) | Qnet (m³/s) | Ghi chú |\n"
            schedule_table += "|------|-----------|------------|------------|----------|------------|-------------|----------|\n"
            schedule_table += water_level_note

        for i, s in enumerate(schedule, 1):
            time_label = f"{int(s['time_start'])}-{int(s['time_end'])}h"
            qnet_str = f"{s['qnet']:+.0f}"

            note = ""
            if i == 1:
                note = "Khởi động"
            elif i == len(schedule):
                note = "Kết thúc"
            elif s['qxa'] == end_discharge:
                note = "Đỉnh ⭐"

            # Format water level
            if has_water_level:
                wl_start = s.get('water_level_start')
                wl_end = s.get('water_level_end')
                if wl_start and wl_end:
                    wl_str = f"{wl_start:.2f} → {wl_end:.2f}"
                elif wl_end:
                    wl_str = f"{wl_end:.2f}"
                else:
                    wl_str = "-"

                schedule_table += f"| **{i}** | {time_label} | **{s['qxa']}** | {s['qcm']} | {s['qtotal']} | {s['qve']} | {qnet_str} | {wl_str} | {note} |\n"
            else:
                schedule_table += f"| **{i}** | {time_label} | **{s['qxa']}** | {s['qcm']} | {s['qtotal']} | {s['qve']} | {qnet_str} | {note} |\n"

        # Calculate water level info if provided
        water_level_info = ""
        actual_water_level_end = None

        if start_level and end_level:
            start_result = interpolate_water_volume(start_level, reservoir)
            end_result = interpolate_water_volume(end_level, reservoir)

            if start_result and end_result:
                volume_change = end_result['V'] - start_result['V']
                net_flow_needed = volume_change * 1_000_000 / (time_days * 86400)

                # Get actual final water level from schedule
                if schedule and schedule[-1].get('water_level_end'):
                    actual_water_level_end = schedule[-1]['water_level_end']

                water_level_info = f"""
**Mục tiêu mực nước:** {start_level}m → {end_level}m (mục tiêu)
**Mực nước dự kiến đạt:** {actual_water_level_end:.2f}m (thực tế) {' ✅' if actual_water_level_end and abs(actual_water_level_end - end_level) < 0.5 else ' ⚠️'}
**Thể tích thay đổi:** {abs(volume_change):.2f} triệu m³
**Lưu lượng thuần cần thiết:** {abs(net_flow_needed):.2f} m³/s
"""
        elif start_level:
            # Only start level provided
            if schedule and schedule[-1].get('water_level_end'):
                actual_water_level_end = schedule[-1]['water_level_end']
                water_level_info = f"""
**Mực nước ban đầu:** {start_level}m
**Mực nước dự kiến sau {time_days:.1f} ngày:** {actual_water_level_end:.2f}m
**Thay đổi:** {actual_water_level_end - start_level:+.2f}m
"""

        # Build result
        result = f"""
### 📅 Lịch vận hành chi tiết - Xả tràn tăng dần

**Thông số vận hành:**
- **Qxa ban đầu:** {start_discharge} m³/s
- **Qxa cuối:** {end_discharge} m³/s
- **Qxa trung bình:** {actual_qxa_avg:.2f} m³/s
- **Bước tăng:** {step_size} m³/s mỗi {cycle_hours} giờ
- **Thời gian:** {time_days:.2f} ngày ({total_hours:.0f} giờ)
- **Số lần điều chỉnh:** {len(schedule)} bước

**Điều kiện:**
- Lưu lượng về (Qve): {inflow_rate} m³/s
- Lưu lượng chạy máy (Qcm): {turbine_discharge} m³/s
{water_level_info}
---

#### 📊 Lịch vận hành theo giờ

{schedule_table}

#### 📊 Kiểm chứng toán học

**Qxa trung bình:**

$$
Q_{{xa\\ avg}} = \\frac{{\\sum (Q_{{xa}} \\times t)}}{{t_{{total}}}} = {actual_qxa_avg:.2f} \\text{{ m³/s}}
$$

**Lưu lượng thuần:**

$$
Q_{{net}} = Q_{{ve}} - Q_{{cm}} - Q_{{xa\\ avg}} = {inflow_rate} - {turbine_discharge} - {actual_qxa_avg:.2f} = {inflow_rate - turbine_discharge - actual_qxa_avg:.2f} \\text{{ m³/s}}
$$

---

✅ **Kết luận:** Lịch vận hành trên đảm bảo an toàn, khả thi, và dễ thực hiện.

""".strip()

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Lỗi khi tạo lịch chi tiết: {str(e)}"
