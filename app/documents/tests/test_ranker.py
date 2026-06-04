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
