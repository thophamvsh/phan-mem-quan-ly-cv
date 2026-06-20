import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from documents.services.docling_convert import (
    _extract_pdf_text,
    _extract_pdf_text_or_ocr,
    _fallback_text,
    _ocr_pdf,
    convert_file_to_markdown,
)


class DoclingConversionEdgeTests(SimpleTestCase):
    def test_text_file_and_legacy_doc(self):
        with tempfile.TemporaryDirectory() as directory:
            text_path = Path(directory) / "sample.txt"
            text_path.write_text("noi dung", encoding="utf-8")
            self.assertEqual(convert_file_to_markdown(text_path), "noi dung")

            doc_path = Path(directory) / "legacy.doc"
            doc_path.write_bytes(b"legacy")
            with self.assertRaisesRegex(ValueError, "docx"):
                convert_file_to_markdown(doc_path)

    @patch("documents.services.docling_convert._extract_pdf_text_or_ocr", return_value="OCR")
    @patch("docling.document_converter.DocumentConverter")
    def test_pdf_uses_ocr_when_docling_text_is_low_quality(self, converter, ocr):
        converter.return_value.convert.return_value = SimpleNamespace(
            document=SimpleNamespace(export_to_markdown=lambda: "short")
        )
        self.assertEqual(convert_file_to_markdown("sample.pdf"), "OCR")
        ocr.assert_called_once()

    @patch("docling.document_converter.DocumentConverter")
    def test_docling_success_and_non_pdf_conversion_error(self, converter):
        body = "Quy dinh van hanh " * 40
        converter.return_value.convert.return_value = SimpleNamespace(
            document=SimpleNamespace(export_to_markdown=lambda: body)
        )
        self.assertEqual(convert_file_to_markdown("sample.docx"), body)

        converter.return_value.convert.side_effect = RuntimeError("broken")
        with self.assertRaisesRegex(ValueError, "broken"):
            convert_file_to_markdown("sample.xlsx")

    @patch("documents.services.docling_convert._ocr_pdf", return_value="OCR")
    @patch("documents.services.docling_convert._extract_pdf_text", return_value="short")
    def test_pdf_fallback_uses_ocr_for_short_text(self, _extract, ocr):
        self.assertEqual(_extract_pdf_text_or_ocr(Path("sample.pdf")), "OCR")
        ocr.assert_called_once()

    @patch("pypdf.PdfReader")
    def test_extract_pdf_text_formats_pages_and_rejects_empty_pdf(self, reader):
        reader.return_value.pages = [Mock(extract_text=Mock(return_value="Page one")), Mock(extract_text=Mock(return_value=""))]
        result = _extract_pdf_text(Path("sample.pdf"))
        self.assertIn("## Trang 1", result)
        self.assertIn("Page one", result)

        reader.return_value.pages = [Mock(extract_text=Mock(return_value=""))]
        with self.assertRaisesRegex(ValueError, "PDF"):
            _extract_pdf_text(Path("sample.pdf"))

    @patch("pdf2image.convert_from_path")
    @patch("pytesseract.image_to_string")
    def test_ocr_pdf_formats_pages_and_handles_empty_or_conversion_error(self, image_to_string, convert):
        convert.return_value = [object(), object()]
        image_to_string.side_effect = ["OCR one", ""]
        self.assertIn("## Trang 1", _ocr_pdf(Path("sample.pdf")))

        image_to_string.side_effect = ["", ""]
        with self.assertRaisesRegex(ValueError, "OCR"):
            _ocr_pdf(Path("sample.pdf"))

        convert.side_effect = RuntimeError("poppler")
        with self.assertRaisesRegex(ValueError, "poppler"):
            _ocr_pdf(Path("sample.pdf"))

    def test_binary_fallback_returns_decoded_text_or_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.bin"
            path.write_bytes("nội dung".encode())
            self.assertIn("nội dung", _fallback_text(path))
            path.write_bytes(b"")
            self.assertIn("data.bin", _fallback_text(path))
