"""
Water Tools - Hydropower calculation toolkit
"""

from .core import *
from .tooldefs import TOOLS, TOOL_REGISTRY
from .runtime import handle_tool_calls, handle_water_tool_call

__all__ = [
    # From core
    'get_water_volume',
    'calculate_volume_difference',
    'calculate_flow_rate',
    'calculate_time_needed',
    'calculate_ramping_discharge',
    'calculate_ramping_from_max',
    'calculate_practical_ramping',
    'calculate_spillway_discharge',
    'calculate_spillway_ramping',
    'create_detailed_spillway_schedule',
    'get_weekly_limit_levels',

    # From tooldefs
    'TOOLS',
    'TOOL_REGISTRY',

    # From runtime
    'handle_tool_calls',
    'handle_water_tool_call',
]
