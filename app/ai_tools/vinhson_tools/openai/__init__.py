"""OpenAI tool definitions and handlers for Vĩnh Sơn Tools"""

from .tool_definitions import (
    operational_data_function,
    comparative_analysis_function,
    hierarchical_statistics_function,
    rainfall_statistics_function,
    rainfall_range_statistics_function,
    rainfall_daily_statistics_function
)
from .tool_handler import VINHSON_TOOLS, handle_vinhson_tool_calls

__all__ = [
    'operational_data_function',
    'comparative_analysis_function',
    'hierarchical_statistics_function',
    'rainfall_statistics_function',
    'rainfall_range_statistics_function',
    'rainfall_daily_statistics_function',
    'VINHSON_TOOLS',
    'handle_vinhson_tool_calls'
]
