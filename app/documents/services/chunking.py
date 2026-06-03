import re


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def estimate_tokens(text):
    return max(1, len((text or "").split()))


def chunk_markdown(markdown_text, max_chars=2400, overlap_chars=220):
    sections = _split_sections(markdown_text or "")
    chunks = []
    for heading_path, content in sections:
        content = content.strip()
        if not content:
            continue
        for part in _split_long_text(content, max_chars=max_chars, overlap_chars=overlap_chars):
            chunks.append(
                {
                    "heading_path": heading_path,
                    "content": part.strip(),
                    "token_count": estimate_tokens(part),
                    "metadata": {"chunking": "markdown_heading"},
                }
            )
    if not chunks and markdown_text.strip():
        chunks.append(
            {
                "heading_path": "",
                "content": markdown_text.strip()[:max_chars],
                "token_count": estimate_tokens(markdown_text),
                "metadata": {"chunking": "fallback"},
            }
        )
    return chunks


def _split_sections(text):
    headings = []
    current = {"heading_path": "", "lines": []}
    sections = []

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            if current["lines"]:
                sections.append((current["heading_path"], "\n".join(current["lines"])))
            level = len(match.group(1))
            title = match.group(2).strip()
            headings = headings[: level - 1]
            headings.append(title)
            current = {"heading_path": " > ".join(headings), "lines": [line]}
        else:
            current["lines"].append(line)

    if current["lines"]:
        sections.append((current["heading_path"], "\n".join(current["lines"])))
    return sections


def _split_long_text(text, max_chars, overlap_chars):
    if len(text) <= max_chars:
        return [text]

    parts = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        window = text[start:end]
        split_at = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
        if split_at > max_chars * 0.45:
            end = start + split_at + 1
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap_chars)
    return parts
