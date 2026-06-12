analyze_hydro_data_function = {
    "name": "analyze_hydro_data",
    "description": """Analyze internal hydrological data in a read-only workspace.

WHEN TO USE:
- User asks for a flexible/ad-hoc summary of rainfall, realtime water level, or H-V curve data.
- User asks "phân tích", "tóm tắt", "bất thường", "xu hướng" for hydrological data.

READ-ONLY: This tool only reads internal Django data. It does not write or update anything.

DATA TYPES:
- water_volume_curve: H-V relationship table for a reservoir.
- rainfall: VRAIN rainfall data by date range.
- realtime_water_level: realtime reservoir water level snapshots by date range.
""",
    "parameters": {
        "type": "object",
        "properties": {
            "data_type": {
                "type": "string",
                "enum": ["water_volume_curve", "rainfall", "realtime_water_level"],
                "description": "Type of internal data to analyze.",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir/factory name, e.g. Song Hinh, Vinh Son, Vinh Son A, Vinh Son B, Vinh Son C, TKT.",
            },
            "start_date": {
                "type": "string",
                "description": "Optional start date for time-series data, format YYYY-MM-DD or DD/MM/YYYY.",
            },
            "end_date": {
                "type": "string",
                "description": "Optional end date for time-series data, format YYYY-MM-DD or DD/MM/YYYY.",
            },
            "stations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional rainfall station column names. If omitted, stations are selected from reservoir context.",
            },
            "limit": {
                "type": "integer",
                "minimum": 10,
                "maximum": 1000,
                "default": 300,
                "description": "Maximum rows to read.",
            },
        },
        "required": ["data_type"],
        "additionalProperties": False,
    },
}


compare_hydro_periods_function = {
    "name": "compare_hydro_periods",
    "description": """Compare two periods using internal hydrological data in a read-only workspace.

WHEN TO USE:
- User asks to compare rainfall or realtime water level between two date ranges.
- User asks whether one period is higher/lower than another.

READ-ONLY: This tool only reads internal Django data. It does not write or update anything.
For official volume, flow, or spillway calculations, use water_tools after this comparison if needed.
""",
    "parameters": {
        "type": "object",
        "properties": {
            "data_type": {
                "type": "string",
                "enum": ["rainfall", "realtime_water_level"],
                "description": "Time-series data type to compare.",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir/factory name, e.g. Song Hinh, Vinh Son, Vinh Son A, Vinh Son B, Vinh Son C.",
            },
            "current_start": {"type": "string", "description": "Current period start date, YYYY-MM-DD or DD/MM/YYYY."},
            "current_end": {"type": "string", "description": "Current period end date, YYYY-MM-DD or DD/MM/YYYY."},
            "compare_start": {"type": "string", "description": "Comparison period start date, YYYY-MM-DD or DD/MM/YYYY."},
            "compare_end": {"type": "string", "description": "Comparison period end date, YYYY-MM-DD or DD/MM/YYYY."},
            "stations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional rainfall station column names.",
            },
        },
        "required": ["data_type", "current_start", "current_end", "compare_start", "compare_end"],
        "additionalProperties": False,
    },
}


get_unit_state_profile_function = {
    "name": "get_unit_state_profile",
    "description": """Lấy thông tin trạng thái hoạt động tích hợp của một tổ máy (bao gồm cả thông số vận hành điện và thông số cơ/nhiệt/làm mát) tại một thời điểm hoặc trong một ngày cụ thể. Dùng khi cần phân tích mối tương quan giữa nhiệt độ các ổ đỡ/cuộn dây, lưu lượng nước làm mát, và công suất phát (P)/dòng điện (I) của tổ máy.

    IMPORTANT DEVICE MAPPING:
    - Nếu người dùng hỏi MBA/máy biến áp/biến áp/transformer T1/T2/T3/T4 thì không dùng H1/H2.
    - Sông Hinh MBA T1 -> device_code="SH.TB.TPP.110.T1", parameter_code="nhiet_do_mba_t1".
    - Sông Hinh MBA T2 -> device_code="SH.TB.TPP.110.T2", parameter_code="nhiet_do_mba_t2".
    - Sông Hinh MBA T3/T4 -> device_code="SH.TB.TPP.22.T3"/"SH.TB.TPP.22.T4".
    - Vĩnh Sơn MBA T1/T2 -> device_code="VS.TB.TPP.T1"/"VS.TB.TPP.T2", parameter_code="nhiet_do_cuon_day_t1"/"nhiet_do_cuon_day_t2".
    
    WHEN TO USE:
    - Khi người dùng hỏi về hoạt động của tổ máy H1, H2 hoặc trạm (ví dụ: nhiệt độ, làm mát, lưu lượng).
    - Khi người dùng hỏi về nhiệt độ/nấc phân áp/mức dầu MBA T1/T2/T3/T4 hoặc máy biến áp của trạm.
    - Khi người dùng yêu cầu phân tích tương quan giữa nhiệt độ ổ đỡ/ổ hướng tuabin/ổ hướng máy phát và lưu lượng nước làm mát.
    - Khi người dùng hỏi xem giá trị đo được (như lưu lượng chèn trục 5.0 l/p) có bất thường hoặc an toàn không, ta cần xem cả tải công suất hiện tại để phân tích sâu hơn.
    
    PARAMETER CODE MAPPING:
    - "nhiệt độ ổ hướng tuabin", "ổ hướng tuabine", "ổ hướng turbine" -> parameter_code="nhiet_do_o_huong_tuabin".
    - "lưu lượng ổ hướng tuabin" -> parameter_code="luu_luong_o_huong_tuabin".
    - "nhiệt độ ổ hướng máy phát" -> parameter_code="nhiet_do_o_huong_may_phat".
    - "nhiệt độ ổ đỡ", "ổ đỡ máy phát" -> parameter_code="nhiet_do_o_do".
    Không dùng "nhiet_do_o_do" khi người dùng hỏi "ổ hướng tuabin".
    """,
    "parameters": {
        "type": "object",
        "properties": {
            "device_code": {
                "type": "string",
                "description": "Mã đầy đủ của thiết bị cần phân tích, có thể là tổ máy hoặc trạm/MBA. Ví dụ: 'SH.TB.H1' (Tổ máy H1 Sông Hinh), 'SH.TB.H2', 'VS.TB.H1', 'VS.TB.H2', 'SH.TB.TPP.110.T1' (MBA T1 Sông Hinh), 'SH.TB.TPP.110.T2', 'VS.TB.TPP.T1' (MBA T1 Vĩnh Sơn). Không dùng H1/H2 khi người dùng hỏi MBA/máy biến áp T1/T2."
            },
            "date": {
                "type": "string",
                "description": "Ngày cần truy vấn dữ liệu (Định dạng YYYY-MM-DD). Mặc định là ngày gần nhất có dữ liệu nếu không cung cấp."
            },
            "time": {
                "type": "string",
                "description": "Optional: Mốc giờ cụ thể cần phân tích (Định dạng HH:MM, ví dụ '07:00', '08:30'). Nếu không cung cấp, sẽ trả về dữ liệu cả ngày để phân tích xu hướng."
            },
            "window": {
                "type": "string",
                "description": "Cửa sổ thời gian để phân tích xu hướng (ví dụ: '30m', '60m', '120m'). Mặc định là '60m'."
            },
            "parameter_code": {
                "type": "string",
                "description": "Optional: Mã của thông số cụ thể cần truy vấn. Ví dụ: 'nhiet_do_o_huong_tuabin' cho nhiệt độ ổ hướng tuabin, 'nhiet_do_o_do' cho nhiệt độ ổ đỡ, 'luu_luong_chen_truc' cho lưu lượng chèn trục, 'nhiet_do_mba_t1' cho nhiệt độ MBA T1 Sông Hinh, 'nhiet_do_cuon_day_t1' cho MBA T1 Vĩnh Sơn. Nếu cung cấp, chỉ trả về thông số này và các thông số liên quan."
            }
        },
        "required": ["device_code"],
        "additionalProperties": False,
    }
}


ANALYSIS_TOOLS = [
    {"type": "function", "function": analyze_hydro_data_function},
    {"type": "function", "function": compare_hydro_periods_function},
    {"type": "function", "function": get_unit_state_profile_function},
]
