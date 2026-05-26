"""
Tool call handler - dispatches tool calls to appropriate functions.
Returns unified schema: {"role":"tool","content":render_markdown(resp),"meta":resp,"tool_call_id":...}.
"""

import json
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)
from tool_format import make_tool_response, render_markdown

from .normalizer import get_normalizer
from ..tooldefs.registry import TOOL_REGISTRY


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
                print(f"❌ Tool execution error: {tool_name}", flush=True)
                print(f"   Arguments: {arguments}", flush=True)
                print(f"   Error: {e}", flush=True)
                import traceback
                traceback.print_exc()

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
            print(f"❌ Tool execution error: {tool_name}", flush=True)
            print(f"   Arguments: {arguments}", flush=True)
            print(f"   Error: {e}", flush=True)
            import traceback
            traceback.print_exc()

    resp = make_tool_response(tool_name, result, get_normalizer(tool_name))
    return {
        "role": "tool",
        "content": render_markdown(resp),
        "meta": resp,
        "tool_call_id": tool_call.id,
    }
