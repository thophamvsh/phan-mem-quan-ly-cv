"""
Normalizers for Sông Hinh tool responses → unified schema: tool, title, summary, table, chart, notes, raw.
"""

from typing import Any, Dict, Optional

# Import from parent week2 so both packages can use it when run from week2
import sys
import os
_week2 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _week2 not in sys.path:
    sys.path.insert(0, _week2)
from tool_format import parse_markdown_blocks

# Tool names (must match tool_definitions)
OPERATIONAL = "get_songinh_operational_data"
COMPARATIVE = "get_songhinh_comparative_analysis"
QVE_ANALYSIS = "get_songhinh_qve_analysis"
HIERARCHICAL = "get_songhinh_hierarchical_statistics"
RAINFALL_STAT = "get_songhinh_rainfall_statistics"
RAINFALL_RANGE = "get_songhinh_rainfall_range_statistics"
RAINFALL_DAILY = "get_songhinh_rainfall_daily_statistics"


def _to_schema(tool_name: str, raw: str, blocks: Dict[str, Any]) -> Dict[str, Any]:
    tables = blocks.get("tables") or []
    return {
        "tool": tool_name,
        "title": (blocks.get("title") or "").strip(),
        "summary": (blocks.get("summary") or "").strip(),
        "table": "\n\n".join(tables).strip() if tables else "",
        "chart": "",
        "notes": (blocks.get("notes") or "").strip(),
        "raw": raw,
    }


def normalize_operational_data(raw: str) -> Dict[str, Any]:
    """Normalize get_songinh_operational_data output."""
    blocks = parse_markdown_blocks(raw)
    return _to_schema(OPERATIONAL, raw, blocks)


def normalize_comparative_analysis(raw: str) -> Dict[str, Any]:
    """Normalize get_songhinh_comparative_analysis output."""
    blocks = parse_markdown_blocks(raw)
    return _to_schema(COMPARATIVE, raw, blocks)


def normalize_qve_analysis(raw: str) -> Dict[str, Any]:
    """Normalize get_songhinh_qve_analysis output."""
    blocks = parse_markdown_blocks(raw)
    return _to_schema(QVE_ANALYSIS, raw, blocks)


def normalize_hierarchical_statistics(raw: str) -> Dict[str, Any]:
    """Normalize get_songhinh_hierarchical_statistics output."""
    blocks = parse_markdown_blocks(raw)
    return _to_schema(HIERARCHICAL, raw, blocks)


def normalize_rainfall_statistics(raw: str) -> Dict[str, Any]:
    """Normalize get_songhinh_rainfall_statistics output."""
    blocks = parse_markdown_blocks(raw)
    return _to_schema(RAINFALL_STAT, raw, blocks)


def normalize_rainfall_daily_statistics(raw: str) -> Dict[str, Any]:
    """Normalize get_songhinh_rainfall_daily_statistics output."""
    blocks = parse_markdown_blocks(raw)
    return _to_schema(RAINFALL_DAILY, raw, blocks)


def normalize_rainfall_range_statistics(raw: str) -> Dict[str, Any]:
    """Normalize get_songhinh_rainfall_range_statistics output (fallback-style)."""
    blocks = parse_markdown_blocks(raw)
    return _to_schema(RAINFALL_RANGE, raw, blocks)


_NORMALIZERS = {
    OPERATIONAL: normalize_operational_data,
    COMPARATIVE: normalize_comparative_analysis,
    QVE_ANALYSIS: normalize_qve_analysis,
    HIERARCHICAL: normalize_hierarchical_statistics,
    RAINFALL_STAT: normalize_rainfall_statistics,
    RAINFALL_DAILY: normalize_rainfall_daily_statistics,
    RAINFALL_RANGE: normalize_rainfall_range_statistics,
}


def get_normalizer(tool_name: str):
    """
    Return normalizer function(raw_content) -> dict for tool_name, or None for fallback.
    Handler: make_tool_response(tool_name, raw_content, get_normalizer(tool_name)).
    """
    return _NORMALIZERS.get(tool_name)
