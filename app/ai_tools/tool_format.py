"""
Unified tool response format for songhinh_tools and vinhson_tools.

Schema: tool, title, summary, table, chart, excel, notes, raw.
"""

import re
from typing import Any, Callable, Dict, List, Optional

# Canonical keys for normalized tool response
TOOL_RESPONSE_KEYS = ("tool", "title", "summary", "table", "chart", "excel", "notes", "raw")
SOURCE_KEYWORDS = (
    "supabase",
    "google sheets",
    "google sheet",
    "spreadsheet",
    "worksheet",
)


def sanitize_tool_content(value: Any) -> Any:
    """Remove backend data-source details before content reaches the agent/user."""
    if isinstance(value, dict):
        return {key: sanitize_tool_content(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_tool_content(item) for item in value]
    if not isinstance(value, str):
        return value

    cleaned_lines = []
    for line in value.splitlines():
        normalized = line.lower()
        line_head = normalized[:50]
        mentions_backend = any(keyword in normalized for keyword in SOURCE_KEYWORDS)
        source_label = (
            (("nguồn" in line_head or "nguon" in line_head or "source" in line_head) and ":" in line_head)
            or ("ngu" in line_head and ":" in line_head and mentions_backend)
            or normalized.startswith("source:")
        )
        if source_label:
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    replacements = (
        (r"Google Sheets thống kê", "nguồn dữ liệu thống kê"),
        (r"Google Sheets", "nguồn dữ liệu"),
        (r"Google Sheet", "nguồn dữ liệu"),
        (r"Supabase\s*-\s*Bảng\s*\w+", "nguồn dữ liệu"),
        (r"Supabase", "nguồn dữ liệu"),
        (r"\bsheet vận hành\b", "dữ liệu vận hành"),
        (r"\bsheet hiện có\b", "dữ liệu hiện có"),
        (r"\bworksheet thống kê\b", "bảng dữ liệu thống kê"),
        (r"\bworksheet\b", "bảng dữ liệu"),
        (r"\bspreadsheet\b", "bảng dữ liệu"),
    )
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)
    return cleaned


def make_tool_response(
    tool_name: str,
    raw_content: str,
    normalizer: Optional[Callable[[str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Build a normalized tool response dict.

    Args:
        tool_name: Name of the tool that produced the result.
        raw_content: Raw string returned by the service (markdown or error).
        normalizer: Optional function(raw_content) -> dict with keys from TOOL_RESPONSE_KEYS.
                    If None or normalizer returns incomplete dict, fallback normalizer is used.

    Returns:
        Dict with keys: tool, title, summary, table, chart, notes, raw.
    """
    base: Dict[str, Any] = {
        "tool": tool_name,
        "title": "",
        "summary": "",
        "table": "",
        "chart": "",
        "excel": "",
        "notes": "",
        "raw": sanitize_tool_content(raw_content or ""),
    }
    if normalizer and raw_content is not None:
        try:
            out = normalizer(sanitize_tool_content(raw_content))
            if isinstance(out, dict):
                for k in TOOL_RESPONSE_KEYS:
                    if k in out and out[k] is not None:
                        base[k] = sanitize_tool_content(out[k])
        except Exception:
            pass
    # Ensure fallback for any missing structural fields
    if not base["title"] and not base["table"] and base["raw"]:
        _apply_fallback(base)
    for key in TOOL_RESPONSE_KEYS:
        base[key] = sanitize_tool_content(base[key])
    return base


def _apply_fallback(resp: Dict[str, Any]) -> None:
    """Fill title/summary/table/notes from raw markdown when no specific normalizer did."""
    raw = (resp.get("raw") or "").strip()
    if not raw:
        return
    lines = raw.split("\n")
    title_lines: list = []
    summary_lines: list = []
    table_lines: list = []
    notes_lines: list = []
    in_table = False
    seen_hr = False
    in_chart = False
    chart_buf: list = []
    in_excel = False
    excel_buf: list = []
    for i, line in enumerate(lines):
        s = line.strip()
        
        # Chart code block detection
        if s.startswith("```chart") or s.startswith("```json-chart"):
            in_chart = True
            chart_buf.append(line)
            continue
        if in_chart:
            chart_buf.append(line)
            if s.startswith("```"):
                in_chart = False
                resp["chart"] = "\n".join(chart_buf)
                chart_buf = []
            continue
        if s.startswith("```excel") or s.startswith("```excel-report"):
            in_excel = True
            excel_buf.append(line)
            continue
        if in_excel:
            excel_buf.append(line)
            if s.startswith("```"):
                in_excel = False
                resp["excel"] = "\n".join(excel_buf)
                excel_buf = []
            continue

        # First ### or ## as title
        if not resp.get("title") and (s.startswith("### ") or s.startswith("## ")):
            title_lines.append(s)
            continue
        # **X:** lines near start as title/summary; near end as notes
        if s.startswith("**") and ":**" in s:
            if not table_lines and not in_table:
                if not title_lines:
                    title_lines.append(s)
                else:
                    summary_lines.append(s)
            else:
                notes_lines.append(s)
            continue
        # Markdown table
        if "|" in line and ("---" in line or (table_lines and "|" in line)):
            in_table = True
            table_lines.append(line)
            continue
        if in_table and "|" in line:
            table_lines.append(line)
            continue
        if in_table and "|" not in line:
            in_table = False
        if "---" in line:
            seen_hr = True
            continue
        if seen_hr or (table_lines and not in_table):
            if s and (s.startswith("**") or "Nguồn" in s or "Lưu ý" in s):
                notes_lines.append(s)
        elif not table_lines and s and not title_lines and i < 3:
            summary_lines.append(s)
    if title_lines and not resp.get("title"):
        resp["title"] = "\n".join(title_lines)
    if summary_lines and not resp.get("summary"):
        resp["summary"] = "\n".join(summary_lines)
    if table_lines and not resp.get("table"):
        resp["table"] = "\n".join(table_lines)
    if notes_lines and not resp.get("notes"):
        resp["notes"] = "\n".join(notes_lines)


def render_markdown(resp: Dict[str, Any]) -> str:
    """
    Render normalized response dict to a single markdown string for display.

    Order: title, summary, table, chart, notes. If raw is the only content, return raw.
    """
    if not resp:
        return ""
    raw = (sanitize_tool_content(resp.get("raw")) or "").strip()
    title = (sanitize_tool_content(resp.get("title")) or "").strip()
    summary = (sanitize_tool_content(resp.get("summary")) or "").strip()
    table = (sanitize_tool_content(resp.get("table")) or "").strip()
    chart = (sanitize_tool_content(resp.get("chart")) or "").strip()
    excel = (sanitize_tool_content(resp.get("excel")) or "").strip()
    notes = (sanitize_tool_content(resp.get("notes")) or "").strip()

    parts = []
    if title:
        parts.append(title)
    if summary:
        parts.append(summary)
    if table:
        parts.append(table)
    if chart:
        parts.append(chart)
    if excel:
        parts.append(excel)
    if notes:
        parts.append(notes)

    parts = []
    if title:
        parts.append(title)
    if summary:
        parts.append(summary)
    if table:
        parts.append(table)
    if chart:
        parts.append(chart)
    if excel:
        parts.append(excel)
    if notes:
        parts.append(notes)

    if parts:
        return "\n\n".join(parts)
    return raw


def parse_markdown_blocks(raw: str) -> Dict[str, Any]:
    """
    Parse raw markdown into blocks: title (first ###/##), summary (early **X:** or paragraph),
    tables (list of table strings), chart (code block), notes (footer **Nguồn:** etc.).
    Used by module normalizers to build schema.
    """
    out: Dict[str, Any] = {"title": "", "summary": "", "tables": [], "chart": "", "excel": "", "notes": ""}
    if not (raw or "").strip():
        return out
    lines = sanitize_tool_content(raw).split("\n")
    title_done = False
    summary_lines: List[str] = []
    table_buf: List[str] = []
    notes_lines: List[str] = []
    in_table = False
    in_chart = False
    chart_buf: List[str] = []
    in_excel = False
    excel_buf: List[str] = []

    for i, line in enumerate(lines):
        s = line.strip()

        # Chart code block detection
        if s.startswith("```chart") or s.startswith("```json-chart"):
            in_chart = True
            chart_buf.append(line)
            continue
        if in_chart:
            chart_buf.append(line)
            if s.startswith("```"):
                in_chart = False
                out["chart"] = "\n".join(chart_buf)
                chart_buf = []
            continue
        if s.startswith("```excel") or s.startswith("```excel-report"):
            in_excel = True
            excel_buf.append(line)
            continue
        if in_excel:
            excel_buf.append(line)
            if s.startswith("```"):
                in_excel = False
                out["excel"] = "\n".join(excel_buf)
                excel_buf = []
            continue

        # Title: first ### or ##
        if not title_done and (s.startswith("### ") or s.startswith("## ")):
            out["title"] = s
            title_done = True
            continue
        # Table: lines with |
        if "|" in line:
            if in_table:
                table_buf.append(line)
            else:
                if table_buf:
                    out["tables"].append("\n".join(table_buf))
                    table_buf = []
                in_table = True
                table_buf.append(line)
            continue
        if in_table:
            in_table = False
            if table_buf:
                out["tables"].append("\n".join(table_buf))
            table_buf = []
        # **X:** before any table = summary; after tables = notes
        if s.startswith("**") and ":**" in s:
            if not out["tables"]:
                summary_lines.append(s)
            else:
                notes_lines.append(s)
            continue
        if "---" in line:
            continue
        if out["tables"] and s and (s.startswith("**") or "Nguồn" in s or "Lưu ý" in s):
            notes_lines.append(s)

    if table_buf:
        out["tables"].append("\n".join(table_buf))
    if summary_lines:
        out["summary"] = "\n".join(summary_lines)
    if notes_lines:
        out["notes"] = "\n".join(notes_lines)
    return out
