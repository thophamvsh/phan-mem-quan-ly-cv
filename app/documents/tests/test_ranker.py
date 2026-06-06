from types import SimpleNamespace

from django.test import SimpleTestCase

from documents.services.query_parser import parse_query
from documents.services.ranker import score_chunk


class DocumentRankerTests(SimpleTestCase):
    def test_keyword_score_matches_unaccented_query_across_punctuation(self):
        chunk = SimpleNamespace(
            heading_path="5. Chi phí tiếp khách, hội nghị",
            content="5. Chi phí tiếp khách, hội nghị.",
            metadata={},
        )

        scores = score_chunk(parse_query("chi phi tiep khach hoi nghi"), chunk, semantic_score=0.36)

        self.assertGreaterEqual(scores["score"], 0.30)
        self.assertGreaterEqual(scores["keyword_score"], 0.60)

    def test_document_title_boosts_matching_content_chunk_over_title_only_chunk(self):
        document = SimpleNamespace(title="Quy chế phối hợp các chủ hồ chứa 2026(4MB).PDF")
        parsed_query = parse_query(
            "Quy chế phối hợp các chủ hồ chứa 2026 quy định mùa lũ từ ngày nào?"
        )
        title_only_chunk = SimpleNamespace(
            document=document,
            heading_path="Quy chế phối hợp các chủ hồ chứa 2026",
            content="# Quy_chế_phối_hợp_các_chủ_hồ_chứa_20264MB.PDF",
            metadata={},
        )
        content_chunk = SimpleNamespace(
            document=document,
            heading_path="Trang 9",
            content=(
                "Chương II QUY CHẾ PHỐI HỢP VẬN HÀNH GIỮA CÁC HỒ. "
                "Điều 1: Mùa lũ. Mùa lũ được quy định từ ngày 01 tháng 9 "
                "đến ngày 15 tháng 12 hằng năm."
            ),
            metadata={},
        )

        title_scores = score_chunk(parsed_query, title_only_chunk, semantic_score=0.50)
        content_scores = score_chunk(parsed_query, content_chunk, semantic_score=0.42)

        self.assertGreaterEqual(content_scores["score"], 0.30)
        self.assertGreater(content_scores["score"], title_scores["score"])
