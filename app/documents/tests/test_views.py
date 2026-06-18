import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from documents.models import Document, DocumentFolder
from khovattu.models import Bang_nha_may


class DocumentViewApiTests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        User = get_user_model()
        self.user = User.objects.create_user(
            email="docs-view@example.com",
            username="docs_view",
            password="testpass123",
        )
        UserProfile.objects.create(user=self.user, can_use_ai_documents=True, is_all_factories=True)

        self.no_ai_user = User.objects.create_user(
            email="docs-no-ai@example.com",
            username="docs_no_ai",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.no_ai_user,
            can_use_ai_tools=True,
            can_use_ai_documents=False,
        )

        self.songhinh = Bang_nha_may.objects.create(
            ma_nha_may="SH",
            ten_nha_may="Song Hinh",
        )
        self.songhinh_user = User.objects.create_user(
            email="docs-songhinh@example.com",
            username="docs_songhinh",
            password="testpass123",
        )
        UserProfile.objects.create(
            user=self.songhinh_user,
            nha_may=self.songhinh,
            can_use_ai_documents=True,
        )

        self.document = Document.objects.create(
            title="Công văn test",
            factory=Document.FACTORY_GENERAL,
            status=Document.STATUS_READY,
            document_type="cong_van",
        )
        self.document.original_file.save(
            "cong-van.docx",
            ContentFile(b"docx-content"),
            save=True,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_view_document_requires_ai_documents_permission(self):
        url = reverse("documents-view", args=[self.document.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_view_document_uses_file_mime_type(self):
        self.client.force_authenticate(self.user)
        url = reverse("documents-view", args=[self.document.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    def test_list_documents_requires_ai_documents_permission(self):
        self.client.force_authenticate(self.no_ai_user)
        response = self.client.get(reverse("documents-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("documents.views._enqueue_process_document")
    def test_upload_document_allows_factory_within_expanded_scope(self, enqueue_mock):
        self.client.force_authenticate(self.songhinh_user)
        upload = SimpleUploadedFile(
            "vinhson.txt",
            b"noi dung tai lieu",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("documents-list"),
            {
                "title": "Tai lieu Vinh Son",
                "file": upload,
                "factory": Document.FACTORY_VINHSON,
                "document_type": "cong_van",
                "visibility": "internal",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Document.objects.filter(title="Tai lieu Vinh Son").exists())
        enqueue_mock.assert_called_once()

    @patch("documents.views._enqueue_process_document")
    def test_upload_document_allows_factory_in_user_scope(self, enqueue_mock):
        self.client.force_authenticate(self.songhinh_user)
        upload = SimpleUploadedFile(
            "songhinh.txt",
            b"noi dung tai lieu",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("documents-list"),
            {
                "title": "Tai lieu Song Hinh",
                "file": upload,
                "factory": Document.FACTORY_SONGHINH,
                "document_type": "cong_van",
                "visibility": "internal",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Document.objects.filter(
                title="Tai lieu Song Hinh",
                factory=Document.FACTORY_SONGHINH,
                created_by=self.songhinh_user,
            ).exists()
        )
        enqueue_mock.assert_called_once()

    @patch("documents.views._enqueue_process_document")
    def test_reprocess_document_within_expanded_scope_returns_200(self, enqueue_mock):
        vinhson_doc = Document.objects.create(
            title="Tai lieu Vinh Son",
            original_file="ai_documents/vinhson.pdf",
            factory=Document.FACTORY_VINHSON,
            status=Document.STATUS_READY,
        )
        self.client.force_authenticate(self.songhinh_user)

        response = self.client.post(
            reverse("documents-reprocess", args=[vinhson_doc.id]),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        enqueue_mock.assert_called_once()


class DocumentFolderApiTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="folder-test@example.com",
            username="folder_test",
            password="testpass123",
        )
        UserProfile.objects.create(user=self.user, can_use_ai_documents=True)
        self.client.force_authenticate(self.user)

    def test_crud_document_folders(self):
        # List folders (should be empty initially)
        response = self.client.get(reverse("document-folders-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

        # Create folder
        response = self.client.post(
            reverse("document-folders-list"),
            {"name": "Thư mục kiểm tra", "description": "Mô tả kiểm tra"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Thư mục kiểm tra")
        self.assertEqual(response.data["slug"], "thu-muc-kiem-tra")
        folder_id = response.data["id"]

        # List folders again
        response = self.client.get(reverse("document-folders-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

        # Update folder
        response = self.client.put(
            reverse("document-folders-detail", args=[folder_id]),
            {"name": "Thư mục đã sửa", "description": "Mô tả mới"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Thư mục đã sửa")

        # Delete folder
        response = self.client.delete(reverse("document-folders-detail", args=[folder_id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_update_document_metadata(self):
        # Create a folder first
        folder = DocumentFolder.objects.create(name="Folder test update")

        # Create a document
        doc = Document.objects.create(
            title="Original Title",
            original_file="ai_documents/test.pdf",
            factory=Document.FACTORY_GENERAL,
            document_type="quytrinh"
        )

        # Update metadata via API
        url = reverse("documents-detail", args=[doc.id])
        response = self.client.patch(
            url,
            {
                "title": "Updated Title",
                "document_type": "quy-dinh",
                "folders": [folder.id]
            },
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertEqual(doc.title, "Updated Title")
        self.assertEqual(doc.document_type, "quy_dinh")
        self.assertEqual(list(doc.folders.values_list("id", flat=True)), [folder.id])
