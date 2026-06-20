import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from core.models import UserProfile
from documents.models import Document, DocumentChunk, DocumentFolder
from documents.services.query_parser import parse_query
from documents.services.retrieval import (
    _build_context,
    _compute_semantic_scores,
    _dedupe_nearby_chunks,
    _focus_content_by_metadata,
    _format_result,
    _get_file_url,
    _get_page_num,
    _matched_metadata,
    _query_needs_multiple_section_parts,
    _resolve_allowed_factories,
    search_documents,
)


class DocumentSearchTests(TestCase):
    databases = {"default"}

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root, KHO_BACKEND_BASE_URL="http://backend/")
        self.override.enable()
        self.user = get_user_model().objects.create_user(
            username="retrieval-edge",
            email="retrieval-edge@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=self.user, can_use_ai_documents=True, is_all_factories=True)
        self.folder = DocumentFolder.objects.create(name="Operations")
        self.document = Document.objects.create(
            title="Quy trinh van hanh ho chua",
            factory=Document.FACTORY_SONGHINH,
            status=Document.STATUS_READY,
            document_type="quy_trinh",
        )
        self.document.original_file.save("quy-trinh.pdf", ContentFile(b"pdf"), save=True)
        self.document.folders.add(self.folder)
        self.chunk = DocumentChunk.objects.create(
            document=self.document,
            chunk_index=0,
            heading_path="Dieu 1 > Trang 3",
            content="Quy trinh van hanh cua ho chua Song Hinh trong mua lu.",
            page_from=3,
            metadata={"section_id": "s1", "section_title": "Nhiem vu trong mua lu", "section_part": 0},
            embedding=[1.0] + [0.0] * 1535,
        )
        DocumentChunk.objects.create(
            document=self.document,
            chunk_index=1,
            heading_path="Dieu 1",
            content="Chi tiet danh sach nhiem vu tiep theo.",
            metadata={"section_id": "s1", "section_title": "Nhiem vu trong mua lu", "section_part": 1},
            embedding=[1.0] + [0.0] * 1535,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    @patch("documents.services.retrieval.get_embedding", return_value=[1.0] + [0.0] * 1535)
    def test_search_filters_and_returns_ranked_context_with_file_link(self, _embedding):
        results = search_documents(
            self.user,
            "quy trinh van hanh mua lu",
            factory=Document.FACTORY_SONGHINH,
            document_type="Quy trình",
            folder_id=self.folder.id,
            limit=1,
        )
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["document_id"], self.document.id)
        self.assertEqual(result["page_num"], 3)
        self.assertEqual(result["file_url"], f"http://backend/api/documents/{self.document.id}/view/#page=3")
        self.assertIn("Chi tiet danh sach", result["content"])

    @patch("documents.services.retrieval.get_embedding", return_value=[1.0] + [0.0] * 1535)
    def test_search_rejects_empty_unknown_factory_and_nonmatching_type(self, _embedding):
        self.assertEqual(search_documents(self.user, ""), [])
        self.assertEqual(search_documents(self.user, "query", factory="unknown"), [])
        self.assertEqual(search_documents(self.user, "query", document_type="cong_van"), [])

    @patch("documents.services.retrieval.get_embedding", return_value=[1.0] + [0.0] * 1535)
    def test_search_excludes_non_ready_and_folder_mismatch(self, _embedding):
        self.document.status = Document.STATUS_FAILED
        self.document.save(update_fields=["status"])
        self.assertEqual(search_documents(self.user, "quy trinh"), [])
        self.document.status = Document.STATUS_READY
        self.document.save(update_fields=["status"])
        other_folder = DocumentFolder.objects.create(name="Other")
        self.assertEqual(search_documents(self.user, "quy trinh", folder_id=other_folder.id), [])

    def test_semantic_scores_skip_dimension_mismatch_and_zero_vectors(self):
        valid = SimpleNamespace(id=1, embedding=[1.0, 0.0])
        mismatch = SimpleNamespace(id=2, embedding=[1.0])
        zero = SimpleNamespace(id=3, embedding=[0.0, 0.0])
        scores = _compute_semantic_scores([valid, mismatch, zero], [1.0, 0.0])
        self.assertEqual(scores[1], 1.0)
        self.assertEqual(scores[3], 0.0)
        self.assertNotIn(2, scores)
        self.assertEqual(_compute_semantic_scores([mismatch], [1.0, 0.0]), {})

    def test_context_page_url_dedupe_and_metadata_helpers(self):
        parsed = parse_query("quy dinh nhiem vu trong mua lu")
        context = _build_context(self.chunk, parsed)
        self.assertIn("Chi tiet danh sach", context)
        self.assertEqual(_get_page_num(self.chunk, context), 3)
        self.assertTrue(_get_file_url(self.document, 3).endswith("#page=3"))
        self.assertTrue(_query_needs_multiple_section_parts("danh sach chi tiet"))
        self.assertFalse(_query_needs_multiple_section_parts("tom tat"))

        scores = {"score": 1, "semantic_score": 1, "keyword_score": 1, "metadata_score": 0, "section_score": 0}
        formatted = _format_result({"chunk": self.chunk, "scores": scores}, parsed)
        self.assertEqual(formatted["document_title"], self.document.title)

        same_section = SimpleNamespace(document_id=1, chunk_index=0, heading_path="h", metadata={"section_id": "s"})
        duplicate = SimpleNamespace(document_id=1, chunk_index=1, heading_path="h", metadata={"section_id": "s"})
        ranked = [{"chunk": same_section}, {"chunk": duplicate}]
        self.assertEqual(len(_dedupe_nearby_chunks(ranked, "tom tat")), 1)
        self.assertEqual(len(_dedupe_nearby_chunks(ranked, "danh sach")), 2)

    def test_date_focus_page_fallback_and_matched_metadata(self):
        content = "1. Pham vi\nTu 01/01/2026 den 02/01/2026 noi dung can lay.\n2. Khac\nBo qua"
        parsed = {"date_ranges": [{"start": "01/01/2026", "end": "02/01/2026"}], "article_refs": ["dieu 1"]}
        focused = _focus_content_by_metadata(parsed, content)
        self.assertIn("Pham vi", focused)
        self.assertNotIn("Bo qua", focused)

        chunk = SimpleNamespace(page_from=None, heading_path="Trang 7", metadata={}, content="")
        self.assertEqual(_get_page_num(chunk, ""), 7)
        chunk.heading_path = ""
        self.assertEqual(_get_page_num(chunk, "## Trang 8\nBody"), 8)
        self.assertIsNone(_get_page_num(chunk, "Body"))

        metadata = {
            "date_ranges": [{"start": "01/01/2026", "end": "02/01/2026"}],
            "article_refs": ["dieu 1", "dieu 2"],
            "section_title": "Pham vi",
        }
        matched = _matched_metadata(parsed, metadata)
        self.assertEqual(len(matched["date_ranges"]), 1)
        self.assertEqual(matched["article_refs"], ["dieu 1"])

    def test_factory_resolution_and_file_url_without_attachment(self):
        allowed = _resolve_allowed_factories(self.user, "")
        self.assertIn(Document.FACTORY_GENERAL, allowed)
        self.assertEqual(
            _resolve_allowed_factories(self.user, Document.FACTORY_VINHSON),
            {Document.FACTORY_VINHSON, Document.FACTORY_GENERAL},
        )
        self.assertEqual(_resolve_allowed_factories(self.user, "invalid"), set())
        no_file = Document.objects.create(title="No file")
        self.assertEqual(_get_file_url(no_file, None), "")
