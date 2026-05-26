"""
OpenAI tool definitions for Sông Hinh Tools
"""

operational_data_function = {
    "name": "get_songinh_operational_data",
    "description": """Get real operational data from Google Sheets for Song Hinh hydropower plant.

WHEN TO USE:
- User asks about "du lieu thuc te", "du lieu van hanh", "operational data", "bao cao Song Hinh"
- User asks "muc nuoc hom nay", "luu luong ngay hom qua"
- User wants "san luong dien", "production data"
- User asks "du lieu gan day", "recent data", "latest data"
- User mentions specific date: "ngay 11/01/2026", "11-1-2026"
- User asks "bao cao Song Hinh tu ngay X den ngay Y" → DÙNG start_date và end_date (KHÔNG dùng comparative_analysis)
- User asks "du lieu Song Hinh tu 1/1/2026 den 26/1/2026" → DÙNG start_date và end_date

QUAN TRỌNG - KHÔNG DÙNG KHI:
- User hỏi "thống kê lưu lượng về" hoặc "thống kê Qve" → PHẢI DÙNG get_songhinh_hierarchical_statistics
- User hỏi "thống kê mực nước" → PHẢI DÙNG get_songhinh_hierarchical_statistics
- User hỏi "thống kê" với date range → PHẢI DÙNG get_songhinh_hierarchical_statistics
- Ví dụ: "Thống kê lưu lượng về Sông Hinh từ 1/1/2026 đến 13/1/2026" → KHÔNG DÙNG TOOL NÀY, dùng get_songhinh_hierarchical_statistics

QUAN TRỌNG - PHÂN BIỆT VỚI COMPARATIVE_ANALYSIS:
- "Báo cáo từ X đến Y" hoặc "Dữ liệu từ X đến Y" → DÙNG get_songinh_operational_data với start_date/end_date (hiển thị dữ liệu thực tế)
- "Phân tích so sánh từ X đến Y" hoặc "So sánh từ X đến Y với cùng kỳ năm trước" → DÙNG get_songhinh_comparative_analysis (phân tích thống kê)

OUTPUT FORMAT:
- **Date Range** (start_date="DD/MM/YYYY", end_date="DD/MM/YYYY"): Returns HORIZONTAL table with all days in range
  * Shows data for each day from start_date to end_date in chronological order
  * Use this when user asks "báo cáo từ X đến Y" or "dữ liệu từ X đến Y"

- **Specific Date** (date="DD/MM/YYYY"): Returns VERTICAL comparison table (3 columns)
  * Column 1: Parameter names
  * Column 2: Current year data
  * Column 3: Same date last year (year-over-year comparison)

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

SOURCE: Google Sheets - Song Hinh hydropower plant
""",
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Optional: Specific date in format 'DD/MM/YYYY' (e.g., '27/04/2020'). If not specified, returns recent data. Ignored if start_date/end_date is specified.",
            },
            "num_days": {
                "type": "number",
                "description": "Number of recent days to retrieve. Default: 7. Ignored if 'date' or start_date/end_date is specified.",
            },
            "start_date": {
                "type": "string",
                "description": "Optional: Start date in format 'DD/MM/YYYY' (e.g., '1/1/2026'). Use with end_date to get data for a date range. Use this when user asks 'báo cáo từ X đến Y' or 'dữ liệu từ X đến Y'.",
            },
            "end_date": {
                "type": "string",
                "description": "Optional: End date in format 'DD/MM/YYYY' (e.g., '26/1/2026'). Must be provided if start_date is specified.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

comparative_analysis_function = {
    "name": "get_songhinh_comparative_analysis",
    "description": """Analyze and compare data between two time periods (current year vs same period last year) for Song Hinh hydropower plant.""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "parameters": {
                "type": "array",
                "items": {"type": "string", "enum": ["water_level", "inflow", "turbine", "spillway"]},
            },
        },
        "required": ["start_date", "end_date"],
        "additionalProperties": False,
    },
}

qve_analysis_function = {
    "name": "get_songhinh_qve_analysis",
    "description": """Phân tích nguyên nhân Qve (và MNH, lượng mưa, sản lượng) khi so sánh năm hiện tại với cùng kỳ năm trước - Thủy điện Sông Hinh.

KHI NÀO DÙNG:
- User hỏi "phân tích Sông Hinh năm X" → TỰ ĐỘNG gọi tool này với start_date="01/01/X", end_date="31/12/X"
- User hỏi "phân tích Sông Hinh tháng Y/X" (ví dụ: tháng 2/2026) → TỰ ĐỘNG gọi tool này với start_date="01/Y/X", end_date="cuối tháng X"
- User hỏi "phân tích Qve Sông Hinh", "tại sao Qve tăng/giảm", "nguyên nhân Qve năm nay so với năm ngoái" (cho Sông Hinh) → analysis_focus="qve" (tập trung nguyên nhân Qve do lượng mưa)
- User hỏi "phân tích dữ liệu Sản lượng Sông Hinh", "phân tích sản lượng" kèm so sánh cùng kỳ → analysis_focus="commercial_output" (nguyên nhân sản lượng do Qve, lượng mưa, MNH)

QUAN TRỌNG - CHỈ GỌI 1 TOOL DUY NHẤT:
- **Tool này ĐÃ BAO GỒM TẤT CẢ: Qve, MNH, lượng mưa, sản lượng trong 1 kết quả**
- Khi user hỏi "phân tích Qve, lượng mưa, sản lượng Sông Hinh" → CHỈ GỌI 1 TOOL DUY NHẤT là get_songhinh_qve_analysis
- **TUYỆT ĐỐI KHÔNG gọi thêm bất kỳ tool nào khác** (không gọi hierarchical_statistics, không gọi comparative_analysis, KHÔNG gọi rainfall_statistics)
- Nếu đã gọi tool này thì KHÔNG gọi thêm get_songhinh_hierarchical_statistics, get_songhinh_comparative_analysis, get_songhinh_rainfall_statistics

VÍ DỤ:
- "Phân tích Sông Hinh năm 2025" → start_date="01/01/2025", end_date="31/12/2025"
- "Phân tích Sông Hinh tháng 2/2026" → start_date="01/02/2026", end_date="28/02/2026"
- "Phân tích Qve, lượng mưa, sản lượng Sông Hinh năm 2025" → CHỈ GỌI get_songhinh_qve_analysis (1 lần)

PARAMETERS:
- start_date, end_date: khoảng thời gian năm nay (DD/MM/YYYY). Cùng kỳ năm trước được tính tự động.
- parameters: ["qve", "water_level", "rainfall", "commercial_output"] - có thể bỏ bớt nếu chỉ hỏi Qve hoặc chỉ MNH
- analysis_focus: "qve" = phân tích tập trung Qve. "commercial_output" = phân tích tập trung Sản lượng

OUTPUT: Bảng số liệu so sánh 4 năm + đoạn văn phân tích nguyên nhân.
CHỈ DÙNG khi user nói Sông Hinh. Vĩnh Sơn → dùng get_vinhson_qve_analysis.
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "Ngày bắt đầu (DD/MM/YYYY)"},
            "end_date": {"type": "string", "description": "Ngày kết thúc (DD/MM/YYYY)"},
            "parameters": {"type": "array", "items": {"type": "string", "enum": ["qve", "water_level", "rainfall", "commercial_output"]}, "description": "Tham số cần phân tích. Mặc định: qve, water_level, rainfall, commercial_output."},
            "analysis_focus": {"type": "string", "enum": ["qve", "commercial_output"], "description": "Tập trung phân tích: qve = nguyên nhân Qve do lượng mưa; commercial_output = nguyên nhân Sản lượng do Qve, mưa, MNH. Mặc định: qve khi user hỏi 'phân tích Qve'; commercial_output khi user hỏi 'phân tích sản lượng'."},
        },
        "required": ["start_date", "end_date"],
        "additionalProperties": False,
    },
}

rainfall_statistics_function = {
    "name": "get_songhinh_rainfall_statistics",
    "description": """Get rainfall statistics by time period (year/month/week) for Sông Hinh.

QUAN TRỌNG - CÂU HỎI THÁNG CHỈ RA KẾT QUẢ THÁNG (CẤM GỌI THÊM NĂM):
- **Khi user hỏi "thống kê mưa ... tháng 1/2026" hoặc "mưa tháng X/Y"** → CHỈ GỌI 1 LẦN với period_type="month", period_value="X/Y" (vd: "1/2026"). Trả về DUY NHẤT kết quả tháng (bảng các trạm theo ngày + bảng tổng 4 năm). CẤM gọi thêm lần với period_type="year". Không ra kết quả năm khi user chỉ hỏi tháng.
- Một câu hỏi tháng = một lần gọi, chỉ period_type="month". Một câu hỏi năm = một lần gọi, chỉ period_type="year".

QUAN TRỌNG - GỌI TOOL CHỈ MỘT LẦN (CẤM GỌI 2 LẦN):
- **User hỏi "với 3 năm cùng kỳ"** → CHỈ GỌI 1 LẦN với period_type="year", period_value="X", compare_years=3. Trả về đúng 4 cột (vd: 2026|2025|2024|2023). CẤM gọi thêm lần với compare_years=2 hoặc giá trị khác.
- **User hỏi "với 2 năm cùng kỳ" / "2 năm liền kề"** → CHỈ GỌI 1 LẦN với compare_years=2. Bảng 2: 3 cột.
- Một câu hỏi = một lần gọi. Không gọi 2 lần cho cùng một câu (vd: không gọi cả compare_years=3 và compare_years=2).
- **"So sánh lượng mưa Sông Hinh năm 2026 với 3 năm cùng kỳ"** → period_type="year", period_value="2026", compare_years=3. Bảng 2 có 4 cột. CHỈ 1 LẦN.

WHEN TO USE:
- User asks "thống kê mưa Sông Hinh", "so sánh lượng mưa Sông Hinh năm X với 2/3 năm liền kề / cùng kỳ", "lượng mưa Sông Hinh"

OUTPUT (khi period_type="year"):
- Bảng 1: Chi tiết các tháng năm được hỏi của các trạm (Tháng | trạm1 | trạm2 | ...)
- Bảng 2: So sánh tổng lượng mưa các trạm (năm được hỏi và N năm cùng kỳ; compare_years=2 → 3 cột, compare_years=3 → 4 cột)

SO SÁNH THÁNG THEO NGÀY (period_type="month"):
- "So sánh lượng mưa Sông Hinh tháng 1/2026 với tháng 1 của 2 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=2. Bảng theo ngày (1-31), 3 cột: 1/2026 | 1/2025 | 1/2024.
- "So sánh lượng mưa tháng 1/2026 với tháng 1 của 3 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=3. Bảng theo ngày, 4 cột: 1/2026 | 1/2025 | 1/2024 | 1/2023.
""",
    "parameters": {
        "type": "object",
        "properties": {
            "period_type": {"type": "string", "enum": ["year", "month", "week"], "description": "Type of period: 'year', 'month', or 'week'"},
            "period_value": {"type": "string", "description": "Period value: year (e.g., '2025'), month (e.g., '1/2026'), or week (e.g., '3/1/2026')"},
            "stations": {"type": "array", "items": {"type": "string"}, "description": "Optional: List of specific stations"},
            "compare_years": {"type": "integer", "default": 1, "minimum": 1, "maximum": 5, "description": "Số năm cùng kỳ để so sánh. User nói 'thống kê năm 2025' → compare_years=1 (chỉ Bảng 1). User nói 'so sánh với 3 năm cùng kỳ' → compare_years=3 (4 cột). Cấm gọi tool 2 lần với 2 giá trị khác nhau."},
        },
        "required": ["period_type", "period_value"],
        "additionalProperties": False,
    },
}

rainfall_range_statistics_function = {
    "name": "get_songhinh_rainfall_range_statistics",
    "description": """Get rainfall statistics for a date range (from one month to another) for Song Hinh.""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_month": {"type": "integer"},
            "start_year": {"type": "integer"},
            "end_month": {"type": "integer"},
            "end_year": {"type": "integer"},
            "stations": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["start_month", "start_year", "end_month", "end_year"],
        "additionalProperties": False,
    },
}

rainfall_daily_statistics_function = {
    "name": "get_songhinh_rainfall_daily_statistics",
    "description": """Get detailed daily rainfall statistics for a specific date range for Song Hinh.
    Use this when user asks "Thống kê lượng mưa từ ngày X đến ngày Y" or "lượng mưa từ 1/12/2025 đến 31/12/2025".
    Returns a detailed table showing rainfall for each day with all stations.""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "Start date in format 'DD/MM/YYYY' (e.g., '1/12/2025')"},
            "end_date": {"type": "string", "description": "End date in format 'DD/MM/YYYY' (e.g., '31/12/2025')"},
            "stations": {"type": "array", "items": {"type": "string"}, "description": "Optional: List of specific stations"},
        },
        "required": ["start_date", "end_date"],
        "additionalProperties": False,
    },
}

hierarchical_statistics_function = {
    "name": "get_songhinh_hierarchical_statistics",
    "description": """Thống kê phân cấp Qve và Mực nước hồ theo năm/tháng/tuần cho Sông Hinh.

QUY TẮC CHỌN THEO TÊN HỒ - BẮT BUỘC:
- **CHỈ DÙNG** khi user nói "Sông Hinh", "Song Hinh", "SH" (ví dụ: "thống kê MNH Sông Hinh", "so sánh Qve hồ Sông Hinh năm 2025").
- **CẤM DÙNG** khi user nói "Vĩnh Sơn", "Vinh Son", "hồ Vĩnh Sơn" → khi đó PHẢI dùng get_vinhson_hierarchical_statistics, KHÔNG dùng tool này.

NGUỒN DỮ LIỆU SHEET SÔNG HINH - BẮT BUỘC:
- **Qve:** CHỈ lấy cột F (Lưu lượng về 2026 / Qv 2026 m3/s). KHÔNG lấy cột G (Qv 2025). So sánh theo năm lọc theo ngày từ cột F.
- Chỉ dùng các cột A (ngày), B (Mực nước TL), C, D, E, F. Cột G (Qve 2025) không lấy.

QUAN TRỌNG - ĐÂY LÀ TOOL CHO QVE VÀ MỰC NƯỚC:
- **KHI USER HỎI VỀ QVE** → PHẢI DÙNG TOOL NÀY (KHÔNG dùng rainfall_statistics)
- **KHI USER HỎI VỀ MỰC NƯỚC** → PHẢI DÙNG TOOL NÀY (KHÔNG dùng rainfall_statistics)
- **KHI USER HỎI "THỐNG KÊ"** với date range → PHẢI DÙNG TOOL NÀY (KHÔNG dùng operational_data)
- Ví dụ: "Thống kê Qve Sông Hinh tháng 12/2025" → DÙNG TOOL NÀY
- Ví dụ: "Thống kê Qve năm 2025 Sông Hinh" → DÙNG TOOL NÀY
- Ví dụ: "Thống kê mực nước tháng X Sông Hinh" → DÙNG TOOL NÀY
- Ví dụ: "Thống kê lưu lượng về Sông Hinh từ 1/1/2026 đến 13/1/2026" → DÙNG TOOL NÀY với start_date="1/1/2026", end_date="13/1/2026" (trả về thống kê theo ngày cho toàn bộ khoảng thời gian)
- Ví dụ: "Thống kê Qve Sông Hinh từ ngày X đến ngày Y" → DÙNG TOOL NÀY với start_date và end_date

SO SÁNH THEO NĂM (giống lượng mưa - nhiều cột trong 1 bảng). Áp dụng cho CẢ Qve VÀ MNH (mực nước):
- **Qve:** "Thống kê Qve hồ Sông Hinh năm 2026 với 2 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=2, parameters=["qve"]. Bảng 3 cột: 2026 | 2025 | 2024.
- **Qve:** "Thống kê Qve ... năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["qve"]. Bảng 4 cột.
- **MNH (mực nước):** "Thống kê MNH / mực nước hồ Sông Hinh năm 2026 với 2 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=2, parameters=["water_level"]. Bảng 3 cột.
- **MNH:** "Thống kê mực nước ... năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["water_level"]. Bảng 4 cột. GỌI 1 LẦN.

WHEN TO USE:
- User asks "thống kê Qve năm 2025 Sông Hinh" → period_type="year", period_value="2025", parameters=["qve"]
- User asks "thống kê Qve năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["qve"]
- User asks "thống kê MNH / mực nước năm 2026 với 3 năm cùng kỳ" → period_type="year", period_value="2026", compare=True, compare_years=3, parameters=["water_level"]
- User asks "thống kê Qve tháng 12/2025 Sông Hinh" → period_type="month", period_value="12/2025", parameters=["qve"]
- User asks "thống kê mực nước tháng X Sông Hinh" → period_type="month", period_value="X/YYYY", parameters=["water_level"]
- User asks "thống kê lưu lượng về Sông Hinh từ X đến Y" → Dùng start_date="X", end_date="Y" (format DD/MM/YYYY) - sẽ trả về thống kê theo ngày cho toàn bộ khoảng thời gian
- User chỉ hỏi về Qve và mực nước (không cần Qcm, Qxl)
- User muốn thống kê phân cấp: năm→tháng, tháng→tuần, tuần→ngày

QUAN TRỌNG - SO SÁNH THÁNG: GỌI CHỈ 1 LẦN. Áp dụng cho CẢ Qve VÀ MNH (mực nước):
- **Qve:** "So sánh Qve tháng X với tháng Y" → period_type="month", period_value="X", compare_with_period_value="Y", parameters=["qve"]. 1 bảng 2 cột theo ngày.
- **MNH:** "So sánh mực nước / MNH tháng X với tháng Y" → cùng trên nhưng parameters=["water_level"].
- **2 năm cùng kỳ:** "So sánh Qve tháng 1/2026 với tháng 1 của 2 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=2, parameters=["qve"]. Bảng theo ngày, 3 cột: 1/2026 | 1/2025 | 1/2024.
- **3 năm cùng kỳ:** "So sánh Qve tháng 1/2026 với tháng 1 của 3 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=3, parameters=["qve"]. Bảng theo ngày, 4 cột: 1/2026 | 1/2025 | 1/2024 | 1/2023.
- **3 năm cùng kỳ (MNH):** "Thống kê MNH tháng 1/2026 với 3 năm cùng kỳ" → period_type="month", period_value="1/2026", compare=True, compare_years=3, parameters=["water_level"]. Bảng theo ngày, 4 cột.
- KHÔNG gọi 2 hoặc 3 lần. Luôn 1 lần gọi.

QUAN TRỌNG - DATE RANGE:
- Khi user hỏi "thống kê từ X đến Y", sử dụng start_date và end_date (format DD/MM/YYYY)
- Tool sẽ trả về thống kê theo ngày cho toàn bộ khoảng thời gian từ start_date đến end_date
- Không cần chỉ định period_type khi có start_date và end_date

KHÔNG DÙNG KHI:
- User hỏi về MƯA (rainfall) → Dùng get_songhinh_rainfall_statistics
- User hỏi "báo cáo" hoặc "dữ liệu" (không phải "thống kê") → Dùng get_songinh_operational_data
""",
    "parameters": {
        "type": "object",
        "properties": {
            "period_type": {"type": "string", "enum": ["year", "month", "week"], "description": "Type of period. Optional if start_date and end_date are provided."},
            "period_value": {"type": "string", "description": "Period value. Optional if start_date and end_date are provided."},
            "parameters": {"type": "array", "items": {"type": "string", "enum": ["qve", "water_level"]}},
            "compare": {"type": "boolean", "default": False},
            "compare_years": {"type": "integer", "default": 1, "minimum": 1, "maximum": 5, "description": "Khi so sánh theo năm: số năm cùng kỳ. 2 → 3 cột (năm hỏi + 2 năm trước), 3 → 4 cột. Dùng cùng compare=True."},
            "compare_with_period_value": {"type": "string", "description": "Optional: Khi so sánh 2 kỳ (vd tháng 1/2026 với 1/2025): truyền kỳ thứ hai, ví dụ '1/2025'. GỌI 1 LẦN với period_value='1/2026' và compare_with_period_value='1/2025'."},
            "start_date": {"type": "string", "description": "Start date in format 'DD/MM/YYYY' (e.g., '1/1/2026'). Use with end_date to get daily statistics for a date range."},
            "end_date": {"type": "string", "description": "End date in format 'DD/MM/YYYY' (e.g., '13/1/2026'). Must be provided if start_date is specified."},
        },
        "required": [],
        "additionalProperties": False,
    },
}

forecast_function = {
    "name": "get_songhinh_forecast",
    "description": """Dự báo Qve và Sản lượng cho tháng hoặc năm tới cho Sông Hinh.

KHI NÀO DÙNG:
- User hỏi "dự báo", "dự đoán", "forecast", "lên kịch bảng" cho Sông Hinh tháng X hoặc năm Y
- Ví dụ: "dự báo Qve Sông Hinh tháng 4/2026"
- Ví dụ: "dự báo sản lượng Sông Hinh năm 2026"
- Ví dụ: "lên kịch bảng cho Sông Hinh tháng tới"

CÁCH TÍNH DỰ BÁO:
1. Tìm tháng/năm có dữ liệu gần nhất trước thời điểm cần dự báo
2. So sánh với các năm liền kề để tìm năm có Qve gần với trung bình nhất
3. Dùng Qve, lượng mưa của năm đó để dự báo cho tháng/năm tới

VÍ DỤ:
- "dự báo Qve Sông Hinh tháng 4/2026" → target_month=4, target_year=2026
- "dự báo sản lượng Sông Hinh năm 2026" → target_year=2026 (không cần target_month)
- "dự báo Sông Hinh tháng tới" → tự động xác định tháng tới

OUTPUT: Bảng phân tích + dự báo Qve và lượng mưa
""",
    "parameters": {
        "type": "object",
        "properties": {
            "target_month": {"type": "integer", "description": "Tháng cần dự báo (1-12). Ví dụ: 4 cho tháng 4."},
            "target_year": {"type": "integer", "description": "Năm cần dự báo. Ví dụ: 2026."}
        },
        "required": ["target_year"],
        "additionalProperties": False
    }
}
