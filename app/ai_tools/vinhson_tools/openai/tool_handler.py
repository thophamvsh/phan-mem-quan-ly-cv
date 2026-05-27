"""
OpenAI tool handler for Vĩnh Sơn Tools.

Sử dụng các service classes để xử lý tool calls.
Returns unified schema: {"role":"tool","content":render_markdown(resp),"meta":resp,"tool_call_id":...}.
"""

import json

from ai_tools.tool_format import make_tool_response, render_markdown

from .normalizer import get_normalizer
from ..services.operational_service import OperationalService
from ..services.comparative_service import ComparativeAnalysisService
from ..services.qve_analysis_service import QveAnalysisService
from ..services.hierarchical_service import HierarchicalStatisticsService
from ..services.rainfall_service import RainfallService
from ..services.forecast_service import ForecastService
from .tool_definitions import (
    operational_data_function,
    comparative_analysis_function,
    qve_analysis_function,
    hierarchical_statistics_function,
    rainfall_statistics_function,
    rainfall_range_statistics_function,
    rainfall_daily_statistics_function,
    forecast_function
)

# Initialize service instances
_operational_service = OperationalService()
_comparative_service = ComparativeAnalysisService()
_qve_analysis_service = QveAnalysisService()
_hierarchical_service = HierarchicalStatisticsService()
_rainfall_service = RainfallService()
_forecast_service = ForecastService()

# Export tools list
VINHSON_TOOLS = [
    {"type": "function", "function": operational_data_function},
    {"type": "function", "function": comparative_analysis_function},
    {"type": "function", "function": qve_analysis_function},
    {"type": "function", "function": hierarchical_statistics_function},
    {"type": "function", "function": rainfall_statistics_function},
    {"type": "function", "function": rainfall_range_statistics_function},
    {"type": "function", "function": rainfall_daily_statistics_function},
    {"type": "function", "function": forecast_function}
]


def handle_vinhson_tool_calls(tool_call):
    """
    Handle Vĩnh Sơn tool calls
    Args:
        tool_call: OpenAI tool call object
    Returns:
        dict: Tool response message
    """
    tool_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments or "{}")

    if tool_name == "get_vinhson_operational_data":
        date = arguments.get('date')
        num_days = arguments.get('num_days', 7)
        reservoir = arguments.get('reservoir', 'Vinh Son -A')
        start_date = arguments.get('start_date')
        end_date = arguments.get('end_date')
        result = _operational_service.get_operational_data(date, num_days, reservoir, start_date, end_date)

    elif tool_name == "get_vinhson_comparative_analysis":
        start_date = arguments.get('start_date')
        end_date = arguments.get('end_date')
        reservoir = arguments.get('reservoir', 'Vinh Son -A')
        parameters = arguments.get('parameters', None)
        result = _comparative_service.get_comparative_analysis(start_date, end_date, reservoir, parameters)

    elif tool_name == "get_vinhson_qve_analysis":
        start_date = arguments.get('start_date')
        end_date = arguments.get('end_date')
        reservoir = arguments.get('reservoir', 'All')
        parameters = arguments.get('parameters', None)
        analysis_focus = arguments.get('analysis_focus', 'qve')
        result = _qve_analysis_service.get_qve_analysis(start_date, end_date, reservoir, parameters, analysis_focus)

    elif tool_name == "get_vinhson_hierarchical_statistics":
        period_type = arguments.get('period_type')
        period_value = arguments.get('period_value', None)
        reservoir = arguments.get('reservoir', 'All')
        parameters = arguments.get('parameters', None)
        compare = arguments.get('compare', False)
        compare_years = arguments.get('compare_years', 1)
        compare_with_period_value = arguments.get('compare_with_period_value', None)
        start_date = arguments.get('start_date')
        end_date = arguments.get('end_date')
        result = _hierarchical_service.get_hierarchical_statistics(period_type, period_value, reservoir, parameters, compare, compare_years, compare_with_period_value, start_date, end_date)

    elif tool_name == "get_vinhson_rainfall_statistics":
        period_type = arguments.get('period_type')
        period_value = arguments.get('period_value')
        reservoir = arguments.get('reservoir', 'Vinh Son -A')
        stations = arguments.get('stations', None)
        compare_years = arguments.get('compare_years', 2)
        result = _rainfall_service.get_rainfall_statistics(period_type, period_value, reservoir, stations, compare_years)

    elif tool_name == "get_vinhson_rainfall_range_statistics":
        start_month = arguments.get('start_month')
        start_year = arguments.get('start_year')
        end_month = arguments.get('end_month')
        end_year = arguments.get('end_year')
        reservoir = arguments.get('reservoir', 'Vinh Son -A')
        stations = arguments.get('stations', None)
        result = _rainfall_service.get_rainfall_range_statistics(start_month, start_year, end_month, end_year, reservoir, stations)

    elif tool_name == "get_vinhson_rainfall_daily_statistics":
        start_date = arguments.get('start_date')
        end_date = arguments.get('end_date')
        reservoir = arguments.get('reservoir', 'Vinh Son -A')
        stations = arguments.get('stations', None)
        result = _rainfall_service.get_rainfall_daily_statistics(start_date, end_date, reservoir, stations)

    elif tool_name == "get_vinhson_forecast":
        target_month = arguments.get('target_month')
        target_year = arguments.get('target_year')
        reservoir = arguments.get('reservoir', 'All')
        if target_month:
            result = _forecast_service.forecast_month(target_month, target_year, reservoir)
        else:
            result = _forecast_service.forecast_year(target_year, reservoir)

    else:
        result = f"Unknown Vinh Son tool: {tool_name}"

    resp = make_tool_response(tool_name, result, get_normalizer(tool_name))
    return {
        "role": "tool",
        "content": render_markdown(resp),
        "meta": resp,
        "tool_call_id": tool_call.id,
    }


__all__ = ["VINHSON_TOOLS", "handle_vinhson_tool_calls"]
