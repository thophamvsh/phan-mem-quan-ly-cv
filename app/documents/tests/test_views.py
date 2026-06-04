import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import UserProfile
from documents.models import Document


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
        UserProfile.objects.create(user=self.user, can_use_ai_tools=True, is_all_factories=True)

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

    def test_view_document_requires_ai_tools_permission(self):
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
