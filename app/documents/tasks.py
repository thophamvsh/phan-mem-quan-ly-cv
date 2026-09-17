import logging

from celery import shared_task
from django.db import close_old_connections

from documents.models import Document, DocumentChunk, DocumentFolder, ModuleGuide
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


def _guide_factory(guide):
    code = str(getattr(guide.nha_may, "ma_nha_may", "") or "").upper()
    return {
        "SH": Document.FACTORY_SONGHINH,
        "VS": Document.FACTORY_VINHSON,
        "TKT": Document.FACTORY_THUONGKONTUM,
    }.get(code, Document.FACTORY_GENERAL)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sync_module_guide_to_rag(self, guide_id):
    close_old_connections()
    try:
        guide = ModuleGuide.objects.select_related("nha_may", "created_by").get(
            pk=guide_id,
            status=ModuleGuide.STATUS_PUBLISHED,
        )
        folder, _created = DocumentFolder.objects.get_or_create(
            name="Quy trình vận hành",
            defaults={"description": "Tài liệu hướng dẫn được đồng bộ từ sổ vận hành."},
        )
        document, _created = Document.objects.update_or_create(
            module_guide=guide,
            defaults={
                "title": guide.title,
                "original_file": guide.file.name,
                "status": Document.STATUS_UPLOADED,
                "document_type": guide.document_kind,
                "factory": _guide_factory(guide),
                "visibility": "internal",
                "version": 1,
                "created_by": guide.created_by,
                "is_active": True,
                "error_message": "",
            },
        )
        document.folders.add(folder)
        process_document(document)
    except ModuleGuide.DoesNotExist:
        logger.info("Module guide %s is no longer published; RAG sync skipped.", guide_id)
    finally:
        close_old_connections()


@shared_task
def retire_module_guide_from_rag(guide_id):
    DocumentChunk.objects.filter(document__module_guide_id=guide_id).delete()
    Document.objects.filter(module_guide_id=guide_id).update(is_active=False)
