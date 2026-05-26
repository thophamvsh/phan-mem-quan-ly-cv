"""
Tool registry - maps tool names to callable functions
"""

from ..core import (
    get_water_volume,
    get_useful_volume,
    get_flood_control_volume,
    calculate_volume_difference,
    calculate_flow_rate,
    calculate_time_needed,
    calculate_level_change,
    calculate_ramping_discharge,
    calculate_ramping_from_max,
    calculate_practical_ramping,
    calculate_spillway_discharge,
    calculate_spillway_ramping,
    create_detailed_spillway_schedule,
)
from .schemas import TOOLS


# Tool name to function mapping
TOOL_REGISTRY = {
    "get_water_volume": get_water_volume,
    "get_useful_volume": get_useful_volume,
    "get_flood_control_volume": get_flood_control_volume,
    "calculate_volume_difference": calculate_volume_difference,
    "calculate_flow_rate": calculate_flow_rate,
    "calculate_level_change": calculate_level_change,
    "calculate_spillway_ramping": calculate_spillway_ramping,
    "create_detailed_spillway_schedule": create_detailed_spillway_schedule,
    "calculate_spillway_discharge": calculate_spillway_discharge,
    "calculate_ramping_discharge": calculate_ramping_discharge,
    "calculate_ramping_from_max": calculate_ramping_from_max,
    "calculate_practical_ramping": calculate_practical_ramping,
    "calculate_time_needed": calculate_time_needed,
}


def get_tool_function(tool_name):
    """Get function by tool name"""
    return TOOL_REGISTRY.get(tool_name)
