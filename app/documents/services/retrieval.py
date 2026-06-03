import logging
import numpy as np

from ai_tools.permissions import (
    AI_TOOL_SCOPE_SONGHINH,
    AI_TOOL_SCOPE_VINHSON,
    get_ai_tool_scopes_for_user,
)
from documents.models import Document, DocumentChunk
from documents.services.embeddings import get_embedding

logger = logging.getLogger(__name__)

MIN_SIMILARITY_SCORE = 0.40


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


def normalize_doc_type(val):
    if not val:
        return ""
    import unicodedata
    s = str(val).lower().replace("đ", "d")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("_", " ").strip()


def search_documents(user, query, factory="", document_type="", limit=5):
    query = (query or "").strip()
    if not query:
        return []

    allowed_factories = get_allowed_factories_for_user(user)
    if factory:
        if factory not in allowed_factories:
            return []
        # General documents are cross-factory and always visible/relevant
        allowed_factories = {factory, Document.FACTORY_GENERAL}

    chunk_queryset = (
        DocumentChunk.objects.select_related("document")
        .defer("document__markdown_text")
        .filter(document__status=Document.STATUS_READY, document__factory__in=allowed_factories)
        .exclude(embedding=[])
    )

    chunks = list(chunk_queryset[:2000])
    if not chunks:
        return []

    if document_type:
        norm_type_query = normalize_doc_type(document_type)
        if norm_type_query:
            filtered_chunks = [
                c for c in chunks
                if normalize_doc_type(c.document.document_type) == norm_type_query
            ]
            if filtered_chunks:
                chunks = filtered_chunks

    query_embedding = get_embedding(query)
    if not query_embedding:
        return []

    query_len = len(query_embedding)
    valid_chunks = []
    valid_embeddings = []
    for chunk in chunks:
        if chunk.embedding and len(chunk.embedding) == query_len:
            valid_chunks.append(chunk)
            valid_embeddings.append(chunk.embedding)
        else:
            logger.warning(
                "Skipping chunk %s due to embedding dimension mismatch (expected %d, got %s)",
                chunk.id,
                query_len,
                len(chunk.embedding) if chunk.embedding else 0,
            )

    if not valid_chunks:
        return []

    # Vectorized cosine similarity using NumPy
    query_vec = np.array(query_embedding, dtype=np.float32)
    doc_matrix = np.array(valid_embeddings, dtype=np.float32)

    dot_products = np.dot(doc_matrix, query_vec)
    doc_norms = np.linalg.norm(doc_matrix, axis=1)
    query_norm = np.linalg.norm(query_vec)

    norms = doc_norms * query_norm
    scores = np.zeros_like(dot_products)
    valid_norms = norms > 0
    scores[valid_norms] = dot_products[valid_norms] / norms[valid_norms]

    scored = []
    for idx, score in enumerate(scores):
        if score >= MIN_SIMILARITY_SCORE:
            scored.append((float(score), valid_chunks[idx]))

    scored.sort(key=lambda item: item[0], reverse=True)

    import os
    import re
    base_url = os.environ.get("KHO_BACKEND_BASE_URL", "http://localhost:8000").rstrip("/")

    results = []
    for score, chunk in scored[: max(1, min(int(limit or 3), 12))]:
        document = chunk.document
        file_url = ""
        if document.original_file:
            file_url = f"{base_url}{document.original_file.url}"

        page_num = chunk.page_from
        if not page_num:
            match = re.search(r"Trang\s+(\d+)", chunk.heading_path or "", re.IGNORECASE)
            if match:
                page_num = int(match.group(1))
            else:
                match = re.search(r"##\s+Trang\s+(\d+)", chunk.content or "", re.IGNORECASE)
                if match:
                    page_num = int(match.group(1))

        if page_num and file_url:
            file_url = f"{file_url}#page={page_num}"

        results.append(
            {
                "score": round(float(score), 4),
                "document_id": document.id,
                "document_title": document.title,
                "factory": document.factory,
                "document_type": document.document_type,
                "heading_path": chunk.heading_path,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "page_num": page_num,
                "file_url": file_url,
            }
        )
    return results
