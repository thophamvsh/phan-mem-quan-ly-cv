from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from documents.serializers import DocumentSearchSerializer, DocumentUploadSerializer


class DocumentSerializerTests(SimpleTestCase):
    def test_upload_serializer_canonicalizes_document_type(self):
        serializer = DocumentUploadSerializer(
            data={
                "title": "Nghị định vận hành",
                "file": SimpleUploadedFile(
                    "nghi-dinh.pdf",
                    b"%PDF-1.4\n",
                    content_type="application/pdf",
                ),
                "factory": "general",
                "document_type": "Nghị định",
                "visibility": "internal",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["document_type"], "nghi_dinh")

    def test_upload_serializer_rejects_legacy_doc_file(self):
        serializer = DocumentUploadSerializer(
            data={
                "title": "File doc cu",
                "file": SimpleUploadedFile(
                    "old.doc",
                    b"legacy",
                    content_type="application/msword",
                ),
                "factory": "general",
                "document_type": "Công văn",
                "visibility": "internal",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)

    def test_search_serializer_canonicalizes_document_type(self):
        serializer = DocumentSearchSerializer(
            data={
                "query": "tìm công văn về vận hành",
                "factory": "",
                "document_type": "Công văn",
                "limit": 8,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["document_type"], "cong_van")
