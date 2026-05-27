"""
OpenAI tool handler for Sông Hinh Tools.

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
from ..services.hours_service import HoursService
from ..services.forecast_service import ForecastServiceSH
from ..core.sheets_client import get_sheets_client_manager
from ..config.columns import OP_COLS, H_COLS
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
_manager = get_sheets_client_manager()
_hours_service = HoursService(_manager, H_COLS)
_operational_service = OperationalService(_manager, OP_COLS, _hours_service)
_comparative_service = ComparativeAnalysisService(_manager, OP_COLS)
_qve_analysis_service = QveAnalysisService(_manager, OP_COLS)
_hierarchical_service = HierarchicalStatisticsService()
_rainfall_service = RainfallService()
_forecast_service = ForecastServiceSH()

# Export tools list
SONGHINH_TOOLS = [
    {"type": "function", "function": operational_data_function},
    {"type": "function", "function": comparative_analysis_function},
    {"type": "function", "function": qve_analysis_function},
    {"type": "function", "function": hierarchical_statistics_function},
    {"type": "function", "function": rainfall_statistics_function},
    {"type": "function", "function": rainfall_range_statistics_function},
    {"type": "function", "function": rainfall_daily_statistics_function},
    {"type": "function", "function": forecast_function}
]


def handle_songhinh_tool_calls(tool_call):
    """
    Handle Sông Hinh tool calls
    Args:
        tool_call: OpenAI tool call object
    Returns:
        dict: Tool response message
    """
    tool_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments or "{}")

    if tool_name == "get_songinh_operational_data":
        result = _operational_service.get_operational_data(
            arguments.get("date"),
            arguments.get("num_days", 7),
            arguments.get("start_date"),
            arguments.get("end_date")
        )

    elif tool_name == "get_songhinh_comparative_analysis":
        result = _comparative_service.get_comparative_analysis(
            arguments.get("start_date"),
            arguments.get("end_date"),
            arguments.get("parameters"),
        )

    elif tool_name == "get_songhinh_qve_analysis":
        result = _qve_analysis_service.get_qve_analysis(
            arguments.get("start_date"),
            arguments.get("end_date"),
            arguments.get("parameters"),
            arguments.get("analysis_focus", "qve"),
        )

    elif tool_name == "get_songhinh_hierarchical_statistics":
        result = _hierarchical_service.get_hierarchical_statistics(
            arguments.get("period_type"),
            arguments.get("period_value"),
            arguments.get("parameters"),
            arguments.get("compare", False),
            arguments.get("compare_years", 1),
            arguments.get("compare_with_period_value"),
            arguments.get("start_date"),
            arguments.get("end_date"),
        )

    elif tool_name == "get_songhinh_rainfall_statistics":
        result = _rainfall_service.get_rainfall_statistics(
            arguments.get("period_type"),
            arguments.get("period_value"),
            arguments.get("stations"),
            arguments.get("compare_years", 2),
        )

    elif tool_name == "get_songhinh_rainfall_range_statistics":
        result = _rainfall_service.get_rainfall_range_statistics(
            arguments.get("start_month"),
            arguments.get("start_year"),
            arguments.get("end_month"),
            arguments.get("end_year"),
            arguments.get("stations"),
        )

    elif tool_name == "get_songhinh_rainfall_daily_statistics":
        result = _rainfall_service.get_rainfall_daily_statistics(
            arguments.get("start_date"),
            arguments.get("end_date"),
            arguments.get("stations"),
        )

    elif tool_name == "get_songhinh_forecast":
        target_month = arguments.get('target_month')
        target_year = arguments.get('target_year')
        if target_month:
            result = _forecast_service.forecast_month(target_month, target_year)
        else:
            result = "### Tạm ngưng\n\nDự báo năm hiện đang tạm ngưng. Vui lòng chọn tháng cụ thể."

    else:
        result = f"Unknown Sông Hinh tool: {tool_name}"

    resp = make_tool_response(tool_name, result, get_normalizer(tool_name))
    return {
        "role": "tool",
        "content": render_markdown(resp),
        "meta": resp,
        "tool_call_id": tool_call.id,
    }


__all__ = ["SONGHINH_TOOLS", "handle_songhinh_tool_calls"]
