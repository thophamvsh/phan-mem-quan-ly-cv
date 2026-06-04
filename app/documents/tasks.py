import logging

from celery import shared_task
from django.db import close_old_connections

from documents.models import Document
from documents.services.ingest import process_document


logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def process_document_task(self, document_id):
    close_old_connections()
    try:
        document = Document.objects.get(pk=document_id)
        process_document(document)
    except Document.DoesNotExist:
        logger.warning("Document %s no longer exists before queued processing started.", document_id)
    finally:
        close_old_connections()
