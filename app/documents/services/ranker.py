from documents.services.normalization import normalize_doc_type, normalize_text
from documents.services.query_parser import parse_query


SEMANTIC_WEIGHT = 0.45
KEYWORD_WEIGHT = 0.25
METADATA_WEIGHT = 0.20
SECTION_WEIGHT = 0.10


def score_keyword(parsed_query, chunk_text):
    normalized = normalize_text(chunk_text)
    if not normalized:
        return 0.0

    score = 0.0
    if parsed_query["normalized"] and parsed_query["normalized"] in normalized:
        score += 1.0

    terms = parsed_query["terms"]
    if terms:
        matched = sum(1 for term in terms if term in normalized)
        score += matched / len(terms)

    for phrase in parsed_query["phrases"]:
        if phrase in normalized:
            score += 0.8

    return min(score, 3.0) / 3.0


def _date_range_key(item):
    return (item.get("start"), item.get("end"))


def score_metadata(parsed_query, metadata):
    metadata = metadata or {}
    score = 0.0

    query_ranges = {_date_range_key(item) for item in parsed_query["date_ranges"]}
    chunk_ranges = {_date_range_key(item) for item in metadata.get("date_ranges", [])}
    if query_ranges:
        if query_ranges & chunk_ranges:
            score += 1.6
        elif chunk_ranges:
            score -= 0.5

    query_articles = set(parsed_query["article_refs"])
    chunk_articles = set(metadata.get("article_refs", []))
    if query_articles:
        if query_articles & chunk_articles:
            score += 0.8
        elif chunk_articles:
            score -= 0.2

    query_numbers = set(parsed_query["numbers"])
    chunk_numbers = set(metadata.get("numbers", []))
    if query_numbers:
        if query_numbers & chunk_numbers:
            score += 0.4
        elif chunk_numbers:
            score -= 0.1

    return max(0.0, min(score, 2.0)) / 2.0


def score_section(parsed_query, heading_path, metadata):
    metadata = metadata or {}
    section_text = " ".join(
        [
            heading_path or "",
            metadata.get("section_title", ""),
            metadata.get("parent_heading", ""),
            metadata.get("section_number", ""),
        ]
    )
    normalized = normalize_text(section_text)
    if not normalized:
        return 0.0

    score = 0.0
    for phrase in parsed_query["phrases"]:
        if phrase in normalized:
            score += 0.8

    for section_ref in parsed_query["section_refs"]:
        if normalize_text(section_ref) in normalized:
            score += 0.5

    terms = parsed_query["terms"]
    if terms:
        matched = sum(1 for term in terms if term in normalized)
        score += 0.5 * (matched / len(terms))

    return min(score, 1.5) / 1.5


def score_chunk(parsed_query, chunk, semantic_score=0.0):
    metadata = chunk.metadata or {}
    text = f"{chunk.heading_path} {chunk.content}"
    keyword = score_keyword(parsed_query, text)
    metadata_score = score_metadata(parsed_query, metadata)
    section = score_section(parsed_query, chunk.heading_path, metadata)
    semantic = max(0.0, min(float(semantic_score or 0), 1.0))

    final_score = (
        SEMANTIC_WEIGHT * semantic
        + KEYWORD_WEIGHT * keyword
        + METADATA_WEIGHT * metadata_score
        + SECTION_WEIGHT * section
    )

    # Boost score if the query date range matches the chunk date range exactly
    query_ranges = { (item.get("start"), item.get("end")) for item in parsed_query.get("date_ranges", []) }
    chunk_ranges = { (item.get("start"), item.get("end")) for item in metadata.get("date_ranges", []) }
    if query_ranges and (query_ranges & chunk_ranges):
        final_score += 0.35

    return {
        "score": min(final_score, 1.0),
        "semantic_score": semantic,
        "keyword_score": keyword,
        "metadata_score": metadata_score,
        "section_score": section,
    }


def matches_document_type(document_type, query_value):
    if not query_value:
        return True
    return normalize_doc_type(document_type) == normalize_doc_type(query_value)


def parse_and_score(query, chunk, semantic_score=0.0):
    return score_chunk(parse_query(query), chunk, semantic_score)
