from django.test import SimpleTestCase

from documents.services.chunking import chunk_markdown


class DocumentChunkingTests(SimpleTestCase):
    def test_chunk_markdown_extracts_heading_and_page_metadata(self):
        markdown = """
## Trang 3

# Quy chế vận hành hồ chứa

Nội dung áp dụng từ 1/9 đến 15/12.

## Trang 4

1. Phạm vi áp dụng

Áp dụng cho nhà máy Sông Hinh.
"""

        chunks = chunk_markdown(markdown)

        self.assertGreaterEqual(len(chunks), 1)
        target_chunk = next(
            chunk
            for chunk in chunks
            if "Quy chế vận hành hồ chứa" in chunk["heading_path"]
        )

        self.assertEqual(target_chunk["page_from"], 3)
        self.assertIn(
            ("1/9", "15/12"),
            {
                (item["start"], item["end"])
                for item in target_chunk["metadata"]["date_ranges"]
            },
        )
