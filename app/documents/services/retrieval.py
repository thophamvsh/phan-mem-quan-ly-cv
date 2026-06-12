import importlib
import logging
import re

import numpy as np
from django.conf import settings

try:
    permissions = importlib.import_module("ai_tools.permissions")
except ModuleNotFoundError:
    permissions = importlib.import_module("app.ai_tools.permissions")

AI_TOOL_SCOPE_SONGHINH = permissions.AI_TOOL_SCOPE_SONGHINH
AI_TOOL_SCOPE_VINHSON = permissions.AI_TOOL_SCOPE_VINHSON
get_ai_tool_scopes_for_user = permissions.get_ai_tool_scopes_for_user

from pgvector.django import CosineDistance
from ..models import Document, DocumentChunk
from .embeddings import get_embedding
from .normalization import normalize_doc_type, normalize_text
from .query_parser import parse_query
from .ranker import matches_document_type, score_chunk


logger = logging.getLogger(__name__)

SEMANTIC_CANDIDATE_LIMIT = 10000
KEYWORD_CANDIDATE_LIMIT = 500
MIN_FINAL_SCORE = 0.30
MAX_CONTEXT_CHARS = 6500


def get_allowed_factories_for_user(user):
    scopes = get_ai_tool_scopes_for_user(user)
    factories = {Document.FACTORY_GENERAL}
    if AI_TOOL_SCOPE_SONGHINH in scopes:
        factories.update({Document.FACTORY_SONGHINH, Document.FACTORY_THUONGKONTUM})
    if AI_TOOL_SCOPE_VINHSON in scopes:
        factories.add(Document.FACTORY_VINHSON)
    return factories


def filter_documents_for_user(user, queryset=None):
    queryset = queryset or Document.objects.all()
    return queryset.filter(factory__in=get_allowed_factories_for_user(user))


def search_documents(user, query, factory="", document_type="", limit=5):
    parsed_query = parse_query(query)
    query = (query or "").strip()
    if not query:
        return []

    allowed_factories = _resolve_allowed_factories(user, factory or parsed_query.get("factory", ""))
    if not allowed_factories:
        return []

    base_queryset = (
        DocumentChunk.objects.select_related("document")
        .defer("document__markdown_text")
        .filter(document__status=Document.STATUS_READY, document__factory__in=allowed_factories)
        .filter(embedding__isnull=False)
    )

    if document_type:
        matching_doc_ids = [
            document.id
            for document in Document.objects.filter(
                status=Document.STATUS_READY,
                factory__in=allowed_factories,
            ).only("id", "document_type")
            if matches_document_type(document.document_type, document_type)
        ]
        base_queryset = base_queryset.filter(document_id__in=matching_doc_ids)

    candidates = _collect_candidates(base_queryset, parsed_query, query)
    if not candidates:
        return []

    ranked = _rank_candidates(candidates, parsed_query, query)
    ranked = [item for item in ranked if item["scores"]["score"] >= MIN_FINAL_SCORE]
    if not ranked:
        return []

    result_limit = max(1, min(int(limit or 3), 12))
    return [_format_result(item, parsed_query) for item in ranked[:result_limit]]


def _resolve_allowed_factories(user, requested_factory):
    allowed_factories = get_allowed_factories_for_user(user)
    if not requested_factory:
        return allowed_factories
    if requested_factory not in allowed_factories:
        return set()
    return {requested_factory, Document.FACTORY_GENERAL}


def _collect_candidates(base_queryset, parsed_query, query):
    candidates = {}
    query_embedding = get_embedding(query)

    for chunk in _semantic_candidates(base_queryset, query_embedding):
        distance = getattr(chunk, "distance", None)
        semantic_score = max(0.0, 1.0 - float(distance)) if distance is not None else 0.0
        candidates[chunk.id] = {"chunk": chunk, "semantic_score": semantic_score}

    for chunk in _keyword_candidates(base_queryset, parsed_query):
        candidates.setdefault(chunk.id, {"chunk": chunk, "semantic_score": 0.0})

    if query_embedding:
        missing_chunks = [
            item["chunk"]
            for item in candidates.values()
            if item["semantic_score"] == 0.0
        ]
        if missing_chunks:
            semantic_scores = _compute_semantic_scores(missing_chunks, query_embedding)
            for chunk_id, semantic_score in semantic_scores.items():
                candidates[chunk_id]["semantic_score"] = semantic_score

    return list(candidates.values())


def _semantic_candidates(base_queryset, query_embedding):
    if not query_embedding:
        return []

    # Use pgvector CosineDistance query to sort directly in database
    chunks = list(
        base_queryset
        .annotate(distance=CosineDistance("embedding", query_embedding))
        .order_by("distance")[:KEYWORD_CANDIDATE_LIMIT]
    )
    return chunks


def _keyword_candidates(base_queryset, parsed_query):
    filters = []

    for phrase in parsed_query.get("phrases", []):
        filters.append(("content__icontains", phrase))
        filters.append(("heading_path__icontains", phrase))

    for date_range in parsed_query.get("date_ranges", []):
        from documents.services.query_parser import generate_date_variants
        for s in generate_date_variants(date_range["start"]):
            filters.append(("content__icontains", s))
        for e in generate_date_variants(date_range["end"]):
            filters.append(("content__icontains", e))

    for article_ref in parsed_query.get("article_refs", []):
        filters.append(("content__icontains", article_ref.replace("dieu", "Điều")))

    for term in parsed_query.get("terms", [])[:10]:
        filters.append(("content__icontains", term))
        filters.append(("heading_path__icontains", term))

    candidates = {}
    for lookup, value in filters:
        if not value:
            continue
        for chunk in base_queryset.filter(**{lookup: value})[:KEYWORD_CANDIDATE_LIMIT]:
            candidates[chunk.id] = chunk

    python_candidates = _python_keyword_candidates(base_queryset, parsed_query)
    for chunk in python_candidates:
        candidates[chunk.id] = chunk

    if not candidates:
        return list(base_queryset[: min(KEYWORD_CANDIDATE_LIMIT, 200)])
    return list(candidates.values())


def _python_keyword_candidates(base_queryset, parsed_query):
    chunks = list(base_queryset[:KEYWORD_CANDIDATE_LIMIT])
    scored = []
    required_ranges = {
        (item.get("start"), item.get("end"))
        for item in parsed_query.get("date_ranges", [])
    }

    for chunk in chunks:
        metadata = chunk.metadata or {}
        text = normalize_text(f"{chunk.heading_path} {chunk.content}")
        score = 0

        for phrase in parsed_query.get("phrases", []):
            if phrase in text:
                score += 4

        terms = parsed_query.get("terms", [])
        score += sum(1 for term in terms if term in text)

        chunk_ranges = {
            (item.get("start"), item.get("end"))
            for item in metadata.get("date_ranges", [])
        }
        if required_ranges & chunk_ranges:
            score += 8

        if score:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:KEYWORD_CANDIDATE_LIMIT]]


def _compute_semantic_scores(chunks, query_embedding):
    query_len = len(query_embedding)
    valid_chunks = []
    valid_embeddings = []

    for chunk in chunks:
        if chunk.embedding and len(chunk.embedding) == query_len:
            valid_chunks.append(chunk)
            valid_embeddings.append(chunk.embedding)
        elif chunk.embedding:
            logger.warning(
                "Skipping chunk %s due to embedding dimension mismatch (expected %d, got %s)",
                chunk.id,
                query_len,
                len(chunk.embedding),
            )

    if not valid_chunks:
        return {}

    query_vec = np.array(query_embedding, dtype=np.float32)
    doc_matrix = np.array(valid_embeddings, dtype=np.float32)
    dot_products = np.dot(doc_matrix, query_vec)
    doc_norms = np.linalg.norm(doc_matrix, axis=1)
    query_norm = np.linalg.norm(query_vec)
    norms = doc_norms * query_norm
    scores = np.zeros_like(dot_products)
    valid_norms = norms > 0
    scores[valid_norms] = dot_products[valid_norms] / norms[valid_norms]

    return {
        chunk.id: max(0.0, float(score))
        for chunk, score in zip(valid_chunks, scores)
    }


def _rank_candidates(candidates, parsed_query, query):
    ranked = []
    for item in candidates:
        chunk = item["chunk"]
        scores = score_chunk(parsed_query, chunk, item.get("semantic_score", 0.0))
        ranked.append({"chunk": chunk, "scores": scores})

    ranked.sort(
        key=lambda item: (
            item["scores"]["score"],
            item["scores"]["metadata_score"],
            item["scores"]["section_score"],
            item["scores"]["keyword_score"],
        ),
        reverse=True,
    )
    return _dedupe_nearby_chunks(ranked, query)


def _dedupe_nearby_chunks(ranked, query):
    deduped = []
    seen = set()
    for item in ranked:
        chunk = item["chunk"]
        metadata = chunk.metadata or {}
        section_key = (
            chunk.document_id,
            metadata.get("section_id") or chunk.chunk_index,
            metadata.get("section_title") or chunk.heading_path,
        )

        if section_key in seen and not _query_needs_multiple_section_parts(query):
            continue
        seen.add(section_key)
        deduped.append(item)
    return deduped


def _query_needs_multiple_section_parts(query):
    normalized = normalize_text(query)
    return any(term in normalized for term in ("bang", "toan bo", "chi tiet", "danh sach"))


def _format_result(item, parsed_query):
    chunk = item["chunk"]
    scores = item["scores"]
    document = chunk.document
    content = _build_context(chunk, parsed_query)
    page_num = _get_page_num(chunk, content)
    file_url = _get_file_url(document, page_num)
    metadata = chunk.metadata or {}

    return {
        "score": round(float(scores["score"]), 4),
        "semantic_score": round(float(scores["semantic_score"]), 4),
        "keyword_score": round(float(scores["keyword_score"]), 4),
        "metadata_score": round(float(scores["metadata_score"]), 4),
        "section_score": round(float(scores["section_score"]), 4),
        "document_id": document.id,
        "document_title": document.title,
        "factory": document.factory,
        "document_type": document.document_type,
        "heading_path": chunk.heading_path,
        "section_title": metadata.get("section_title", ""),
        "chunk_index": chunk.chunk_index,
        "content": content,
        "page_num": page_num,
        "file_url": file_url,
        "matched_metadata": _matched_metadata(parsed_query, metadata),
    }


def _build_context(chunk, parsed_query):
    metadata = chunk.metadata or {}
    content = chunk.content or ""
    focused = _focus_content_by_metadata(parsed_query, content)
    if focused != content:
        return focused

    if _should_expand_section(parsed_query, metadata):
        expanded = _expand_same_section(chunk)
        return expanded[:MAX_CONTEXT_CHARS]

    return content[:MAX_CONTEXT_CHARS]


def _focus_content_by_metadata(parsed_query, content):
    if not parsed_query.get("date_ranges") or not content:
        return content

    normalized_content = normalize_text(content)
    for date_range in parsed_query["date_ranges"]:
        start = re.escape(date_range["start"])
        end = re.escape(date_range["end"])
        match = re.search(rf"{start}\s*(?:den|toi|-)\s*{end}", normalized_content)
        if not match:
            continue

        original_start = min(match.start(), len(content))
        headings = list(
            re.finditer(
                r"(?m)^\s*(?:#{1,6}\s+|\*\*)?(?:[IVX]+|\d+(?:\.\d+)*)\.\s+",
                content,
            )
        )
        start_index = original_start
        for heading in headings:
            if heading.start() <= original_start:
                start_index = heading.start()
            else:
                break

        end_index = len(content)
        for heading in headings:
            if heading.start() > original_start:
                end_index = heading.start()
                break

        focused = content[start_index:end_index].strip()
        if focused:
            return focused[:MAX_CONTEXT_CHARS]

    return content


def _should_expand_section(parsed_query, metadata):
    if parsed_query.get("date_ranges"):
        return False
    if parsed_query.get("article_refs"):
        return False
    return any(
        phrase in parsed_query.get("phrases", [])
        for phrase in (
            "quy dinh nhiem vu trong mua lu",
            "nhiem vu trong mua lu",
            "quy dinh nhiem vu trong mua can",
            "nhiem vu trong mua can",
        )
    ) or bool(metadata.get("section_title") and metadata.get("section_part") == 0)


def _expand_same_section(chunk):
    metadata = chunk.metadata or {}
    section_id = metadata.get("section_id")
    if not section_id:
        return chunk.content or ""

    section_chunks = (
        DocumentChunk.objects.filter(
            document_id=chunk.document_id,
            metadata__section_id=section_id,
        )
        .order_by("chunk_index")
        .only("content", "chunk_index", "metadata")
    )
    content = "\n\n".join(item.content for item in section_chunks if item.content)
    return content or chunk.content or ""


def _get_page_num(chunk, content):
    if chunk.page_from:
        return chunk.page_from

    metadata = chunk.metadata or {}
    if metadata.get("page_from"):
        return metadata["page_from"]

    match = re.search(r"Trang\s+(\d+)", chunk.heading_path or "", re.IGNORECASE)
    if match:
        return int(match.group(1))

    match = re.search(r"##\s+Trang\s+(\d+)", content or "", re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _get_file_url(document, page_num):
    if not document.original_file:
        return ""
    base_url = getattr(settings, "KHO_BACKEND_BASE_URL", "http://localhost:8000").rstrip("/")
    file_url = f"{base_url}/api/documents/{document.id}/view/"
    if page_num and document.original_file.name.lower().endswith(".pdf"):
        return f"{file_url}#page={page_num}"
    return file_url


def _matched_metadata(parsed_query, metadata):
    metadata = metadata or {}
    query_ranges = {
        (item.get("start"), item.get("end"))
        for item in parsed_query.get("date_ranges", [])
    }
    chunk_ranges = metadata.get("date_ranges", [])
    matched_ranges = [
        item
        for item in chunk_ranges
        if (item.get("start"), item.get("end")) in query_ranges
    ]

    query_articles = set(parsed_query.get("article_refs", []))
    matched_articles = [
        item
        for item in metadata.get("article_refs", [])
        if item in query_articles
    ]

    return {
        "date_ranges": matched_ranges,
        "article_refs": matched_articles,
        "section_title": metadata.get("section_title", ""),
        "page_from": metadata.get("page_from"),
        "page_to": metadata.get("page_to"),
    }
