import re

from documents.services.normalization import normalize_text
from documents.services.query_parser import (
    extract_article_refs,
    extract_date_ranges,
    extract_numbers,
)


MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
HTML_HEADING_RE = re.compile(r"^<h([1-6])[^>]*>(.+?)</h\1>\s*$", re.IGNORECASE)
BOLD_SECTION_RE = re.compile(
    r"^\*\*(?P<title>(?:[IVX]+|\d+(?:\.\d+)*)\.\s+.+?)\*\*(?:\s*[\(*].*)?:?\s*$"
)
PLAIN_SECTION_RE = re.compile(r"^(?P<title>(?:[IVX]+|\d+(?:\.\d+)*)\.\s+.+?)\s*$")
PAGE_RE = re.compile(r"(?:^|\n)\s*(?:##\s*)?Trang\s+(\d+)\b", re.IGNORECASE)
STANDALONE_PAGE_RE = re.compile(r"^\s*(\d{1,4})\s*$")


def estimate_tokens(text):
    return max(1, len((text or "").split()))


def _strip_boilerplate_lines(text):
    if not text:
        return ""
    lines = text.splitlines()
    from collections import Counter
    candidate_lines = [
        line.strip()
        for line in lines
        if line.strip() and not (line.strip().startswith("|") or line.strip().endswith("|"))
    ]
    counts = Counter(candidate_lines)
    to_strip = {
        line
        for line, count in counts.items()
        if count >= 4 and len(line) < 120
    }
    
    cleaned_lines = []
    for line in lines:
        if line.strip() in to_strip:
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def chunk_markdown(markdown_text, max_chars=2600, overlap_chars=180):
    cleaned_text = _strip_boilerplate_lines(markdown_text or "")
    blocks = _split_logical_sections(cleaned_text)
    chunks = []

    for section_index, block in enumerate(blocks):
        content = block["content"].strip()
        if not content:
            continue

        parts = _split_long_text(content, max_chars=max_chars, overlap_chars=overlap_chars)
        for part_index, part in enumerate(parts):
            metadata = _build_metadata(block, section_index, part_index, part)
            chunks.append(
                {
                    "heading_path": block.get("heading_path", ""),
                    "content": part.strip(),
                    "token_count": estimate_tokens(part),
                    "page_from": metadata.get("page_from"),
                    "page_to": metadata.get("page_to"),
                    "metadata": metadata,
                }
            )

    if not chunks and markdown_text.strip():
        fallback = markdown_text.strip()[:max_chars]
        metadata = _extract_metadata(fallback)
        metadata.update({"chunking": "fallback", "section_id": "fallback"})
        chunks.append(
            {
                "heading_path": "",
                "content": fallback,
                "token_count": estimate_tokens(markdown_text),
                "page_from": metadata.get("page_from"),
                "page_to": metadata.get("page_to"),
                "metadata": metadata,
            }
        )

    return chunks


def _split_logical_sections(text):
    headings = []
    sections = []
    current = _new_section("", "", "", [])
    current_page = None

    for line in text.splitlines():
        page_num = _extract_page_marker(line)
        if page_num:
            current_page = page_num

        heading = _parse_heading(line)
        if heading:
            if current["lines"]:
                sections.append(_finalize_section(current))
            level, title = heading
            headings = headings[: level - 1]
            headings.append(title)
            current = _new_section(
                title=title,
                heading_path=" > ".join(headings),
                parent_heading=" > ".join(headings[:-1]),
                headings=headings,
            )
            current["page_from"] = current_page
            current["lines"].append(line)
            continue

        section_title = _parse_inline_section_title(line)
        if section_title and current["lines"] and _should_start_new_section(current, section_title):
            sections.append(_finalize_section(current))
            parent_heading = current.get("parent_heading") or current.get("heading_path", "")
            heading_path = " > ".join(part for part in [parent_heading, section_title] if part)
            current = _new_section(
                title=section_title,
                heading_path=heading_path,
                parent_heading=parent_heading,
                headings=headings,
            )
            current["page_from"] = current_page

        current["lines"].append(line)
        if current_page:
            current["page_to"] = current_page
            if not current.get("page_from"):
                current["page_from"] = current_page

    if current["lines"]:
        sections.append(_finalize_section(current))

    return sections


def _new_section(title, heading_path, parent_heading, headings):
    return {
        "title": title,
        "heading_path": heading_path,
        "parent_heading": parent_heading,
        "headings": list(headings),
        "lines": [],
        "page_from": None,
        "page_to": None,
    }


def _finalize_section(section):
    content = "\n".join(section["lines"]).strip()
    section["content"] = content
    if not section.get("title"):
        title = _first_meaningful_line(content)
        section["title"] = title
        section["heading_path"] = section.get("heading_path") or title
    return section


def _parse_heading(line):
    markdown = MARKDOWN_HEADING_RE.match(line.strip())
    if markdown:
        return len(markdown.group(1)), _clean_title(markdown.group(2))

    html = HTML_HEADING_RE.match(line.strip())
    if html:
        return int(html.group(1)), _clean_title(html.group(2))

    return None


def _parse_inline_section_title(line):
    stripped = line.strip()
    for pattern in (BOLD_SECTION_RE, PLAIN_SECTION_RE):
        match = pattern.match(stripped)
        if match:
            title = _clean_title(match.group("title"))
            if _looks_like_section_title(title):
                return title
    return ""


def _looks_like_section_title(title):
    normalized = normalize_text(title)
    if len(normalized) < 6:
        return False
    if "|" in title or "<td" in normalized or "<tr" in normalized:
        return False
    return True


def _should_start_new_section(current, section_title):
    normalized_current = normalize_text(current.get("title", ""))
    normalized_next = normalize_text(section_title)
    if not normalized_next or normalized_next == normalized_current:
        return False
    return True


def _extract_page_marker(line):
    match = PAGE_RE.search(line)
    if match:
        return int(match.group(1))

    standalone = STANDALONE_PAGE_RE.match(line)
    if standalone:
        number = int(standalone.group(1))
        if 1 <= number <= 2000:
            return number
    return None


def _clean_title(title):
    title = re.sub(r"<[^>]+>", "", title or "")
    title = title.replace("*", "").replace("_", "").strip()
    return re.sub(r"\s+", " ", title)


def _first_meaningful_line(text):
    for line in (text or "").splitlines():
        cleaned = _clean_title(line)
        if cleaned:
            return cleaned[:180]
    return ""


def _split_long_text(text, max_chars, overlap_chars):
    if len(text) <= max_chars:
        return [text]

    parts = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        window = text[start:end]
        split_at = max(
            window.rfind("\n## "),
            window.rfind("\n**"),
            window.rfind("\n\n"),
            window.rfind("</table>"),
            window.rfind(". "),
            window.rfind("\n"),
        )
        if split_at > max_chars * 0.45:
            end = start + split_at + 1
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return parts


def _build_metadata(block, section_index, part_index, content):
    metadata = _extract_metadata(content)
    section_title = block.get("title", "")
    parent_heading = block.get("parent_heading", "")
    section_number = _extract_section_number(section_title)
    page_from = metadata.get("page_from") or block.get("page_from")
    page_to = metadata.get("page_to") or block.get("page_to") or page_from

    metadata.update(
        {
            "chunking": "section_metadata",
            "section_id": f"{section_index}",
            "section_part": part_index,
            "section_title": section_title,
            "section_number": section_number,
            "parent_heading": parent_heading,
            "heading_path": block.get("heading_path", ""),
            "page_from": page_from,
            "page_to": page_to,
        }
    )
    return metadata


def _extract_metadata(text):
    page_numbers = [int(match.group(1)) for match in PAGE_RE.finditer(text or "")]
    if not page_numbers:
        page_numbers = [
            int(match.group(1))
            for match in STANDALONE_PAGE_RE.finditer(text or "")
            if 1 <= int(match.group(1)) <= 2000
        ]

    return {
        "date_ranges": extract_date_ranges(text),
        "article_refs": extract_article_refs(text),
        "numbers": extract_numbers(text),
        "page_from": min(page_numbers) if page_numbers else None,
        "page_to": max(page_numbers) if page_numbers else None,
    }


def _extract_section_number(title):
    match = re.match(r"\s*([IVX]+|\d+(?:\.\d+)*)\.", title or "", re.IGNORECASE)
    return match.group(1) if match else ""
