"""
Normalizers for Vĩnh Sơn tool responses → unified schema: tool, title, summary, table, chart, notes, raw.
"""

from typing import Any, Dict, Optional

from ai_tools.tool_format import parse_markdown_blocks

OPERATIONAL = "get_vinhson_operational_data"
COMPARATIVE = "get_vinhson_comparative_analysis"
QVE_ANALYSIS = "get_vinhson_qve_analysis"
HIERARCHICAL = "get_vinhson_hierarchical_statistics"
RAINFALL_STAT = "get_vinhson_rainfall_statistics"
RAINFALL_RANGE = "get_vinhson_rainfall_range_statistics"
RAINFALL_DAILY = "get_vinhson_rainfall_daily_statistics"
FORECAST = "get_vinhson_forecast"


def _to_schema(tool_name: str, raw: str, blocks: Dict[str, Any]) -> Dict[str, Any]:
    tables = blocks.get("tables") or []
    return {
        "tool": tool_name,
        "title": (blocks.get("title") or "").strip(),
        "summary": (blocks.get("summary") or "").strip(),
        "table": "\n\n".join(tables).strip() if tables else "",
        "chart": (blocks.get("chart") or "").strip(),
        "excel": (blocks.get("excel") or "").strip(),
        "notes": (blocks.get("notes") or "").strip(),
        "raw": raw,
    }


def normalize_operational_data(raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(OPERATIONAL, raw, blocks)


def normalize_comparative_analysis(raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(COMPARATIVE, raw, blocks)


def normalize_qve_analysis(raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(QVE_ANALYSIS, raw, blocks)


def normalize_hierarchical_statistics(raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(HIERARCHICAL, raw, blocks)


def normalize_rainfall_statistics(raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(RAINFALL_STAT, raw, blocks)


def normalize_rainfall_daily_statistics(raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(RAINFALL_DAILY, raw, blocks)


def normalize_rainfall_range_statistics(raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(RAINFALL_RANGE, raw, blocks)


def normalize_forecast(raw: str) -> Dict[str, Any]:
    blocks = parse_markdown_blocks(raw)
    return _to_schema(FORECAST, raw, blocks)


_NORMALIZERS = {
    OPERATIONAL: normalize_operational_data,
    COMPARATIVE: normalize_comparative_analysis,
    QVE_ANALYSIS: normalize_qve_analysis,
    HIERARCHICAL: normalize_hierarchical_statistics,
    RAINFALL_STAT: normalize_rainfall_statistics,
    RAINFALL_DAILY: normalize_rainfall_daily_statistics,
    RAINFALL_RANGE: normalize_rainfall_range_statistics,
    FORECAST: normalize_forecast,
}


def get_normalizer(tool_name: str):
    """Return normalizer function(raw_content) -> dict for tool_name, or None for fallback."""
    return _NORMALIZERS.get(tool_name)
