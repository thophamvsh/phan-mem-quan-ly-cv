import logging

from django.db import transaction
from django.utils import timezone

from documents.models import Document, DocumentChunk
from documents.services.chunking import chunk_markdown
from documents.services.docling_convert import convert_file_to_markdown
from documents.services.embeddings import get_embedding, get_embeddings_batch


logger = logging.getLogger(__name__)


def process_document(document):
    document.status = Document.STATUS_PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])

    try:
        logger.info("Processing document %s started.", document.id)
        markdown = convert_file_to_markdown(document.original_file.path)
        chunks = chunk_markdown(markdown)
        contents = [chunk["content"] for chunk in chunks]
        embeddings = get_embeddings_batch(contents)
        prepared_chunks = []
        for index, chunk in enumerate(chunks):
            prepared_chunks.append(
                {
                    "chunk_index": index,
                    "heading_path": chunk.get("heading_path", ""),
                    "content": chunk["content"],
                    "token_count": chunk.get("token_count", 0),
                    "page_from": chunk.get("page_from"),
                    "page_to": chunk.get("page_to"),
                    "metadata": chunk.get("metadata", {}),
                    "embedding": embeddings[index],
                }
            )

        with transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()
            for chunk in prepared_chunks:
                DocumentChunk.objects.create(
                    document=document,
                    chunk_index=chunk["chunk_index"],
                    heading_path=chunk["heading_path"],
                    content=chunk["content"],
                    token_count=chunk["token_count"],
                    page_from=chunk["page_from"],
                    page_to=chunk["page_to"],
                    metadata=chunk["metadata"],
                    embedding=chunk["embedding"],
                )
            document.markdown_text = markdown
            document.status = Document.STATUS_READY
            document.processed_at = timezone.now()
            document.error_message = ""
            document.save(
                update_fields=[
                    "markdown_text",
                    "status",
                    "processed_at",
                    "error_message",
                    "updated_at",
                ]
            )
        logger.info("Processing document %s completed with %s chunks.", document.id, len(prepared_chunks))
    except Exception as exc:
        logger.exception("Processing document %s failed.", document.id)
        document.status = Document.STATUS_FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message", "updated_at"])
        raise

    return document
