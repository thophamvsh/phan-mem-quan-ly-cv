"""
Tool call handler - dispatches tool calls to appropriate functions.
Returns unified schema: {"role":"tool","content":render_markdown(resp),"meta":resp,"tool_call_id":...}.
"""

import json
import logging

from ai_tools.tool_format import make_tool_response, render_markdown

from .normalizer import get_normalizer
from ..tooldefs.registry import TOOL_REGISTRY


logger = logging.getLogger(__name__)


def handle_tool_calls(message):
    """
    Handle tool calls from OpenAI using registry pattern

    Args:
        message: OpenAI message object with tool_calls

    Returns:
        list: List of tool response messages
    """
    responses = []

    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        # Get function from registry
        func = TOOL_REGISTRY.get(tool_name)

        if func is None:
            result = f"Unknown tool: {tool_name}"
        else:
            try:
                result = func(**arguments)
            except Exception as e:
                result = f"Error executing {tool_name}: {str(e)}"
                logger.exception("Tool execution error: %s arguments=%s", tool_name, arguments)

        resp = make_tool_response(tool_name, result, get_normalizer(tool_name))
        responses.append({
            "role": "tool",
            "content": render_markdown(resp),
            "meta": resp,
            "tool_call_id": tool_call.id,
        })

    return responses


def handle_water_tool_call(tool_call):
    """
    Handle a single water tool call (same interface as songhinh/vinhson handlers).

    Args:
        tool_call: OpenAI tool call object

    Returns:
        dict: Tool response message
    """
    tool_name = tool_call.function.name
    arguments = json.loads(tool_call.function.arguments)

    func = TOOL_REGISTRY.get(tool_name)

    if func is None:
        result = f"Unknown water tool: {tool_name}"
    else:
        try:
            result = func(**arguments)
        except Exception as e:
            result = f"Error executing {tool_name}: {str(e)}"
            logger.exception("Tool execution error: %s arguments=%s", tool_name, arguments)

    resp = make_tool_response(tool_name, result, get_normalizer(tool_name))
    return {
        "role": "tool",
        "content": render_markdown(resp),
        "meta": resp,
        "tool_call_id": tool_call.id,
    }
