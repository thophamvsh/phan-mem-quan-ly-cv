from django.test import SimpleTestCase

from documents.services.query_parser import parse_query


class QueryParserTests(SimpleTestCase):
    def test_terms_are_deduplicated_and_common_words_are_removed(self):
        parsed = parse_query("Quy chế phối hợp các chủ hồ chứa quy chế")

        self.assertEqual(parsed["terms"].count("quy"), 1)
        self.assertNotIn("cac", parsed["terms"])
