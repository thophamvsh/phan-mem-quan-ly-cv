"""
Core water calculation functions
"""

from .interpolation import interpolate_water_level_from_volume
from .volume import get_water_volume, get_useful_volume, get_flood_control_volume, calculate_volume_difference
from .flow import calculate_flow_rate, calculate_time_needed, calculate_level_change
from .ramping import (
    calculate_ramping_discharge,
    calculate_ramping_from_max,
    calculate_practical_ramping
)
from .spillway import (
    calculate_spillway_discharge,
    calculate_spillway_ramping,
    create_detailed_spillway_schedule
)
from .weekly_limit import get_weekly_limit_levels

__all__ = [
    # Interpolation
    'interpolate_water_level_from_volume',

    # Volume
    'get_water_volume',
    'get_useful_volume',
    'get_flood_control_volume',
    'calculate_volume_difference',

    # Flow
    'calculate_flow_rate',
    'calculate_time_needed',
    'calculate_level_change',

    # Ramping
    'calculate_ramping_discharge',
    'calculate_ramping_from_max',
    'calculate_practical_ramping',

    # Spillway
    'calculate_spillway_discharge',
    'calculate_spillway_ramping',
    'create_detailed_spillway_schedule',

    # Weekly limits
    'get_weekly_limit_levels',
]
