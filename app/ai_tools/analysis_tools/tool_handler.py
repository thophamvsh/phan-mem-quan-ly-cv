import json
import logging

from ai_tools.tool_format import make_tool_response, render_markdown

from .services import analyze_hydro_data, compare_hydro_periods, get_unit_state_profile
from .tool_definitions import ANALYSIS_TOOLS


logger = logging.getLogger(__name__)


TOOL_REGISTRY = {
    "analyze_hydro_data": analyze_hydro_data,
    "compare_hydro_periods": compare_hydro_periods,
    "get_unit_state_profile": get_unit_state_profile,
}



def handle_analysis_tool_call(tool_call):
    tool_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments or "{}")
    func = TOOL_REGISTRY.get(tool_name)
    if not func:
        result = f"Unknown analysis tool: {tool_name}"
    else:
        try:
            result = func(**arguments)
        except Exception as exc:
            logger.exception("Analysis tool execution failed: %s arguments=%s", tool_name, arguments)
            result = f"Lỗi khi chạy analysis tool {tool_name}: {exc}"

    resp = make_tool_response(tool_name, result, None)
    return {
        "role": "tool",
        "content": render_markdown(resp),
        "meta": resp,
        "tool_call_id": tool_call.id,
    }
