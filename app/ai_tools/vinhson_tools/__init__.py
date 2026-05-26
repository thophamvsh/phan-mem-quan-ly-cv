"""
Vĩnh Sơn tools package (wrapper).

- Mục tiêu hiện tại: đổi đường dẫn import trong `app.py` sang `vinhson_tools`
  nhưng vẫn giữ nguyên `vinhsontools.py` như file dự phòng/legacy.
"""

from .openai.tool_handler import VINHSON_TOOLS, handle_vinhson_tool_calls

__all__ = ["VINHSON_TOOLS", "handle_vinhson_tool_calls"]
