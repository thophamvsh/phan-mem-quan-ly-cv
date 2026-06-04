from django.test import SimpleTestCase

from documents.services.docling_convert import _is_text_too_short


class DoclingConvertTests(SimpleTestCase):
    def test_page_markers_and_repeated_watermark_are_not_meaningful_text(self):
        markdown = """# cvdi_547-QD_sua_doi_bo_sung.pdf

## Trang 1

thoph(Pham Hoang Tho) - 04/06/2026 16:44:22
thoph(Pham Hoang Tho) - 04/06/2026 16:44:22
thoph(Pham Hoang Tho) - 04/06/2026 16:44:22

## Trang 2

thoph(Pham Hoang Tho) - 04/06/2026 16:44:22
thoph(Pham Hoang Tho) - 04/06/2026 16:44:22
thoph(Pham Hoang Tho) - 04/06/2026 16:44:22
"""

        self.assertTrue(_is_text_too_short(markdown))

    def test_real_body_text_is_meaningful(self):
        body = " ".join(
            [
                "Quyet dinh ban hanh phu luc quy che quan ly tai chinh va chi tieu noi bo.",
                "Noi dung quy dinh ve chi phi tiep khach, hoi nghi, cong tac phi.",
                "Cac khoan chi khac phuc vu hoat dong san xuat kinh doanh cua cong ty.",
                "Quy dinh nay ap dung cho cac don vi khi lap de nghi thanh toan.",
                "Ho so phai kem chung tu hop le va duoc cap co tham quyen phe duyet.",
                "Phong tai chinh ke toan chiu trach nhiem kiem tra va huong dan thuc hien.",
            ]
        )
        markdown = f"# van-ban.pdf\n\n## Trang 1\n\n{body}"

        self.assertFalse(_is_text_too_short(markdown))
