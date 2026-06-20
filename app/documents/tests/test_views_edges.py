import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from documents.models import Document, DocumentFolder
from documents.serializers import DocumentUploadSerializer
from documents.views import _enqueue_process_document, _run_process_in_background


class DocumentSerializerAndModelEdgeTests(TestCase):
    databases = {"default"}

    def test_upload_rejects_file_over_50mb(self):
        upload = SimpleUploadedFile("large.pdf", b"x", content_type="application/pdf")
        upload.size = 50 * 1024 * 1024 + 1
        serializer = DocumentUploadSerializer(
            data={
                "title": "Large",
                "file": upload,
                "factory": Document.FACTORY_GENERAL,
                "document_type": "bao_cao",
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)

    @patch("documents.models.slugify", return_value="")
    @patch("uuid.uuid4")
    def test_folder_uses_uuid_slug_when_name_cannot_be_slugified(self, uuid4, _slugify):
        uuid4.return_value = SimpleNamespace(hex="abcdef123456")
        folder = DocumentFolder.objects.create(name="!!!")
        self.assertEqual(folder.slug, "abcdef12")
        self.assertEqual(str(folder), "!!!")


class DocumentApiEdgeTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = get_user_model().objects.create_user(
            username="documents-edge",
            email="documents-edge@example.com",
            password="testpass123",
        )
        UserProfile.objects.create(user=self.user, can_use_ai_documents=True, is_all_factories=True)
        self.client.force_authenticate(self.user)
        self.folder = DocumentFolder.objects.create(name="Filtered")
        self.ready = Document.objects.create(
            title="Ready",
            original_file="ai_documents/ready.pdf",
            status=Document.STATUS_READY,
            factory=Document.FACTORY_SONGHINH,
        )
        self.ready.folders.add(self.folder)
        self.failed = Document.objects.create(
            title="Failed",
            original_file="ai_documents/failed.pdf",
            status=Document.STATUS_FAILED,
            factory=Document.FACTORY_VINHSON,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_list_filters_factory_status_and_folder(self):
        response = self.client.get(
            reverse("documents-list"),
            {"factory": Document.FACTORY_SONGHINH, "status": Document.STATUS_READY, "folder_id": self.folder.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data["results"]], [self.ready.id])

    @patch("documents.views.search_documents", return_value=[{"document_id": 1, "content": "match"}])
    def test_search_endpoint_validates_and_forwards_filters(self, search):
        response = self.client.post(
            reverse("documents-search"),
            {"query": "quy trinh", "document_type": "Quy trình", "limit": 3},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["content"], "match")
        self.assertEqual(search.call_args.kwargs["document_type"], "quy_trinh")

        invalid = self.client.post(reverse("documents-search"), {"query": "x", "limit": 99}, format="json")
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reprocess_missing_document_returns_404(self):
        response = self.client.post(reverse("documents-reprocess", args=[999999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_rejects_document_without_attachment_and_missing_physical_file(self):
        no_file = Document.objects.create(title="No file")
        response = self.client.get(reverse("documents-view", args=[no_file.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        response = self.client.get(reverse("documents-view", args=[self.ready.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_delete_and_update_without_folders(self):
        self.ready.folders.add(self.folder)
        response = self.client.patch(
            reverse("documents-detail", args=[self.ready.id]),
            {"title": "Updated", "factory": Document.FACTORY_GENERAL, "document_type": "Công văn"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.ready.refresh_from_db()
        self.assertEqual(self.ready.document_type, "cong_van")
        self.assertEqual(list(self.ready.folders.values_list("id", flat=True)), [self.folder.id])

        deleted = self.client.delete(reverse("documents-detail", args=[self.failed.id]))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)


class DocumentBackgroundProcessingTests(TestCase):
    databases = {"default"}

    @override_settings(DOCUMENTS_USE_CELERY=True)
    @patch("documents.tasks.process_document_task.delay")
    @patch("documents.views._run_process_in_background")
    def test_enqueue_uses_celery_when_available(self, background, delay):
        _enqueue_process_document(10)
        delay.assert_called_once_with(10)
        background.assert_not_called()

    @override_settings(DOCUMENTS_USE_CELERY=True)
    @patch("documents.tasks.process_document_task.delay", side_effect=RuntimeError("broker offline"))
    @patch("documents.views._run_process_in_background")
    def test_enqueue_falls_back_to_thread_when_celery_fails(self, background, _delay):
        _enqueue_process_document(10)
        background.assert_called_once_with(10)

    @patch("documents.views.threading.Thread")
    @patch("documents.views.close_old_connections")
    @patch("documents.views.process_document")
    def test_background_runner_processes_document_and_closes_connections(self, process, close, thread):
        document = Document.objects.create(title="Background", original_file="background.txt")

        def run_immediately(*, target, daemon):
            worker = Mock()
            worker.start.side_effect = target
            return worker

        thread.side_effect = run_immediately
        _run_process_in_background(document.id)
        process.assert_called_once()
        self.assertEqual(close.call_count, 2)

    @patch("documents.views.threading.Thread")
    @patch("documents.views.close_old_connections")
    @patch("documents.views.process_document")
    def test_background_runner_ignores_deleted_document(self, process, close, thread):
        def run_immediately(*, target, daemon):
            worker = Mock()
            worker.start.side_effect = target
            return worker

        thread.side_effect = run_immediately
        _run_process_in_background(999999)
        process.assert_not_called()
        self.assertEqual(close.call_count, 2)
