import json
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from documents.ai_tools import handle_document_tool_call
from documents.models import Document, DocumentChunk
from documents.services.ingest import process_document
from documents.tasks import process_document_task


class DocumentIngestTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.document = Document.objects.create(title="Test", original_file="")
        self.document.original_file.save("test.txt", ContentFile(b"content"), save=True)
        DocumentChunk.objects.create(
            document=self.document,
            chunk_index=0,
            content="old",
            embedding=[0.0] * 1536,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    @patch("documents.services.ingest.get_embeddings_batch", return_value=[[0.1] * 1536, [0.2] * 1536])
    @patch("documents.services.ingest.chunk_markdown")
    @patch("documents.services.ingest.convert_file_to_markdown", return_value="# Heading\nBody")
    def test_process_document_replaces_chunks_and_marks_ready(self, _convert, chunk_markdown, _embeddings):
        chunk_markdown.return_value = [
            {"content": "first", "heading_path": "Heading", "token_count": 2, "page_from": 1, "page_to": 1, "metadata": {"section_id": "s1"}},
            {"content": "second", "token_count": 1},
        ]
        result = process_document(self.document)
        self.document.refresh_from_db()
        self.assertEqual(result.id, self.document.id)
        self.assertEqual(self.document.status, Document.STATUS_READY)
        self.assertEqual(self.document.markdown_text, "# Heading\nBody")
        self.assertIsNotNone(self.document.processed_at)
        self.assertEqual(list(self.document.chunks.values_list("content", flat=True)), ["first", "second"])

    @patch("documents.services.ingest.convert_file_to_markdown", side_effect=RuntimeError("convert failed"))
    def test_process_document_marks_failed_and_preserves_existing_chunks(self, _convert):
        with self.assertRaisesRegex(RuntimeError, "convert failed"):
            process_document(self.document)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.STATUS_FAILED)
        self.assertIn("convert failed", self.document.error_message)
        self.assertEqual(self.document.chunks.get().content, "old")

    @patch("documents.services.ingest.get_embeddings_batch", return_value=[])
    @patch("documents.services.ingest.chunk_markdown", return_value=[{"content": "new"}])
    @patch("documents.services.ingest.convert_file_to_markdown", return_value="new")
    def test_process_document_fails_when_embedding_count_is_inconsistent(self, _convert, _chunks, _embeddings):
        with self.assertRaises(IndexError):
            process_document(self.document)
        self.document.refresh_from_db()
        self.assertEqual(self.document.status, Document.STATUS_FAILED)
        self.assertEqual(self.document.chunks.get().content, "old")


class DocumentTaskAndToolTests(TestCase):
    databases = {"default"}

    @patch("documents.tasks.close_old_connections")
    @patch("documents.tasks.process_document")
    def test_task_processes_existing_document_and_closes_connections(self, process, close):
        document = Document.objects.create(title="Task", original_file="task.txt")
        process_document_task.run(document.id)
        process.assert_called_once()
        self.assertEqual(close.call_count, 2)

    @patch("documents.tasks.close_old_connections")
    @patch("documents.tasks.process_document")
    def test_task_ignores_deleted_document(self, process, close):
        process_document_task.run(999999)
        process.assert_not_called()
        self.assertEqual(close.call_count, 2)

    @staticmethod
    def _tool_call(arguments):
        return SimpleNamespace(function=SimpleNamespace(arguments=json.dumps(arguments)))

    @patch("documents.ai_tools.has_ai_documents_permission", return_value=False)
    def test_document_tool_denies_user_without_permission(self, _permission):
        result = handle_document_tool_call(Mock(), self._tool_call({"query": "test"}))
        self.assertIn("khong co quyen", result["content"])

    @patch("documents.ai_tools.search_documents", return_value=[])
    @patch("documents.ai_tools.has_ai_documents_permission", return_value=True)
    def test_document_tool_handles_no_results(self, _permission, search):
        result = handle_document_tool_call(Mock(), self._tool_call({"query": "test", "limit": 2}))
        self.assertIn("Khong tim thay", result["content"])
        search.assert_called_once()

    @patch("documents.ai_tools.search_documents")
    @patch("documents.ai_tools.has_ai_documents_permission", return_value=True)
    def test_document_tool_formats_heading_page_link_and_score(self, _permission, search):
        search.return_value = [{
            "document_title": "Quy trinh",
            "heading_path": "Dieu 1",
            "page_num": 3,
            "file_url": "http://example/view/#page=3",
            "score": 1.25,
            "content": "Noi dung",
        }]
        result = handle_document_tool_call(Mock(), self._tool_call({"query": "test"}))
        self.assertIn("Quy trinh > Dieu 1", result["content"])
        self.assertIn("Trang: 3", result["content"])
        self.assertIn("Score: 1.25", result["content"])

    @patch("documents.ai_tools.has_ai_documents_permission", return_value=True)
    def test_document_tool_handles_malformed_json(self, _permission):
        tool_call = SimpleNamespace(function=SimpleNamespace(arguments="{invalid"))
        result = handle_document_tool_call(Mock(), tool_call)
        self.assertIn("khong hop le", result["content"])
