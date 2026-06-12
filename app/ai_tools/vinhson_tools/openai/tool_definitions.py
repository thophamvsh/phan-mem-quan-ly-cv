"""
OpenAI tool definitions for Vĩnh Sơn Tools
"""

# Tool definitions sẽ được import từ file gốc tạm thời
# TODO: Di chuyển đầy đủ tool definitions từ vinhsontools.py

operational_data_function = {
    "name": "get_vinhson_operational_data",
    "description": """Get real operational data (báo cáo dữ liệu) from Google Sheets for Vinh Son hydropower plant.

QUAN TRỌNG - DÙNG TOOL NÀY KHI USER NÓI "BÁO CÁO" HOẶC "DỮ LIỆU":
- **"Báo cáo dữ liệu Vĩnh Sơn từ ngày X đến Y"** → CHỈ GỌI get_vinhson_operational_data, KHÔNG gọi hierarchical_statistics
- **"Báo cáo Vĩnh Sơn từ 1 đến 28/1/2026"** → CHỈ GỌI get_vinhson_operational_data
- **"Dữ liệu Vĩnh Sơn từ X đến Y"** → CHỈ GỌI get_vinhson_operational_data
- Ví dụ: "Báo cáo dữ liệu Vĩnh Sơn từ ngày 1 đến 28/1/2026" → DÙNG TOOL NÀY với start_date="1/1/2026", end_date="28/1/2026"

WHEN TO USE:
- User asks "bao cao", "bao cao du lieu", "du lieu thuc te", "du lieu van hanh", "operational data"
- User asks "muc nuoc hom nay", "luu luong ngay hom qua"
- User wants "san luong dien", "production data"
- User asks "du lieu gan day", "recent data", "latest data"
- User mentions specific date: "ngay 11/01/2026", "11-1-2026"
- User asks "bao cao Vinh Son tu ngay X den ngay Y" → DÙNG start_date và end_date (CHỈ tool này, KHÔNG dùng hierarchical_statistics)
- User asks "du lieu Vinh Son tu X den Y" → DÙNG start_date và end_date

QUAN TRỌNG - KHÔNG DÙNG KHI:
- User hỏi "thống kê lưu lượng về" hoặc "thống kê Qve" → PHẢI DÙNG get_vinhson_hierarchical_statistics
- User hỏi "thống kê mực nước" → PHẢI DÙNG get_vinhson_hierarchical_statistics
- User hỏi "thống kê" với date range → PHẢI DÙNG get_vinhson_hierarchical_statistics
- Ví dụ: "Thống kê lưu lượng về Vĩnh Sơn từ 1/1/2026 đến 13/1/2026" → KHÔNG DÙNG TOOL NÀY, dùng get_vinhson_hierarchical_statistics

PHÂN BIỆT:
- "Báo cáo" / "Dữ liệu" + date range → get_vinhson_operational_data (tool này)
- "Thống kê" + date range → get_vinhson_hierarchical_statistics
- "Phân tích so sánh" / "So sánh với cùng kỳ năm trước" → get_vinhson_comparative_analysis

OUTPUT FORMAT:
- **Date Range** (start_date="DD/MM/YYYY", end_date="DD/MM/YYYY"): Returns HORIZONTAL table with all days in range
  * Shows data for each day from start_date to end_date in chronological order
  * Use this when user asks "báo cáo từ X đến Y" or "dữ liệu từ X đến Y"

- **Specific Date** (date="DD/MM/YYYY"): Returns current-day operational report, NOT a same-period comparison
  * Includes production for day/month/year
  * Includes % achieved against daily/monthly/yearly Qc/plan
  * Do not add same-date-last-year comparison unless the user explicitly asks for comparison

- **Multiple Days** (num_days=N): Returns HORIZONTAL table (multiple rows)
  * Shows data for N recent days in chronological order

DATA AVAILABLE:
- Muc nuoc thuong luu (water level at 24h00) - m
- Dung tich huu ich (reservoir capacity) - trieu m3
- Luu luong ve (Qve, inflow) - m3/s
- Luu luong chay may (Qcm, turbine discharge) - m3/s
- Luu luong xa lu (Qxl, spillway discharge) - m3/s
- San luong dien dau cuc (generator output) - kWh
- San luong dien thuong pham (commercial output) - kWh

SOURCE: Google Sheets - Vinh Son hydropower plant (3 reservoirs: A, B, C)
""",
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Optional: Specific date in format 'DD/MM/YYYY' (e.g., '27/04/2020'). If not specified, returns recent data. Ignored if start_date/end_date is specified."},
            "num_days": {"type": "number", "description": "Number of recent days to retrieve. Default: 7. Ignored if 'date' or start_date/end_date is specified."},
            "start_date": {"type": "string", "description": "Optional: Start date in format 'DD/MM/YYYY' (e.g., '1/1/2026'). Use with end_date to get data for a date range. Use this when user asks 'báo cáo từ X đến Y' or 'dữ liệu từ X đến Y'."},
            "end_date": {"type": "string", "description": "Optional: End date in format 'DD/MM/YYYY' (e.g., '26/1/2026'). Must be provided if start_date is specified."},
            "reservoir": {"type": "string", "enum": ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C", "All"], "default": "All", "description": "Optional: Specific reservoir. Default: 'All'. Use 'All' to get data for all 3 reservoirs."}
        },
        "required": [],
        "additionalProperties": False
    }
}

comparative_analysis_function = {
    "name": "get_vinhson_comparative_analysis",
    "description": """Analyze and compare data between two time periods (current year vs same period last year) for Vinh Son hydropower plant.
WHEN TO USE:
- User asks "phân tích so sánh", "comparative analysis"
- User wants to compare "từ ngày X đến ngày Y" with "cùng kỳ năm trước"
- User asks "thay đổi" or "sự thay đổi" for a DATE RANGE (not single date)
- User mentions "xu hướng", "trend" for a specific period

OUTPUT: Comparison tables (min, max, avg, change %) for current year vs last year
PARAMETER SELECTION:
- If user asks "phân tích mực nước" → parameters=["water_level"]
- If user asks "so sánh lưu lượng về" → parameters=["inflow"]
- If user asks "phân tích tổng hợp" → parameters=null (all)

KHÔNG DÙNG KHI:
- User asks "báo cáo từ X đến Y" (dùng get_vinhson_operational_data)
- User asks "dữ liệu từ X đến Y" (dùng get_vinhson_operational_data)
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "Start date in format 'DD/MM/YYYY'"},
            "end_date": {"type": "string", "description": "End date in format 'DD/MM/YYYY'"},
            "reservoir": {"type": "string", "enum": ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C", "All"], "default": "All", "description": "Optional: Specific reservoir. Default: 'All'. Use 'All' to get data for all 3 reservoirs (A, B, C)."},
            "parameters": {"type": "array", "items": {"type": "string", "enum": ["water_level", "inflow", "turbine", "spillway"]}, "description": "Optional: List of parameters to analyze. If not specified, analyzes all parameters."}
        },
        "required": ["start_date", "end_date"],
        "additionalProperties": False
    }
}

forecast_function = {
    "name": "get_vinhson_forecast",
    "description": """Dự báo Qve và Sản lượng cho tháng hoặc năm tới cho VĨNH SƠN.

QUAN TRỌNG - CHỈ DÙNG CHO VĨNH SƠN:
- Tool này CHỈ dùng cho Vĩnh Sơn
- Khi user hỏi về Sông Hinh → KHÔNG dùng tool này
- Sông Hinh có tool riêng: get_songhinh_forecast

KHI NÀO DÙNG:
- User hỏi "dự báo", "dự đoán", "forecast", "lên kịch bảng" cho Vĩnh Sơn tháng X hoặc năm Y
- Ví dụ: "dự báo Qve Vĩnh Sơn tháng 4/2026"
- Ví dụ: "dự báo sản lượng Vĩnh Sơn năm 2026"
- Ví dụ: "lên kịch bảng cho Vĩnh Sơn tháng tới"

CÁCH TÍNH DỰ BÁO:
1. Tìm tháng/năm có dữ liệu gần nhất trước thời điểm cần dự báo
2. So sánh với các năm liền kề để tìm năm có Qve gần với trung bình nhất
3. Dùng Qve, lượng mưa của năm đó để dự báo cho tháng/năm tới

VÍ DỤ:
- "dự báo Qve Vĩnh Sơn tháng 4/2026" → target_month=4, target_year=2026
- "dự báo sản lượng Vĩnh Sơn năm 2026" → target_year=2026 (không cần target_month)
- "dự báo Vĩnh Sơn tháng tới" → tự động xác định tháng tới

OUTPUT: Bảng phân tích + dự báo Qve và lượng mưa
""",
    "parameters": {
        "type": "object",
        "properties": {
            "target_month": {"type": "integer", "description": "Tháng cần dự báo (1-12). Ví dụ: 4 cho tháng 4."},
            "target_year": {"type": "integer", "description": "Năm cần dự báo. Ví dụ: 2026."},
            "reservoir": {"type": "string", "enum": ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C", "All"], "default": "All", "description": "Optional: Hồ cụ thể hoặc All. Default: 'All'."}
        },
        "required": ["target_year"],
        "additionalProperties": False
    }
}

qve_analysis_function = {
    "name": "get_vinhson_qve_analysis",
    "description": """Phân tích nguyên nhân Qve (và MNH, lượng mưa, sản lượng) khi so sánh năm hiện tại với cùng kỳ năm trước - Thủy điện Vĩnh Sơn.

KHI NÀO DÙNG:
- User hỏi "phân tích Qve Vĩnh Sơn năm X" → TỰ ĐỘNG gọi tool này với start_date="01/01/X", end_date="31/12/X"
- User hỏi "phân tích Qve Vĩnh Sơn tháng Y/X" (ví dụ: tháng 1/2025) → TỰ ĐỘNG gọi tool này với start_date="01/Y/X", end_date="cuối tháng X"
- User hỏi "phân tích Qve, lượng mưa, sản lượng Vĩnh Sơn tháng Y/X" → TỰ ĐỘNG gọi tool này với start_date="01/Y/X", end_date="cuối tháng X"
- User hỏi "phân tích Qve hồ Vĩnh Sơn", "tại sao Qve tăng/giảm" → analysis_focus="qve" (tập trung nguyên nhân Qve do lượng mưa)
- User hỏi "phân tích dữ liệu Sản lượng Vĩnh Sơn", "phân tích sản lượng VS" → analysis_focus="commercial_output" (nguyên nhân sản lượng do Qve, lượng mưa, MNH)

QUAN TRỌNG - CHỈ GỌI 1 TOOL DUY NHẤT:
- **Tool này ĐÃ BAO GỒM TẤT CẢ: Qve, MNH, lượng mưa, sản lượng trong 1 kết quả**
- Khi user hỏi "phân tích Qve, lượng mưa, sản lượng Vĩnh Sơn" → CHỈ GỌI 1 TOOL DUY NHẤT là get_vinhson_qve_analysis
- **TUYỆT ĐỐI KHÔNG gọi thêm bất kỳ tool nào khác** (không gọi hierarchical_statistics, không gọi comparative_analysis, KHÔNG gọi rainfall_statistics)
- Nếu đã gọi tool này thì KHÔNG gọi thêm get_vinhson_hierarchical_statistics, get_vinhson_comparative_analysis, get_vinhson_rainfall_statistics

VÍ DỤ:
- "Phân tích Qve Vĩnh Sơn năm 2025" → start_date="01/01/2025", end_date="31/12/2025"
- "Phân tích Qve Vĩnh Sơn tháng 1/2025" → start_date="01/01/2025", end_date="31/01/2025"
- "Phân tích Qve, lượng mưa, sản lượng Vĩnh Sơn tháng 1/2025" → CHỈ GỌI get_vinhson_qve_analysis (1 lần) với start_date="01/01/2025", end_date="31/01/2025"

PARAMETERS:
- start_date, end_date: khoảng thời gian (DD/MM/YYYY). Cùng kỳ năm trước được tính tự động.
- reservoir: "All" (cả 3 hồ A,B,C) hoặc "Vinh Son -A", "Vinh Son -B", "Vinh Son -C"
- parameters: ["qve", "water_level", "rainfall", "commercial_output"] - có thể bỏ bớt nếu chỉ hỏi Qve hoặc chỉ MNH
- analysis_focus: "qve" = phân tích tập trung Qve. "commercial_output" = phân tích tập trung Sản lượng

OUTPUT: Bảng số liệu so sánh + đoạn văn phân tích nguyên nhân.
CHỈ DÙNG khi user nói Vĩnh Sơn. Sông Hinh → dùng get_songhinh_qve_analysis.
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "Ngày bắt đầu (DD/MM/YYYY)"},
            "end_date": {"type": "string", "description": "Ngày kết thúc (DD/MM/YYYY)"},
            "reservoir": {"type": "string", "enum": ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C", "All"], "description": "Hồ: All = cả 3 hồ, hoặc từng hồ cụ thể. Default: All."},
            "parameters": {"type": "array", "items": {"type": "string", "enum": ["qve", "water_level", "rainfall", "commercial_output"]}, "description": "Tham số cần phân tích. Mặc định: qve, water_level, rainfall, commercial_output."},
            "analysis_focus": {"type": "string", "enum": ["qve", "commercial_output"], "description": "Tập trung phân tích: qve = nguyên nhân Qve do lượng mưa; commercial_output = nguyên nhân Sản lượng do Qve, mưa, MNH."},
        },
        "required": ["start_date", "end_date"],
        "additionalProperties": False
    }
}

hierarchical_statistics_function = {
    "name": "get_vinhson_hierarchical_statistics",
    "description": """Thống kê phân cấp Qve (lưu lượng về) và Mực nước hồ theo năm/tháng/tuần cho Vĩnh Sơn.

TUYỆT ĐỐI KHÔNG DÙNG TOOL NÀY CHO MƯA HOẶC LƯỢNG MƯA. Nếu câu hỏi có từ "mưa" hoặc "lượng mưa", PHẢI dùng tool get_vinhson_rainfall_statistics.

QUY TẮC CHỌN THEO TÊN HỒ - BẮT BUỘC:
- **CHỈ DÙNG** khi user nói "Vĩnh Sơn", "Vinh Son", "hồ Vĩnh Sơn" (ví dụ: "so sánh MNH hồ Vĩnh Sơn năm 2025 với 3 năm cùng kỳ", "thống kê Qve Vĩnh Sơn năm 2026").
- **CẤM DÙNG** khi user chỉ nói "Sông Hinh" / "Song Hinh" → khi đó dùng get_songhinh_hierarchical_statistics. Khi user hỏi "Vĩnh Sơn" PHẢI dùng tool NÀY (get_vinhson_hierarchical_statistics).

QUY TẮC BẮT BUỘC - SO SÁNH 2 THÁNG (vd "tháng 1/2026 với tháng 1/2025"):
- **Luôn GỌI ĐÚNG 1 LẦN** với period_type="month", period_value="1/2026", compare_with_period_value="1/2025", parameters=["qve"] (hoặc water_level). Tool trả về 3 bảng (Hồ A, B, C) so sánh 2 tháng.
- **CẤM** gọi 2 lần (một lần cho 1/2026, một lần cho 1/2025). Nếu gọi 2 lần sẽ ra 6 bảng riêng lẻ, sai yêu cầu. Chỉ được 1 lần gọi với compare_with_period_value.

QUY TẮC ĐẦU TIÊN - PHÂN BIỆT QVE VỚI MƯA:
- **Nếu câu hỏi có từ "Qve" hoặc "lưu lượng về"** → LUÔN dùng tool NÀY (get_vinhson_hierarchical_statistics).
- **Qve:** "So sánh Qve ... năm 2025 với 2 năm cùng kỳ" → period_type="year", period_value="2025", compare=True, compare_years=2, parameters=["qve"]. Bảng 3 cột.
- **Qve:** "Thống kê Qve hồ Vĩnh Sơn năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["qve"]. Bảng 4 cột.
- **MNH (mực nước):** "Thống kê MNH / mực nước hồ Vĩnh Sơn năm 2026 với 2 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=2, parameters=["water_level"]. Bảng 3 cột.
- **MNH:** "Thống kê mực nước ... năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["water_level"]. Bảng 4 cột.
- Qve = lưu lượng về (m³/s). MNH = mực nước hồ (m).

QUAN TRỌNG - ĐÂY LÀ TOOL CHO QVE VÀ MỰC NƯỚC:
- **KHI USER HỎI VỀ QVE** (hoặc "lưu lượng về", "so sánh Qve") → PHẢI DÙNG TOOL NÀY
- **KHI USER HỎI VỀ MỰC NƯỚC** → PHẢI DÙNG TOOL NÀY
- **KHI USER HỎI "THỐNG KÊ"** với date range → PHẢI DÙNG TOOL NÀY (KHÔNG dùng operational_data)
- Ví dụ: "Thống kê Qve Vinh Son tháng 12/2025" → DÙNG TOOL NÀY
- Ví dụ: "Thống kê Qve năm 2025 Vinh Son" → DÙNG TOOL NÀY
- Ví dụ: "Thống kê mực nước tháng X Vinh Son" → DÙNG TOOL NÀY
- Ví dụ: "Thống kê lưu lượng về Vĩnh Sơn từ 1/1/2026 đến 13/1/2026" → DÙNG TOOL NÀY với start_date="1/1/2026", end_date="13/1/2026" (trả về thống kê theo ngày cho toàn bộ khoảng thời gian)
- Ví dụ: "Thống kê Qve Vĩnh Sơn từ ngày X đến ngày Y" → DÙNG TOOL NÀY với start_date và end_date

WHEN TO USE:
- User asks "thống kê Qve năm 2025 Vinh Son" → reservoir="All", period_type="year", period_value="2025", parameters=["qve"]
- User asks "thống kê Qve năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["qve"]
- User asks "thống kê MNH / mực nước năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["water_level"]
- User asks "thống kê Qve tháng 12/2025 Vinh Son" → period_type="month", period_value="12/2025", parameters=["qve"]
- User asks "thống kê mực nước tháng X Vinh Son" → reservoir="All", period_type="month", period_value="X/YYYY", parameters=["water_level"]
- User asks "thống kê lưu lượng về Vĩnh Sơn từ X đến Y" → Dùng start_date="X", end_date="Y" (format DD/MM/YYYY) - sẽ trả về thống kê theo ngày cho toàn bộ khoảng thời gian
- User chỉ hỏi về Qve và mực nước (không cần Qcm, Qxl)
- User muốn thống kê phân cấp: năm→tháng, tháng→tuần, tuần→ngày

QUAN TRỌNG - CHỈ TRẢ VỀ ĐÚNG THAM SỐ USER HỎI:
- **User hỏi "Thống kê Qve"** (hoặc "lưu lượng về") → CHỈ truyền parameters=["qve"] → Trả lời CHỈ bảng Qve
- **User hỏi "Thống kê MNH"** hoặc **"Thống kê mực nước"** → CHỈ truyền parameters=["water_level"] → Trả lời CHỈ bảng MNH
- Không truyền cả hai (qve + water_level) trừ khi user hỏi rõ cả hai
- Ví dụ: "Thống kê Qve của Vĩnh Sơn 1/9/2025 đến 31/12/2025" → parameters=["qve"]
- Ví dụ: "Thống kê MNH của Vĩnh Sơn từ X đến Y" → parameters=["water_level"]

QUAN TRỌNG - DATE RANGE:
- Khi user hỏi "thống kê từ X đến Y", sử dụng start_date và end_date (format DD/MM/YYYY)
- Tool sẽ trả về thống kê theo ngày cho toàn bộ khoảng thời gian từ start_date đến end_date
- Với reservoir="All", gộp 1 bảng với cột Hồ A, Hồ B, Hồ C
- Không cần chỉ định period_type khi có start_date và end_date

QUAN TRỌNG - RESERVOIR SELECTION:
- **Khi user KHÔNG chỉ định hồ cụ thể** (ví dụ: "Thống kê Qve Vinh Son năm 2025") → DÙNG reservoir="All" để thống kê CẢ 3 HỒ A, B, C
- **Khi user chỉ định hồ cụ thể** (ví dụ: "hồ A", "hồ B", "hồ C") → Dùng reservoir tương ứng
- **Mặc định:** Nếu không chỉ định, dùng "All" để hiển thị cả 3 hồ

QUAN TRỌNG - SO SÁNH THÁNG: CHỈ 1 LẦN GỌI. Áp dụng cho CẢ Qve VÀ MNH (mực nước):
- **Qve:** "So sánh Qve tháng X với tháng Y" → period_type="month", period_value="X", compare_with_period_value="Y", parameters=["qve"]. 3 bảng (Hồ A,B,C), mỗi bảng 2 cột theo ngày.
- **MNH:** "So sánh mực nước / MNH tháng X với tháng Y" → cùng trên, parameters=["water_level"].
- **2 năm cùng kỳ:** "So sánh Qve tháng 1/2026 với tháng 1 của 2 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=2, parameters=["qve"]. Trả về 3 bảng (Hồ A,B,C), mỗi bảng 3 cột: 1/2026 | 1/2025 | 1/2024.
- **3 năm cùng kỳ:** "So sánh Qve tháng 1/2026 với tháng 1 của 3 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=3, parameters=["qve"]. Trả về 3 bảng (Hồ A,B,C), mỗi bảng 4 cột: 1/2026 | 1/2025 | 1/2024 | 1/2023.
- **3 năm cùng kỳ (MNH):** "Thống kê MNH tháng 1/2026 với 3 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=3, parameters=["water_level"]. Trả về 3 bảng (Hồ A,B,C), mỗi bảng 4 cột.
- CẤM gọi 2 hoặc 3 lần. Luôn 1 lần gọi.

QUAN TRỌNG - SO SÁNH THEO NĂM. Áp dụng cho CẢ Qve VÀ MNH (mực nước):
- **Qve:** "Thống kê Qve ... năm X với 2 năm cùng kỳ" → period_type="year", period_value="X", compare=True, compare_years=2, parameters=["qve"]. Bảng 3 cột.
- **Qve:** "Thống kê Qve ... năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["qve"]. Bảng 4 cột.
- **MNH:** "Thống kê MNH / mực nước ... năm 2026 với 2 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=2, parameters=["water_level"]. Bảng 3 cột.
- **MNH:** "Thống kê mực nước ... năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["water_level"]. Bảng 4 cột.
- KHÔNG tạo nhiều bảng riêng; 1 BẢNG với nhiều cột (mỗi cột 1 năm). GỌI 1 LẦN.

KHÔNG DÙNG KHI:
- User hỏi **"báo cáo"** hoặc **"báo cáo dữ liệu"** hoặc **"dữ liệu từ X đến Y"** (không có từ "thống kê") → PHẢI DÙNG get_vinhson_operational_data, KHÔNG dùng tool này
- Ví dụ: "Báo cáo dữ liệu Vĩnh Sơn từ ngày 1 đến 28/1/2026" → KHÔNG DÙNG TOOL NÀY, chỉ gọi get_vinhson_operational_data
- User muốn thống kê Qcm, Qxl (không có tool này nữa)
- User hỏi về MƯA (rainfall) → Dùng get_vinhson_rainfall_statistics

PHÂN BIỆT RÕ:
- "Báo cáo dữ liệu từ X đến Y" = get_vinhson_operational_data (1 tool duy nhất)
- "Thống kê lưu lượng về từ X đến Y" = get_vinhson_hierarchical_statistics (tool này)

OUTPUT: Chỉ hiển thị đúng tham số được hỏi (Qve hoặc MNH). Tables with Min/Max/Avg for each level (year→month, month→week, week→day)
PARAMETERS: parameters=["qve"] khi user hỏi Qve; parameters=["water_level"] khi user hỏi MNH/mực nước. CHỈ truyền 1 loại trừ khi user hỏi cả hai.
SOURCE: Đọc từ Google Sheets thống kê (STATS_EXPORT_SPREADSHEET_ID_VINHSON)
""",
    "parameters": {
        "type": "object",
        "properties": {
            "period_type": {"type": "string", "enum": ["year", "month", "week"], "description": "Type of period. Optional if start_date and end_date are provided."},
            "period_value": {"type": "string", "description": "Period value. Optional if start_date and end_date are provided."},
            "reservoir": {"type": "string", "enum": ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C", "All"], "default": "All", "description": "Optional: Specific reservoir. Default: 'All' (shows all 3 reservoirs in one table)"},
            "parameters": {"type": "array", "items": {"type": "string", "enum": ["qve", "water_level"]}, "description": "CHỈ truyền đúng tham số user hỏi: User hỏi Qve → parameters=['qve']. User hỏi MNH/mực nước → parameters=['water_level']. Không truyền cả hai trừ khi user hỏi cả hai."},
            "compare": {"type": "boolean", "default": False, "description": "Optional: Compare with previous years. Default: False"},
            "compare_years": {"type": "integer", "default": 1, "minimum": 1, "maximum": 5, "description": "Khi so sánh theo năm (compare=True): số năm cùng kỳ. 2 → 3 cột, 3 → 4 cột (vd: năm 2026 với 3 năm cùng kỳ → compare_years=3)."},
            "compare_with_period_value": {"type": "string", "description": "BẮT BUỘC khi user nói 'so sánh tháng X với tháng Y': truyền kỳ thứ hai (Y). VD: so sánh 1/2026 với 1/2025 → period_value='1/2026', compare_with_period_value='1/2025'. Chỉ gọi tool 1 LẦN. Cấm gọi 2 lần."},
            "start_date": {"type": "string", "description": "Start date in format 'DD/MM/YYYY' (e.g., '1/1/2026'). Use with end_date to get daily statistics for a date range."},
            "end_date": {"type": "string", "description": "End date in format 'DD/MM/YYYY' (e.g., '13/1/2026'). Must be provided if start_date is specified."}
        },
        "required": [],
        "additionalProperties": False
    }
}

rainfall_statistics_function = {
    "name": "get_vinhson_rainfall_statistics",
    "description": """Get rainfall statistics (MƯA - mm) by time period for Vinh Son. CHỈ dùng khi user nói rõ MƯA / lượng mưa.

QUAN TRỌNG - CÂU HỎI THÁNG CHỈ RA KẾT QUẢ THÁNG (CẤM GỌI THÊM NĂM):
- **Khi user hỏi "thống kê mưa ... tháng 1/2026" hoặc "mưa tháng X/Y"** → CHỈ GỌI 1 LẦN với period_type="month", period_value="X/Y" (vd: "1/2026"). Trả về DUY NHẤT kết quả tháng (bảng các trạm theo ngày + bảng tổng 4 năm). CẤM gọi thêm lần với period_type="year". Không ra kết quả năm khi user chỉ hỏi tháng.
- Một câu hỏi tháng = một lần gọi, chỉ period_type="month". Một câu hỏi năm = một lần gọi, chỉ period_type="year".

QUY TẮC ĐẦU TIÊN - KHÔNG DÙNG KHI USER HỎI QVE:
- **Nếu câu hỏi có "Qve" hoặc "lưu lượng về"** (lưu lượng về hồ, m³/s) → KHÔNG DÙNG tool này. PHẢI dùng get_vinhson_hierarchical_statistics.
- Tool này CHỈ cho MƯA (rainfall, mm). Qve = lưu lượng về = inflow (m³/s) = tool hierarchical_statistics.
- Ví dụ: "So sánh Qve năm 2025 với 2 năm cùng kỳ" → KHÔNG gọi tool này, gọi get_vinhson_hierarchical_statistics.

QUY TẮC BẮT BUỘC - CHỈ GỌI ĐÚNG 1 LẦN (CẤM GỌI 2 LẦN):
- **User hỏi "với 3 năm cùng kỳ"** → CHỈ GỌI 1 LẦN với period_type="year", period_value="X", compare_years=3. Trả về đúng 4 cột (vd: 2026|2025|2024|2023). CẤM gọi thêm lần với compare_years=2 hoặc bất kỳ giá trị nào khác.
- **User hỏi "với 2 năm cùng kỳ" / "2 năm liền kề"** → CHỈ GỌI 1 LẦN với compare_years=2. Bảng 2: 3 cột.
- Một câu hỏi = một lần gọi. Không gọi 2 lần cho cùng một câu (vd: không gọi cả compare_years=3 và compare_years=2).
- **"So sánh lượng mưa Vĩnh Sơn 2026 với 3 năm cùng kỳ"** → period_type="year", period_value="2026", compare_years=3. Bảng 2 có 4 cột. CHỈ 1 LẦN.

QUAN TRỌNG - ĐÂY LÀ TOOL CHỈ CHO MƯA (RAINFALL):
- Dùng khi user hỏi về MƯA: "lượng mưa", "lưu lượng mưa", "mưa trung bình", "thống kê mưa"
- KHÔNG dùng khi user hỏi Qve (lưu lượng về hồ) → dùng get_vinhson_hierarchical_statistics
- KHÔNG dùng khi user hỏi mực nước → dùng get_vinhson_hierarchical_statistics

WHEN TO USE:
- "so sánh lượng mưa Vĩnh Sơn năm X với 2 năm liền kề" → period_type="year", period_value="X", compare_years=2. "với 3 năm cùng kỳ" → compare_years=3.
- "thống kê mưa năm X Vĩnh Sơn" → GỌI 1 LẦN với period_value="X"
- Default reservoir="All" (all 3 stations: Hồ A, B, C)

KHÔNG DÙNG KHI:
- User hỏi về Qve (lưu lượng về) → Dùng get_vinhson_hierarchical_statistics
- User hỏi về mực nước → Dùng get_vinhson_hierarchical_statistics

OUTPUT (khi period_type="year"):
- Bảng 1: Chi tiết các tháng năm được hỏi của 3 trạm (Tháng | Hồ A | Hồ B | Hồ C)
- Bảng 2: Chỉ hiển thị khi user yêu cầu so sánh với N năm (compare_years > 1). So sánh tổng lượng mưa các trạm (năm được hỏi và N năm cùng kỳ; compare_years=2 → 3 cột, compare_years=3 → 4 cột)

QUY TẮC MỚI:
- "thống kê mưa năm 2025" → compare_years=1 (chỉ Bảng 1)
- "so sánh mưa năm 2025 với 2 năm cùng kỳ" → compare_years=2 (Bảng 1 + Bảng 2)
- "so sánh mưa năm 2025 với 3 năm cùng kỳ" → compare_years=3 (Bảng 1 + Bảng 2)

SO SÁNH THÁNG THEO NGÀY (period_type="month"):
- "So sánh lượng mưa Vĩnh Sơn tháng 1/2026 với tháng 1 của 2 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=2. Ba bảng (Hồ A, B, C), mỗi bảng theo ngày, 3 cột.
- "So sánh lượng mưa tháng 1/2026 với tháng 1 của 3 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=3. Ba bảng, mỗi bảng 4 cột theo ngày.

PERIOD TYPES:
- "year": Bảng 1 + Bảng 2; compare_years=2 → 3 cột năm, compare_years=3 → 4 cột năm
- "month": So sánh theo ngày (1-31), 3 bảng (Hồ A, B, C) + bảng tổng; compare_years=2 → 3 cột, 3 → 4 cột
""",
    "parameters": {
        "type": "object",
        "properties": {
            "period_type": {"type": "string", "enum": ["year", "month", "week"], "description": "Type of period: 'year', 'month', or 'week'"},
            "period_value": {"type": "string", "description": "Period value: year (e.g., '2026'), month (e.g., '1/2026'), or week (e.g., '3/1/2026')"},
            "reservoir": {"type": "string", "enum": ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C", "All"], "description": "Optional: Specific reservoir. Default: 'All' (all 3 stations: Hồ A, B, C). Use 'All' when user does not specify a reservoir."},
            "stations": {"type": "array", "items": {"type": "string"}, "description": "Optional: List of specific stations"},
            "compare_years": {"type": "integer", "default": 1, "minimum": 1, "maximum": 5, "description": "Số năm cùng kỳ để so sánh. User nói 'thống kê năm 2025' → compare_years=1 (chỉ Bảng 1). User nói 'so sánh với 3 năm cùng kỳ' → compare_years=3 (4 cột). Cấm gọi tool 2 lần với 2 giá trị khác nhau."}
        },
        "required": ["period_type", "period_value"],
        "additionalProperties": False
    }
}

rainfall_range_statistics_function = {
    "name": "get_vinhson_rainfall_range_statistics",
    "description": """Get rainfall statistics for a date range (from one month to another) for Vinh Son.
WHEN TO USE:
- User asks "Lượng mưa từ tháng X/Y đến tháng Z/W"
- User asks about rainfall in a specific date range spanning multiple months
- User asks "Thống kê mưa từ ... đến ..." for Vinh Son

OUTPUT: Monthly breakdown with totals and per-station details
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_month": {"type": "integer", "description": "Start month (1-12)"},
            "start_year": {"type": "integer", "description": "Start year (e.g., 2025)"},
            "end_month": {"type": "integer", "description": "End month (1-12)"},
            "end_year": {"type": "integer", "description": "End year (e.g., 2025)"},
            "reservoir": {"type": "string", "enum": ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"], "description": "Optional: Specific reservoir. Default: 'Vinh Son -A'"},
            "stations": {"type": "array", "items": {"type": "string"}, "description": "Optional: List of specific stations"}
        },
        "required": ["start_month", "start_year", "end_month", "end_year"],
        "additionalProperties": False
    }
}

rainfall_daily_statistics_function = {
    "name": "get_vinhson_rainfall_daily_statistics",
    "description": """Get detailed daily rainfall statistics for a specific date range for Vinh Son.
Use this when user asks "Thống kê lượng mưa từ ngày X đến ngày Y" or "lượng mưa từ 1/12/2025 đến 31/12/2025".
Returns a detailed table showing rainfall for each day with all stations.
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "Start date in format 'DD/MM/YYYY' (e.g., '1/12/2025')"},
            "end_date": {"type": "string", "description": "End date in format 'DD/MM/YYYY' (e.g., '31/12/2025')"},
            "reservoir": {"type": "string", "enum": ["Vinh Son -A", "Vinh Son -B", "Vinh Son -C"], "description": "Optional: Specific reservoir. Default: Vinh Son -A"},
            "stations": {"type": "array", "items": {"type": "string"}, "description": "Optional: List of specific stations"}
        },
        "required": ["start_date", "end_date"],
        "additionalProperties": False
    }
}
