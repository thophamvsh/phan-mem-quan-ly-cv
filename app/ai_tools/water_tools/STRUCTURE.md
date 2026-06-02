# Water Tools - Cấu trúc & Chức năng chi tiết

```
water_tools/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── interpolation.py
│   ├── volume.py
│   ├── flow.py
│   ├── ramping.py
│   └── spillway.py
├── tooldefs/
│   ├── __init__.py
│   ├── schemas.py
│   └── registry.py
└── runtime/
    ├── __init__.py
    └── handler.py
```

---

## `__init__.py` — Entry point

Export toàn bộ API công khai của module `water_tools`.

| Export | Nguồn |
|--------|-------|
| Tất cả hàm tính toán (12 hàm) | `core/` |
| `TOOLS`, `TOOL_REGISTRY` | `tooldefs/` |
| `handle_tool_calls` | `runtime/` |

Cách dùng:
```python
from water_tools import TOOLS, handle_tool_calls
```

---

## `core/` — Các hàm tính toán thủy văn

### `core/__init__.py`
Re-export tất cả hàm từ các module con trong `core/`.

---

### `core/interpolation.py` — Nội suy ngược V → H

| Hàm | Mô tả |
|-----|--------|
| `interpolate_water_level_from_volume(target_volume, reservoir, hint_level)` | Nội suy tuyến tính ngược: từ dung tích (triệu m³) → mực nước (m). Dùng `query_nearby_water_levels()` từ `hydro_data_repository` để lấy bảng quan hệ H~V trong app `thongsothuyvan`, sau đó nội suy giữa 2 điểm gần nhất. Fallback: ước lượng tuyến tính ~23 triệu m³/m (Sông Hinh). |

Phụ thuộc: `hydro_data_repository.interpolate_water_volume`, `hydro_data_repository.query_nearby_water_levels`

---

### `core/volume.py` — Tra cứu dung tích & chênh lệch

| Hàm | Mô tả |
|-----|--------|
| `get_water_volume(water_level, reservoir)` | Tra cứu dung tích hồ tại một mực nước. Trả về kết quả nội suy tuyến tính (chuẩn thủy văn) với công thức LaTeX chi tiết. Hỗ trợ 3 phương pháp: `exact` (trùng khớp), `interpolated` (nội suy), `nearest` (gần nhất). |
| `calculate_volume_difference(start_level, end_level, reservoir)` | Tính chênh lệch dung tích ΔV giữa 2 mực nước. Công thức: `ΔV = V(end) - V(start)`. Trả về bảng so sánh và kết luận cần thêm/xả bao nhiêu nước. |

Phụ thuộc: `hydro_data_repository.interpolate_water_volume`

---

### `core/flow.py` — Lưu lượng, thời gian, thay đổi mực nước

| Hàm | Mô tả |
|-----|--------|
| `calculate_flow_rate(start_level, end_level, time_days, discharge_rate, reservoir)` | Tính lưu lượng cần thiết để thay đổi mực nước trong khoảng thời gian cho trước. Công thức: `Q = ΔV / t`. Nếu có `discharge_rate` (Qcm): `Q_về = Q_thuần + Q_xả`. Trả về tốc độ thay đổi (cm/giờ, cm/ngày). |
| `calculate_time_needed(start_level, end_level, inflow_rate, discharge_rate, reservoir)` | Tính thời gian cần thiết để thay đổi mực nước với lưu lượng cho trước. Công thức: `t = |ΔV| / |Q_thuần|` với `Q_thuần = Q_vào - Q_xả`. |
| `calculate_level_change(qve, qcm, time_days, start_level, reservoir)` | Tính mực nước cuối sau khoảng thời gian với Qve và Qcm cho trước. Công thức: `ΔV = Q_thuần × t`, sau đó nội suy ngược V → H. Trả về mực nước cuối, độ thay đổi (m), tốc độ (cm/ngày, cm/giờ). |

Phụ thuộc: `hydro_data_repository.interpolate_water_volume`, `core.interpolation.interpolate_water_level_from_volume`

---

### `core/ramping.py` — Phân bổ lưu lượng xả tăng dần

| Hàm | Mô tả |
|-----|--------|
| `calculate_ramping_discharge(avg_discharge, time_days, start_discharge)` | Tính lịch xả tăng tuyến tính khi biết Q_start. Công thức: `Q_end = 2 × Q_avg - Q_start`. Trả về tốc độ tăng (m³/s/ngày, m³/s/giờ) và lịch vận hành. |
| `calculate_ramping_from_max(avg_discharge, time_days, max_discharge)` | Bài toán ngược: tính Q_start khi biết Q_max. Công thức: `Q_start = 2 × Q_avg - Q_max`. Kiểm tra tính khả thi và trả về lịch vận hành. |
| `calculate_practical_ramping(avg_discharge, time_days, start_discharge, max_discharge)` | Phân bổ xả thực tế với ràng buộc vận hành: lưu lượng phải là bội số 50, bước tăng ∈ {50, 100, 150, 200, 250, 400}, chu kỳ điều chỉnh tự động theo thời gian (<1 ngày: 2-4h, 1-3 ngày: 6h, 3-7 ngày: 12h, >7 ngày: 24h). Xử lý xung đột ràng buộc khi cả start và max đều cho trước. |

Không phụ thuộc module ngoài (tính toán thuần túy).

---

### `core/spillway.py` — Tính toán xả tràn qua đập

| Hàm | Mô tả |
|-----|--------|
| `calculate_spillway_discharge(start_level, end_level, time_days, inflow_rate, turbine_discharge, reservoir)` | Tính Qxa (lưu lượng xả tràn) hằng số. Phương trình cân bằng nước: `Qxa = Qve - Qcm - (ΔV/t)`. Trả về bảng kết quả với công thức LaTeX từng bước. |
| `calculate_spillway_ramping(start_level, end_level, time_days, inflow_rate, turbine_discharge, max_discharge, start_discharge, reservoir)` | Tính lịch xả tràn tăng dần (tool phức tạp nhất). Tự động tính Qxa_avg từ cân bằng nước, sau đó thử nhiều tổ hợp (cycle × step × start) để tìm 3-4 phương án tối ưu. Sắp xếp theo độ chính xác Qxa_avg và độ lệch thời gian. |
| `create_detailed_spillway_schedule(start_discharge, end_discharge, time_days, cycle_hours, step_size, inflow_rate, turbine_discharge, start_level, end_level, reservoir)` | Tạo lịch vận hành chi tiết theo giờ (Step 2 - sau khi user chọn phương án). Tính mực nước hồ thay đổi từng bước dùng hệ số dV/dH. Bao gồm: bảng giờ-by-giờ với cột MNH, kiểm chứng toán học, hướng dẫn vận hành. |

Phụ thuộc: `hydro_data_repository.interpolate_water_volume`, `core.interpolation.interpolate_water_level_from_volume`

---

## `tooldefs/` — Định nghĩa tool cho OpenAI API

### `tooldefs/__init__.py`
Export `TOOLS`, `TOOL_REGISTRY`, `get_tool_function`.

---

### `tooldefs/schemas.py` — JSON Schema cho OpenAI function calling

Định nghĩa 11 tool schemas cho OpenAI API:

| Schema variable | Tool name | Khi nào dùng |
|----------------|-----------|--------------|
| `water_level_function` | `get_water_volume` | User hỏi dung tích tại mực nước X |
| `volume_difference_function` | `calculate_volume_difference` | User hỏi chênh lệch dung tích giữa 2 mực nước |
| `level_change_function` | `calculate_level_change` | User cho Qve, Qcm, thời gian → hỏi mực nước thay đổi bao nhiêu |
| `flow_rate_function` | `calculate_flow_rate` | User cho 2 mực nước + thời gian → hỏi lưu lượng cần thiết |
| `time_calculation_function` | `calculate_time_needed` | User cho 2 mực nước + lưu lượng → hỏi mất bao lâu |
| `ramping_discharge_function` | `calculate_ramping_discharge` | User cho Q_avg + Q_start → tính lịch xả tăng dần |
| `ramping_from_max_function` | `calculate_ramping_from_max` | User cho Q_avg + Q_max → tính Q_start và lịch xả |
| `practical_ramping_function` | `calculate_practical_ramping` | User muốn lịch xả thực tế (bội 50, bước chuẩn) |
| `spillway_calculation_function` | `calculate_spillway_discharge` | Tính Qxa hằng số (không tăng dần) |
| `spillway_ramping_function` | `calculate_spillway_ramping` | Tính lịch xả tràn tăng dần (phức tạp nhất, nhiều phương án) |
| `detailed_spillway_schedule_function` | `create_detailed_spillway_schedule` | Tạo lịch chi tiết sau khi user chọn phương án |

Hồ chứa hỗ trợ: Sông Hinh (196-213m), TKT/Thượng Kon Tum (1135-1165m).

Export: `TOOLS` — danh sách 11 tool dạng `[{"type": "function", "function": ...}]` cho OpenAI API.

---

### `tooldefs/registry.py` — Ánh xạ tên tool → hàm Python

| Export | Mô tả |
|--------|--------|
| `TOOL_REGISTRY` | Dict `{tool_name: callable}` — ánh xạ 11 tên tool sang hàm tương ứng trong `core/` |
| `get_tool_function(tool_name)` | Helper trả về hàm từ tên tool |

---

## `runtime/` — Xử lý tool call từ OpenAI

### `runtime/__init__.py`
Export `handle_tool_calls`.

---

### `runtime/handler.py` — Dispatcher

| Hàm | Mô tả |
|-----|--------|
| `handle_tool_calls(message)` | Nhận `message` từ OpenAI response (có `tool_calls`), parse JSON arguments, tra `TOOL_REGISTRY` để tìm hàm, gọi `func(**arguments)`, trả về list `[{"role": "tool", "content": result, "tool_call_id": id}]`. Xử lý lỗi: unknown tool, exception khi thực thi. |

---

## Luồng hoạt động

```
User query
    ↓
app.py → OpenAI API (với TOOLS schemas)
    ↓
OpenAI trả về tool_calls
    ↓
handle_tool_calls(message)
    ↓
TOOL_REGISTRY[tool_name] → core function
    ↓
core function gọi `hydro_data_repository` (Django models trong app `thongsothuyvan`, bảng H~V)
    ↓
Trả kết quả markdown → OpenAI → User
```
