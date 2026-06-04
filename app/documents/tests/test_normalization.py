from django.test import SimpleTestCase

from documents.services.normalization import canonicalize_doc_type, normalize_doc_type
from documents.services.ranker import matches_document_type


class DocumentTypeNormalizationTests(SimpleTestCase):
    def test_canonicalize_known_document_types(self):
        cases = {
            "Quy trình": "quy_trinh",
            "quy-trinh": "quy_trinh",
            "Quy định": "quy_dinh",
            "Quy chế": "quy_che",
            "Công văn": "cong_van",
            "Thông tư": "thong_tu",
            "Nghị định": "nghi_dinh",
            "Báo cáo": "bao_cao",
        }

        for raw_value, expected in cases.items():
            with self.subTest(raw_value=raw_value):
                self.assertEqual(canonicalize_doc_type(raw_value), expected)

    def test_unknown_document_type_is_preserved_for_backward_compatibility(self):
        self.assertEqual(canonicalize_doc_type("huong_dan_noi_bo"), "huong_dan_noi_bo")

    def test_matches_document_type_accepts_label_or_code(self):
        self.assertEqual(normalize_doc_type("Quy chế"), "quy_che")
        self.assertTrue(matches_document_type("Quy chế", "quy_che"))
        self.assertTrue(matches_document_type("nghi_dinh", "Nghị định"))
        self.assertFalse(matches_document_type("Công văn", "Thông tư"))
