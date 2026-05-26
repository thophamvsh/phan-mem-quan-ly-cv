"""
Unified tool response format for songhinh_tools and vinhson_tools.

Schema: tool, title, summary, table, chart, notes, raw.
"""

from typing import Any, Callable, Dict, List, Optional

# Canonical keys for normalized tool response
TOOL_RESPONSE_KEYS = ("tool", "title", "summary", "table", "chart", "notes", "raw")


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
        "notes": "",
        "raw": raw_content or "",
    }
    if normalizer and raw_content is not None:
        try:
            out = normalizer(raw_content)
            if isinstance(out, dict):
                for k in TOOL_RESPONSE_KEYS:
                    if k in out and out[k] is not None:
                        base[k] = out[k]
        except Exception:
            pass
    # Ensure fallback for any missing structural fields
    if not base["title"] and not base["table"] and base["raw"]:
        _apply_fallback(base)
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
    for i, line in enumerate(lines):
        s = line.strip()
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
    raw = (resp.get("raw") or "").strip()
    title = (resp.get("title") or "").strip()
    summary = (resp.get("summary") or "").strip()
    table = (resp.get("table") or "").strip()
    chart = (resp.get("chart") or "").strip()
    notes = (resp.get("notes") or "").strip()

    parts = []
    if title:
        parts.append(title)
    if summary:
        parts.append(summary)
    if table:
        parts.append(table)
    if chart:
        parts.append(chart)
    if notes:
        parts.append(notes)

    if parts:
        return "\n\n".join(parts)
    return raw


def parse_markdown_blocks(raw: str) -> Dict[str, Any]:
    """
    Parse raw markdown into blocks: title (first ###/##), summary (early **X:** or paragraph),
    tables (list of table strings), notes (footer **Nguồn:** etc.).
    Used by module normalizers to build schema.
    """
    out: Dict[str, Any] = {"title": "", "summary": "", "tables": [], "notes": ""}
    if not (raw or "").strip():
        return out
    lines = raw.split("\n")
    title_done = False
    summary_lines: List[str] = []
    table_buf: List[str] = []
    notes_lines: List[str] = []
    in_table = False
    for i, line in enumerate(lines):
        s = line.strip()
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
