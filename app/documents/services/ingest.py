from django.db import transaction
from django.utils import timezone

from documents.models import Document, DocumentChunk
from documents.services.chunking import chunk_markdown
from documents.services.docling_convert import convert_file_to_markdown
from documents.services.embeddings import get_embedding


def process_document(document):
    document.status = Document.STATUS_PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])

    try:
        markdown = convert_file_to_markdown(document.original_file.path)
        chunks = chunk_markdown(markdown)
        with transaction.atomic():
            DocumentChunk.objects.filter(document=document).delete()
            for index, chunk in enumerate(chunks):
                content = chunk["content"]
                DocumentChunk.objects.create(
                    document=document,
                    chunk_index=index,
                    heading_path=chunk.get("heading_path", ""),
                    content=content,
                    token_count=chunk.get("token_count", 0),
                    page_from=chunk.get("page_from"),
                    page_to=chunk.get("page_to"),
                    metadata=chunk.get("metadata", {}),
                    embedding=get_embedding(content),
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
    except Exception as exc:
        document.status = Document.STATUS_FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message", "updated_at"])
        raise

    return document
