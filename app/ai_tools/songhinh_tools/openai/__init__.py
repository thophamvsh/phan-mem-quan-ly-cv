"""OpenAI tool definitions and handlers for Sông Hinh Tools"""

from .tool_definitions import (
    operational_data_function,
    comparative_analysis_function,
    hierarchical_statistics_function,
    rainfall_statistics_function,
    rainfall_range_statistics_function,
    rainfall_daily_statistics_function
)
from .tool_handler import SONGHINH_TOOLS, handle_songhinh_tool_calls

__all__ = [
    'operational_data_function',
    'comparative_analysis_function',
    'hierarchical_statistics_function',
    'rainfall_statistics_function',
    'rainfall_range_statistics_function',
    'rainfall_daily_statistics_function',
    'SONGHINH_TOOLS',
    'handle_songhinh_tool_calls'
]
