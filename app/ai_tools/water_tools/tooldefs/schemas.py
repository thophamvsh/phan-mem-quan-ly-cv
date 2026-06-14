"""
OpenAI function definitions (tool schemas)
"""

water_level_function = {
    "name": "get_water_volume",
    "description": """REQUIRED: Get the volume (Dung tích) of water in the reservoir based on water level (Mực nước).

QUAN TRỌNG - RESERVOIR SELECTION:
- Khi user hỏi về một hồ cụ thể (ví dụ: "hồ A Vĩnh Sơn", "Vinh Son A"), CHỈ truy vấn hồ đó.
- KHÔNG tự động truy vấn tất cả các hồ A, B, C nếu user không yêu cầu.

RESERVOIRS:
- "Sông Hinh" or "Song Hinh": mực nước chết = 196m, mực nước dâng bình thường = 209m, Range: 196-213m
- "TKT" or "Thượng Kon Tum" or "Thượng Kontum": Water level range 1135-1165m
- "Vĩnh Sơn A" or "Vinh Son A": mực nước chết = 765m, mực nước dâng bình thường = 775m, Range: 765-780m
- "Vĩnh Sơn B" or "Vinh Son B": mực nước chết = 813.6m, mực nước dâng bình thường = 826m, Range: 813-832m
- "Vĩnh Sơn C" or "Vinh Son C": mực nước chết = 971.3m, mực nước dâng bình thường = 981m, Range: 971-988m

Extract reservoir name from user query. If not specified, default to "Sông Hinh".

You MUST use this function whenever the user asks about water level or volume. Do NOT estimate or guess.""",
    "parameters": {
        "type": "object",
        "properties": {
            "water_level": {
                "type": "number",
                "description": "The water level in meters (Mực nước hồ). Can be decimal number like 196.01 or 1135.5.",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Options: 'Sông Hinh', 'TKT', 'Thượng Kon Tum', 'Vĩnh Sơn', 'Vĩnh Sơn A', 'Vĩnh Sơn B', 'Vĩnh Sơn C'. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "TKT", "Thượng Kon Tum", "Thuong Kon Tum", "Thượng Kontum", "Vĩnh Sơn", "Vinh Son", "Vĩnh Sơn A", "Vinh Son A", "Vĩnh Sơn B", "Vinh Son B", "Vĩnh Sơn C", "Vinh Son C", "VS A", "VS B", "VS C"]
            },
        },
        "required": ["water_level"],
        "additionalProperties": False
    }
}

useful_volume_function = {
    "name": "get_useful_volume",
    "description": """REQUIRED: Calculate total useful volume of a reservoir (between mực nước chết and mực nước dâng bình thường).

WHEN TO USE:
- User asks "tổng dung tích hữu ích của hồ X"
- User asks "dung tich hữu ích Vĩnh Sơn"
- User asks "tổng dung tích Sông Hinh"

Công thức: Dung tích hữu ích = V(mực nước dâng bình thường) - V(mực nước chết)

RESERVOIRS:
- "Sông Hinh": mực nước chết = 196m, mực nước dâng bình thường = 209m
- "Vĩnh Sơn A": mực nước chết = 765m, mực nước dâng bình thường = 775m
- "Vĩnh Sơn B": mực nước chết = 813.6m, mực nước dâng bình thường = 826m
- "Vĩnh Sơn C": mực nước chết = 971.3m, mực nước dâng bình thường = 981m

EXAMPLES:
- "Tổng dung tích hữu ích hồ Sông Hinh" → reservoir="Sông Hinh"
- "Dung tích hữu ích Vĩnh Sơn A" → reservoir="Vĩnh Sơn A"
""",
    "parameters": {
        "type": "object",
        "properties": {
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Options: 'Sông Hinh', 'Vĩnh Sơn A', 'Vĩnh Sơn B', 'Vĩnh Sơn C'. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "Vĩnh Sơn", "Vinh Son", "Vĩnh Sơn A", "Vinh Son A", "Vĩnh Sơn B", "Vinh Son B", "Vĩnh Sơn C", "Vinh Son C"]
            },
        },
        "required": [],
        "additionalProperties": False
    }
}

flood_control_volume_function = {
    "name": "get_flood_control_volume",
    "description": """REQUIRED: Calculate flood control volume at a given water level.

WHEN TO USE:
- User asks "dung tich phong lu cua hồ X"
- User asks "với mực nước Y dung tích phòng lũ bao nhiêu"
- User asks "dung tich trống lũ"

Công thức: Dung tích phòng lũ = V(MNDBT) - V(mực nước hiện tại)

RESERVOIRS:
- "Sông Hinh": MNDBT = 209m
- "Vĩnh Sơn A": MNDBT = 775m
- "Vĩnh Sơn B": MNDBT = 826m
- "Vĩnh Sơn C": MNDBT = 981m

EXAMPLES:
- "Với mực nước 206.5m dung tích phòng lũ của Sông Hinh bao nhiêu?" → water_level=206.5, reservoir="Sông Hinh"
- "Dung tích phòng lũ hồ Vĩnh Sơn A tại 770m" → water_level=770, reservoir="Vĩnh Sơn A"
""",
    "parameters": {
        "type": "object",
        "properties": {
            "water_level": {
                "type": "number",
                "description": "Current water level in meters",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Options: 'Sông Hinh', 'Vĩnh Sơn A', 'Vĩnh Sơn B', 'Vĩnh Sơn C'. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "Vĩnh Sơn", "Vinh Son", "Vĩnh Sơn A", "Vinh Son A", "Vĩnh Sơn B", "Vinh Son B", "Vĩnh Sơn C", "Vinh Son C"]
            },
        },
        "required": ["water_level"],
        "additionalProperties": False
    }
}

flow_rate_function = {
    "name": "calculate_flow_rate",
    "description": """REQUIRED: Calculate the flow rate (Lưu lượng) needed to change water level over time.

WHEN TO USE:
- User asks about "lưu lượng" (flow rate)
- User asks "how much water" to reach a level
- User mentions time: "trong vòng X ngày/giờ" (in X days/hours)
- Query structure: "level A → level B in X time"

RESERVOIRS AND WATER LEVELS:
- "Sông Hinh": mực nước chết = 196m, mực nước dâng bình thường = 209m, Range: 196-213m
- "Vĩnh Sơn A": mực nước chết = 765m, mực nước dâng bình thường = 775m, Range: 765-780m
- "Vĩnh Sơn B": mực nước chết = 813.6m, mực nước dâng bình thường = 826m, Range: 813-832m
- "Vĩnh Sơn C": mực nước chết = 971.3m, mực nước dâng bình thường = 981m, Range: 971-988m
- "TKT" or "Thượng Kon Tum": Range: 1135-1165m
- "Vĩnh Sơn A" or "Vinh Son A": mực nước chết = 765m, mực nước dâng bình thường = 775m, Range: 765-780m

QUAN TRỌNG: Khi user hỏi về một hồ cụ thể, CHỈ truy vấn hồ đó.

Extract reservoir name from user query. If not specified, default to "Sông Hinh".

CRITICAL TIME CONVERSION:
- If time is in HOURS (giờ/h): MUST divide by 24 to get days
  Example: 17h → time_days=0.708 (17/24)
  Example: 48h → time_days=2 (48/24)
- If time is in DAYS (ngày): use directly
  Example: 2 ngày → time_days=2
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_level": {
                "type": "number",
                "description": "Starting water level in meters (Mực nước bắt đầu)",
            },
            "end_level": {
                "type": "number",
                "description": "Target/ending water level in meters (Mực nước kết thúc)",
            },
            "time_days": {
                "type": "number",
                "description": "Time period in DAYS (decimal allowed). CRITICAL: If user says hours (giờ/h), you MUST convert: time_days = hours / 24. Examples: 17h → 0.708, 48h → 2, 6h → 0.25",
            },
            "discharge_rate": {
                "type": "number",
                "description": "Optional: Discharge/outflow rate in m³/s. Extract from: 'chạy máy', 'xả', 'discharge', 'Qcm', 'Qxa'. If both Qcm and Qxa given, sum them: discharge_rate = Qcm + Qxa. Otherwise omit.",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Options: 'Sông Hinh', 'TKT', 'Thượng Kon Tum', 'Vĩnh Sơn', 'Vĩnh Sơn A', 'Vĩnh Sơn B', 'Vĩnh Sơn C'. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "TKT", "Thượng Kon Tum", "Thuong Kon Tum", "Thượng Kontum", "Vĩnh Sơn", "Vinh Son", "Vĩnh Sơn A", "Vinh Son A", "Vĩnh Sơn B", "Vinh Son B", "Vĩnh Sơn C", "Vinh Son C", "VS A", "VS B", "VS C"]
            },
        },
        "required": ["start_level", "end_level", "time_days"],
        "additionalProperties": False
    }
}

ramping_discharge_function = {
    "name": "calculate_ramping_discharge",
    "description": """REQUIRED: Calculate ramping discharge schedule (linear increase) given STARTING discharge.

WHEN TO USE:
- User has AVERAGE discharge rate (Qxa trung bình)
- User provides STARTING discharge (bắt đầu từ X m³/s)
- User asks "tăng dần", "phân bổ", "schedule", "lịch xả"
- Query structure: "Qxa = X m³/s, bắt đầu từ Y m³/s, tăng dần như thế nào?"

EXAMPLE:
"Qxa = 950 m³/s trong 3 ngày, bắt đầu từ 300 m³/s, tăng dần thế nào?"
→ avg_discharge=950, start_discharge=300, time_days=3

OUTPUT:
- Ending discharge (Q_end = 2*Q_avg - Q_start)
- Rate of increase (m³/s per day/hour)
- Hourly/daily discharge schedule
""",
    "parameters": {
        "type": "object",
        "properties": {
            "avg_discharge": {
                "type": "number",
                "description": "Average discharge rate over the period (m³/s). This is the Qxa value user wants to achieve on average.",
            },
            "time_days": {
                "type": "number",
                "description": "Time period in days",
            },
            "start_discharge": {
                "type": "number",
                "description": "Starting discharge rate (m³/s). The initial flow rate at time=0.",
            },
        },
        "required": ["avg_discharge", "time_days", "start_discharge"],
        "additionalProperties": False
    }
}

ramping_from_max_function = {
    "name": "calculate_ramping_from_max",
    "description": """REQUIRED: Calculate ramping discharge schedule given MAX discharge constraint (inverse problem).

WHEN TO USE:
- User has AVERAGE discharge rate (Qxa trung bình)
- User provides MAX discharge constraint (max không quá X m³/s, Q_max = X)
- User asks "bắt đầu xả bao nhiêu?" or "tăng như thế nào?" WITHOUT specifying start
- Query structure: "Qxa = X m³/s, max không quá Y m³/s, bắt đầu bao nhiêu?"

EXAMPLE:
"Qxa = 950 m³/s trong 3 ngày, max không quá 1500 m³/s, bắt đầu xả bao nhiêu?"
→ avg_discharge=950, max_discharge=1500, time_days=3

OUTPUT:
- Starting discharge (Q_start = 2*Q_avg - Q_max) - what we solve for
- Rate of increase (m³/s per day/hour)
- Hourly/daily discharge schedule
- Verification that Q_max is not exceeded
""",
    "parameters": {
        "type": "object",
        "properties": {
            "avg_discharge": {
                "type": "number",
                "description": "Average discharge rate over the period (m³/s). This is the Qxa value user wants to achieve on average.",
            },
            "time_days": {
                "type": "number",
                "description": "Time period in days",
            },
            "max_discharge": {
                "type": "number",
                "description": "Maximum allowed discharge rate (m³/s). The upper limit constraint.",
            },
        },
        "required": ["avg_discharge", "time_days", "max_discharge"],
        "additionalProperties": False
    }
}

practical_ramping_function = {
    "name": "calculate_practical_ramping",
    "description": """REQUIRED: Calculate PRACTICAL ramping discharge schedule with REAL-WORLD constraints.

WHEN TO USE:
- User mentions "thực tế", "vận hành", "practical", "thực hiện"
- User wants ramping schedule that follows hydropower operation rules
- User asks about step-wise increase with specific intervals

REAL-WORLD CONSTRAINTS:
1. All discharge values MUST be multiples of 50 (e.g., 50, 100, 150, 200, 250, ...)
2. Step size MUST be one of: 50, 100, 150, 200, 250, 400 m³/s
3. Cycle time depends on total duration:
   - < 1 day: 2h or 4h cycles
   - 1-3 days: 6h cycles
   - 3-7 days: 12h cycles
   - > 7 days: 24h cycles

EXAMPLES:
"Qxa = 950 m³/s trong 3 ngày, bắt đầu 300 m³/s, lịch vận hành thực tế?"
→ avg_discharge=950, start_discharge=300, time_days=3

"Qxa = 950 m³/s trong 3 ngày, max 1500 m³/s, lịch thực tế?"
→ avg_discharge=950, max_discharge=1500, time_days=3

OUTPUT:
- Rounded discharge values (multiples of 50)
- Practical step size from allowed list
- Detailed operation schedule with cycle times
- Safety notes and operation guidelines
""",
    "parameters": {
        "type": "object",
        "properties": {
            "avg_discharge": {
                "type": "number",
                "description": "Average discharge rate over the period (m³/s). Will be rounded to nearest 50.",
            },
            "time_days": {
                "type": "number",
                "description": "Time period in days. Used to determine cycle time.",
            },
            "start_discharge": {
                "type": "number",
                "description": "Optional: Starting discharge rate (m³/s). Will be rounded to nearest 50. Use if user specifies starting value.",
            },
            "max_discharge": {
                "type": "number",
                "description": "Optional: Maximum discharge constraint (m³/s). Will be rounded down to nearest 50. Use if user specifies max limit.",
            },
        },
        "required": ["avg_discharge", "time_days"],
        "additionalProperties": False
    }
}

detailed_spillway_schedule_function = {
    "name": "create_detailed_spillway_schedule",
    "description": """REQUIRED: Create DETAILED ramping schedule AFTER user has chosen a strategy.

WHEN TO USE:
- User has ALREADY CHOSEN a specific option from calculate_spillway_ramping
- User says "chọn phương án X" or "option X"
- User specifies exact parameters: "Qxa start=X, end=Y, step=Z, chu kỳ=W"
- User wants to see DETAILED schedule with specific parameters

THIS IS STEP 2 - Use AFTER showing options!

CRITICAL: ALWAYS include start_level and end_level from the ORIGINAL query!
- Extract from conversation history: "mực nước từ 209m về 207m"
- Extract from conversation history: "mnh 209 về 207"
- These are REQUIRED for water level tracking in the schedule!

IMPORTANT: Extract parameters from user's choice:
- If user says "chọn phương án 1" → extract start/end from that option
- If user specifies "Qxa bắt đầu 100, kết thúc 550, bước 50, chu kỳ 6h" → use those values
- ALWAYS include start_level and end_level from original query

EXAMPLES:
Original query: "Qxa tăng dần trong 70h để mnh 209 về 207m với Qve=200, Qcm=53"
User chooses: "Chọn phương án 2"
→ start_discharge=100, end_discharge=570, cycle_hours=6, step_size=50,
   start_level=209, end_level=207, time_days=70/24, inflow_rate=200, turbine_discharge=53

OUTPUT:
- Hour-by-hour schedule table WITH water level column
- Step-by-step operation guide
- Safety instructions
- Mathematical verification
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_discharge": {
                "type": "number",
                "description": "Starting Qxa in m³/s (must be multiple of 50, minimum 50)",
            },
            "end_discharge": {
                "type": "number",
                "description": "Ending Qxa in m³/s (must be multiple of 50)",
            },
            "time_days": {
                "type": "number",
                "description": "Time period in DAYS. Convert hours to days if needed.",
            },
            "cycle_hours": {
                "type": "number",
                "description": "Adjustment cycle in hours. Common values: 1, 2, 4, 6, 12, 24. Default: 6",
            },
            "step_size": {
                "type": "number",
                "description": "Step size in m³/s. Must be one of: 50, 100, 150, 200, 250, 400. Default: 50",
            },
            "inflow_rate": {
                "type": "number",
                "description": "Inflow rate (Qve) in m³/s",
            },
            "turbine_discharge": {
                "type": "number",
                "description": "Turbine discharge (Qcm) in m³/s",
            },
            "start_level": {
                "type": "number",
                "description": "Optional: Starting water level in meters (for context)",
            },
            "end_level": {
                "type": "number",
                "description": "Optional: Target water level in meters (for context)",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "TKT", "Thượng Kon Tum", "Thuong Kon Tum", "Thượng Kontum"]
            },
        },
        "required": ["start_discharge", "end_discharge", "time_days", "inflow_rate", "turbine_discharge"],
        "additionalProperties": False
    }
}

spillway_ramping_function = {
    "name": "calculate_spillway_ramping",
    "description": """REQUIRED: Calculate RAMPING spillway discharge schedule given water level targets.

WHEN TO USE:
- User asks "Qxa tăng dần từ thấp đến cao"
- User wants ramping discharge to achieve target water level
- User provides Qve, Qcm and asks for ramping Qxa schedule
- Complex query: "Qxa từ X đến Y để mực nước từ A về B"

THIS IS THE MOST COMPREHENSIVE TOOL - use it for complex ramping scenarios!

EXAMPLES:
"Qxa tăng dần từ thấp đến cao trong 70 giờ để mnh 209 về 207m với Qve=200, Qcm=53, Qxa_max=2000"
→ start_level=209, end_level=207, time_days=70/24, inflow_rate=200, turbine_discharge=53, max_discharge=2000

"Qxa bắt đầu từ 100 m³/s tăng dần để mnh từ 208 đến 206 trong 3 ngày, Qve=150, Qcm=40"
→ start_level=208, end_level=206, time_days=3, inflow_rate=150, turbine_discharge=40, start_discharge=100

ADVANTAGES:
- Automatically calculates required Qxa_avg from water balance
- Tries multiple strategies to find best fit
- Adjusts cycle time and step size for optimization
- Provides multiple alternatives

RESERVOIRS:
- "Sông Hinh": 196-213m
- "TKT" or "Thượng Kon Tum": 1135-1165m
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_level": {
                "type": "number",
                "description": "Starting water level in meters",
            },
            "end_level": {
                "type": "number",
                "description": "Target water level in meters",
            },
            "time_days": {
                "type": "number",
                "description": "Time period in DAYS. Convert hours to days if needed (hours / 24).",
            },
            "inflow_rate": {
                "type": "number",
                "description": "Known inflow rate (Qve) in m³/s",
            },
            "turbine_discharge": {
                "type": "number",
                "description": "Known turbine discharge (Qcm) in m³/s",
            },
            "max_discharge": {
                "type": "number",
                "description": "Optional: Maximum spillway discharge allowed (Qxa_max). Default 2000 m³/s.",
            },
            "start_discharge": {
                "type": "number",
                "description": "Optional: Starting spillway discharge (Qxa_start). If not provided, will be calculated automatically.",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "TKT", "Thượng Kon Tum", "Thuong Kon Tum", "Thượng Kontum"]
            },
        },
        "required": ["start_level", "end_level", "time_days", "inflow_rate", "turbine_discharge"],
        "additionalProperties": False
    }
}

spillway_calculation_function = {
    "name": "calculate_spillway_discharge",
    "description": """REQUIRED: Calculate SINGLE VALUE spillway discharge (Qxa) - NOT ramping.

WHEN TO USE:
- User asks "Qxa bao nhiêu" for CONSTANT discharge (not ramping)
- User wants SINGLE VALUE, not a schedule
- Simple calculation without ramping

NOTE: If user wants RAMPING (tăng dần), use calculate_spillway_ramping instead!

EQUATION:
Qxa = Qve - Qcm - (ΔV / time)

EXAMPLE:
"Với Qve = 300 m³/s, Qcm = 50 m³/s, vậy Qxa bao nhiêu để từ 209.6 về 204.5 trong 3 ngày?"
→ inflow_rate=300, turbine_discharge=50, solve for constant Qxa

RESERVOIRS:
- "Sông Hinh": 196-213m
- "TKT" or "Thượng Kon Tum": 1135-1165m
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_level": {
                "type": "number",
                "description": "Starting water level in meters",
            },
            "end_level": {
                "type": "number",
                "description": "Target water level in meters",
            },
            "time_days": {
                "type": "number",
                "description": "Time period in DAYS. Convert hours to days if needed.",
            },
            "inflow_rate": {
                "type": "number",
                "description": "Known inflow rate (Qve) in m³/s",
            },
            "turbine_discharge": {
                "type": "number",
                "description": "Known turbine discharge (Qcm) in m³/s",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "TKT", "Thượng Kon Tum", "Thuong Kon Tum", "Thượng Kontum"]
            },
        },
        "required": ["start_level", "end_level", "time_days", "inflow_rate", "turbine_discharge"],
        "additionalProperties": False
    }
}

volume_difference_function = {
    "name": "calculate_volume_difference",
    "description": """REQUIRED: Calculate volume DIFFERENCE between two water levels.

WHEN TO USE:
- User asks "từ X đến Y có dung tích bao nhiêu" (volume difference)
- User asks "chênh lệch dung tích" or "thể tích chênh lệch"
- User wants to know ΔV = V(level2) - V(level1)
- Query structure: "mnh từ A đến B có dung tích bao nhiêu"

QUAN TRỌNG - RESERVOIR SELECTION:
- Khi user hỏi về một hồ cụ thể (ví dụ: "hồ A Vĩnh Sơn", "Vinh Son A", "hồ A"), CHỈ truy vấn hồ đó.
- KHÔNG tự động truy vấn tất cả các hồ A, B, C nếu user không yêu cầu.
- Nếu user chỉ nói "Vĩnh Sơn" mà không nói A/B/C, hỏi lại user muốn hồ nào.
- Nếu user chỉ định "hồ A" hoặc "Vinh Son -A", dùng reservoir="Vinh Son A".

EXAMPLES:
- "Mnh hồ A Vĩnh Sơn từ 771.56 đến 772.568 có dung tích bao nhiêu?" → start_level=771.56, end_level=772.568, reservoir="Vinh Son A"
- "Mnh từ 204.5 đến 209 có dung tích bao nhiêu?" → start_level=204.5, end_level=209, reservoir="Sông Hinh"
- "Chênh lệch dung tích giữa 200m và 210m?" → start_level=200, end_level=210

OUTPUT:
- Volume at start_level
- Volume at end_level
- Difference: ΔV = V_end - V_start

RESERVOIRS:
- "Sông Hinh": 196-213m
- "TKT" or "Thượng Kon Tum": 1135-1165m
- "Vĩnh Sơn A" or "Vinh Son A": 765-780m
- "Vĩnh Sơn B" or "Vinh Son B": 813-832m
- "Vĩnh Sơn C" or "Vinh Son C": 971-988m
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_level": {
                "type": "number",
                "description": "Starting water level in meters",
            },
            "end_level": {
                "type": "number",
                "description": "Ending water level in meters",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Options: 'Sông Hinh', 'TKT', 'Thượng Kon Tum', 'Vĩnh Sơn', 'Vĩnh Sơn A', 'Vĩnh Sơn B', 'Vĩnh Sơn C'. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "TKT", "Thượng Kon Tum", "Thuong Kon Tum", "Thượng Kontum", "Vĩnh Sơn", "Vinh Son", "Vĩnh Sơn A", "Vinh Son A", "Vĩnh Sơn B", "Vinh Son B", "Vĩnh Sơn C", "Vinh Son C", "VS A", "VS B", "VS C"]
            },
        },
        "required": ["start_level", "end_level"],
        "additionalProperties": False
    }
}

level_change_function = {
    "name": "calculate_level_change",
    "description": """REQUIRED: Calculate how much the water level CHANGES (drops or rises) given Qve, Qcm and time.

WHEN TO USE:
- User asks "mực nước từ X xuống/tăng bao nhiêu" with Qve and Qcm given
- User asks "Với Qve = X và Qcm = Y trong Z ngày thì mực nước H xuống bao nhiêu?"
- Query: given inflow (Qve), discharge (Qcm), duration (days), starting level → find END level and the drop/rise (m)

EXAMPLES:
- "Với Qve là 20 m3/s và Qcm là 50 m3/s trong 5.5 ngày thì mực nước hồ Sông Hinh 208.37 xuống bao nhiêu?"
  → qve=20, qcm=50, time_days=5.5, start_level=208.37, reservoir="Sông Hinh"
- "Qve 100, Qcm 80, 3 ngày, từ 210m thì mực nước tăng hay giảm bao nhiêu?"
  → qve=100, qcm=80, time_days=3, start_level=210

OUTPUT:
- End water level (m)
- Change in level (drop or rise in m)

RESERVOIRS:
- "Sông Hinh" or "Song Hinh": 196-213m
- "TKT" or "Thượng Kon Tum": 1135-1165m
""",
    "parameters": {
        "type": "object",
        "properties": {
            "qve": {
                "type": "number",
                "description": "Lưu lượng về hồ (Qve) in m³/s",
            },
            "qcm": {
                "type": "number",
                "description": "Lưu lượng chạy máy / xả (Qcm) in m³/s",
            },
            "time_days": {
                "type": "number",
                "description": "Thời gian (ngày). Có thể thập phân, ví dụ 5.5 ngày.",
            },
            "start_level": {
                "type": "number",
                "description": "Mực nước ban đầu (m), ví dụ 208.37",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "TKT", "Thượng Kon Tum", "Thuong Kon Tum", "Thượng Kontum"]
            },
        },
        "required": ["qve", "qcm", "time_days", "start_level"],
        "additionalProperties": False
    }
}

time_calculation_function = {
    "name": "calculate_time_needed",
    "description": """REQUIRED: Calculate the TIME needed to change water level given flow rates.

WHEN TO USE:
- User asks "trong bao lâu" (how long)
- User asks "mất bao nhiêu thời gian" (how much time)
- User asks "bao lâu để mực nước thay đổi"
- Query structure: "how long from level A to level B with flow X"

IMPORTANT: This is OPPOSITE of calculate_flow_rate:
- calculate_flow_rate: given TIME → find FLOW
- calculate_time_needed: given FLOW → find TIME

RESERVOIRS:
- "Sông Hinh": 196-213m
- "TKT" or "Thượng Kon Tum": 1135-1165m

FLOW RATE NOTATION (Ký hiệu chuyên ngành):
- Qve, Q ve, "lưu lượng về" → inflow_rate (m³/s)
- Qcm, Q cm, "lưu lượng chạy máy" → discharge_rate (m³/s)
- Qxa, Q xa, "lưu lượng xả" → discharge_rate (m³/s)
- Note: Both Qcm and Qxa are discharge (outflow)
- If user gives both Qcm and Qxa → discharge_rate = Qcm + Qxa

EXTRACTION EXAMPLES:
- "Qve = 100" → inflow_rate=100, discharge_rate=0
- "Qcm = 30" → inflow_rate=0, discharge_rate=30
- "Qcm = 30, Qxa = 20" → inflow_rate=0, discharge_rate=50 (30+20)
- "Qve = 100, Qcm = 30" → inflow_rate=100, discharge_rate=30
- If not mentioned → default 0
""",
    "parameters": {
        "type": "object",
        "properties": {
            "start_level": {
                "type": "number",
                "description": "Starting water level in meters",
            },
            "end_level": {
                "type": "number",
                "description": "Target water level in meters",
            },
            "inflow_rate": {
                "type": "number",
                "description": "Water inflow rate in m³/s. Extract from: 'lưu lượng về', 'Qve', 'Q ve'. Default 0 if not mentioned.",
            },
            "discharge_rate": {
                "type": "number",
                "description": "Water discharge/outflow rate in m³/s. Extract from: 'lưu lượng xả', 'chạy máy', 'Qcm', 'Qxa'. If both Qcm and Qxa given, sum them: discharge_rate = Qcm + Qxa. Default 0 if not mentioned.",
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir name. Options: 'Sông Hinh', 'TKT', 'Thượng Kon Tum', 'Vĩnh Sơn', 'Vĩnh Sơn A', 'Vĩnh Sơn B', 'Vĩnh Sơn C'. Default: 'Sông Hinh'.",
                "enum": ["Sông Hinh", "Song Hinh", "TKT", "Thượng Kon Tum", "Thuong Kon Tum", "Thượng Kontum", "Vĩnh Sơn", "Vinh Son", "Vĩnh Sơn A", "Vinh Son A", "Vĩnh Sơn B", "Vinh Son B", "Vĩnh Sơn C", "Vinh Son C", "VS A", "VS B", "VS C"]
            },
        },
        "required": ["start_level", "end_level"],
        "additionalProperties": False
    }
}

weekly_limit_levels_function = {
    "name": "get_weekly_limit_levels",
    "description": """REQUIRED: Tra cứu MNGH tuần (mực nước giới hạn tuần) đã cấu hình trong database.

WHEN TO USE:
- User hỏi "MNGH tuần này bao nhiêu?"
- User hỏi "Mực nước giới hạn tuần sau của hồ A Vĩnh Sơn?"
- User hỏi "MNGH tuần 24 năm 2026 của Sông Hinh/Thượng Kon Tum/Vĩnh Sơn A/B?"
- User hỏi "tuần cố định", "tuần X", "week X" liên quan MNGH.

RESERVOIRS:
- "Sông Hinh"
- "Vĩnh Sơn A" / "hồ A Vĩnh Sơn"
- "Vĩnh Sơn B" / "hồ B Vĩnh Sơn"
- "Vĩnh Sơn" means return A and B only.
- "Thượng Kon Tum" / "TKT"
- Do NOT query Vĩnh Sơn C for MNGH because hồ C is not configured.

PARAMETER RULES:
- "tuần này" → week_selector="current"
- "tuần sau" → week_selector="next"
- "tuần 24", "tuần 24 năm 2026" → week_selector="specific", week_number=24, year=2026 if mentioned
- If user asks all reservoirs or does not specify reservoir, use reservoir="all".
- target_date is optional ISO date YYYY-MM-DD; use only when user gives an explicit date.""",
    "parameters": {
        "type": "object",
        "properties": {
            "week_selector": {
                "type": "string",
                "description": "Which week to query: current=tuần này, next=tuần sau, specific=tuần cố định.",
                "enum": ["current", "next", "specific"],
            },
            "reservoir": {
                "type": "string",
                "description": "Reservoir to query. Use 'all' if unspecified. Options: 'all', 'Sông Hinh', 'Vĩnh Sơn', 'Vĩnh Sơn A', 'Vĩnh Sơn B', 'Thượng Kon Tum', 'TKT'.",
                "enum": ["all", "Sông Hinh", "Song Hinh", "Vĩnh Sơn", "Vinh Son", "Vĩnh Sơn A", "Vinh Son A", "Vĩnh Sơn B", "Vinh Son B", "VS A", "VS B", "Thượng Kon Tum", "Thuong Kon Tum", "TKT"],
            },
            "week_number": {
                "type": "integer",
                "description": "Required only for week_selector='specific'. ISO/settings week number, e.g. 24.",
            },
            "year": {
                "type": "integer",
                "description": "Optional year for week_selector='specific'. If omitted, use current ISO year.",
            },
            "target_date": {
                "type": "string",
                "description": "Optional explicit date in YYYY-MM-DD to determine current/next week.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}



# Tools list for OpenAI
TOOLS = [
    {"type": "function", "function": water_level_function},
    {"type": "function", "function": useful_volume_function},
    {"type": "function", "function": flood_control_volume_function},
    {"type": "function", "function": volume_difference_function},
    {"type": "function", "function": level_change_function},
    {"type": "function", "function": flow_rate_function},
    {"type": "function", "function": spillway_ramping_function},
    {"type": "function", "function": detailed_spillway_schedule_function},
    {"type": "function", "function": spillway_calculation_function},
    {"type": "function", "function": ramping_discharge_function},
    {"type": "function", "function": ramping_from_max_function},
    {"type": "function", "function": practical_ramping_function},
    {"type": "function", "function": time_calculation_function},
    {"type": "function", "function": weekly_limit_levels_function}
]
