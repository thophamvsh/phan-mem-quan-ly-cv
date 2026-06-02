"""
Normalizers for Water Tools responses → unified schema: tool, title, summary, table, chart, notes, raw.
"""

from typing import Any, Dict

from ai_tools.tool_format import parse_markdown_blocks


# Tool names (must match tooldefs/schemas.py)
WATER_VOLUME = "get_water_volume"
USEFUL_VOLUME = "get_useful_volume"
FLOOD_CONTROL_VOLUME = "get_flood_control_volume"
VOLUME_DIFF = "calculate_volume_difference"
LEVEL_CHANGE = "calculate_level_change"
FLOW_RATE = "calculate_flow_rate"
TIME_NEEDED = "calculate_time_needed"
RAMPING_DISCHARGE = "calculate_ramping_discharge"
RAMPING_FROM_MAX = "calculate_ramping_from_max"
PRACTICAL_RAMPING = "calculate_practical_ramping"
SPILLWAY_DISCHARGE = "calculate_spillway_discharge"
SPILLWAY_RAMPING = "calculate_spillway_ramping"
DETAILED_SCHEDULE = "create_detailed_spillway_schedule"


def _to_schema(tool_name: str, raw: str, blocks: Dict[str, Any]) -> Dict[str, Any]:
    tables = blocks.get("tables") or []
    return {
        "tool": tool_name,
        "title": (blocks.get("title") or "").strip(),
        "summary": (blocks.get("summary") or "").strip(),
        "table": "\n\n".join(tables).strip() if tables else "",
        "chart": (blocks.get("chart") or "").strip(),
        "excel": (blocks.get("excel") or "").strip(),
        "notes": (blocks.get("notes") or "").strip(),
        "raw": raw,
    }


def _normalize(tool_name: str, raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(tool_name, raw, blocks)


def _preserve_raw(tool_name: str, raw: str) -> Dict[str, Any]:
    return {
        "tool": tool_name,
        "title": "",
        "summary": raw,
        "table": " ",
        "chart": "",
        "excel": "",
        "notes": "",
        "raw": raw,
    }


_NORMALIZERS = {
    WATER_VOLUME: lambda raw: _normalize(WATER_VOLUME, raw),
    USEFUL_VOLUME: lambda raw: _preserve_raw(USEFUL_VOLUME, raw),
    FLOOD_CONTROL_VOLUME: lambda raw: _normalize(FLOOD_CONTROL_VOLUME, raw),
    VOLUME_DIFF: lambda raw: _normalize(VOLUME_DIFF, raw),
    LEVEL_CHANGE: lambda raw: _normalize(LEVEL_CHANGE, raw),
    FLOW_RATE: lambda raw: _normalize(FLOW_RATE, raw),
    TIME_NEEDED: lambda raw: _normalize(TIME_NEEDED, raw),
    RAMPING_DISCHARGE: lambda raw: _normalize(RAMPING_DISCHARGE, raw),
    RAMPING_FROM_MAX: lambda raw: _normalize(RAMPING_FROM_MAX, raw),
    PRACTICAL_RAMPING: lambda raw: _normalize(PRACTICAL_RAMPING, raw),
    SPILLWAY_DISCHARGE: lambda raw: _normalize(SPILLWAY_DISCHARGE, raw),
    SPILLWAY_RAMPING: lambda raw: _normalize(SPILLWAY_RAMPING, raw),
    DETAILED_SCHEDULE: lambda raw: _normalize(DETAILED_SCHEDULE, raw),
}


def get_normalizer(tool_name: str):
    """Return normalizer function(raw_content) -> dict for tool_name, or None for fallback."""
    return _NORMALIZERS.get(tool_name)
