"""
Ramping discharge calculation functions

These functions have been consolidated into spillway.py.
Import from spillway for unified functionality.
"""

# Import from spillway for unified functionality
from .spillway import (
    calculate_spillway_discharge,
    calculate_spillway_ramping,
    create_detailed_spillway_schedule,
)

# Aliases for backward compatibility
calculate_ramping_discharge = calculate_spillway_ramping
calculate_ramping_from_max = calculate_spillway_ramping
calculate_practical_ramping = calculate_spillway_ramping


__all__ = [
    'calculate_spillway_discharge',
    'calculate_spillway_ramping',
    'create_detailed_spillway_schedule',
    'calculate_ramping_discharge',
    'calculate_ramping_from_max',
    'calculate_practical_ramping',
]
