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


ANALYSIS_TOOLS = [
    {"type": "function", "function": analyze_hydro_data_function},
    {"type": "function", "function": compare_hydro_periods_function},
]
