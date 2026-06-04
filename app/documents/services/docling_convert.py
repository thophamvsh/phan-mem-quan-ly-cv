import re
from collections import Counter
from pathlib import Path


TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".csv", ".log"}
UNSUPPORTED_EXTENSIONS = {".doc"}
PDF_EXTENSIONS = {".pdf"}
MIN_EXTRACTED_TEXT_CHARS = 300


def convert_file_to_markdown(file_path):
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in UNSUPPORTED_EXTENSIONS:
        raise ValueError("File .doc cu khong duoc Docling ho tro truc tiep. Hay chuyen file sang .docx hoac .pdf roi upload lai.")
    if suffix in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8", errors="replace")

    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        if suffix in PDF_EXTENSIONS:
            return _extract_pdf_text_or_ocr(path)
        return _fallback_text(path)

    try:
        result = DocumentConverter().convert(str(path))
    except Exception as exc:
        if suffix in PDF_EXTENSIONS:
            try:
                return _extract_pdf_text_or_ocr(path)
            except Exception:
                pass
        raise ValueError(f"Khong the chuyen doi file bang Docling: {exc}") from exc
    document = getattr(result, "document", None)
    if document and hasattr(document, "export_to_markdown"):
        markdown = document.export_to_markdown()
        if suffix in PDF_EXTENSIONS and _is_text_too_short(markdown):
            return _extract_pdf_text_or_ocr(path)
        return markdown
    return _fallback_text(path)


def _extract_pdf_text_or_ocr(path):
    try:
        markdown = _extract_pdf_text(path)
        if not _is_text_too_short(markdown):
            return markdown
    except Exception:
        pass
    return _ocr_pdf(path)


def _extract_pdf_text(path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("Backend chua cai pypdf de fallback doc PDF khi Docling khong xu ly duoc.") from exc

    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"## Trang {index}\n\n{text.strip()}")
    if not pages:
        raise ValueError("Khong trich xuat duoc text tu PDF. File co the la scan/anh hoac bi khoa.")
    return f"# {path.name}\n\n" + "\n\n".join(pages)


def _ocr_pdf(path):
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise ValueError("Backend chua cai pytesseract/pdf2image de OCR PDF scan.") from exc

    try:
        images = convert_from_path(str(path), dpi=250)
    except Exception as exc:
        raise ValueError("Khong the chuyen PDF scan thanh anh. Kiem tra goi poppler-utils trong Docker image.") from exc

    pages = []
    for index, image in enumerate(images, start=1):
        text = pytesseract.image_to_string(image, lang="vie+eng", config="--psm 6") or ""
        if text.strip():
            pages.append(f"## Trang {index}\n\n{text.strip()}")

    if not pages:
        raise ValueError("OCR khong trich xuat duoc text tu PDF scan. File co the qua mo, nghieng, chat luong anh thap hoac bi khoa.")
    return f"# {path.name}\n\n" + "\n\n".join(pages)


def _is_text_too_short(text):
    meaningful_text = _meaningful_text_for_length(text)
    compact = "".join(ch for ch in meaningful_text if not ch.isspace())
    return len(compact) < MIN_EXTRACTED_TEXT_CHARS


def _meaningful_text_for_length(text):
    lines = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# ") and line.lower().endswith(".pdf"):
            continue
        if re.match(r"^#{1,6}\s*Trang\s+\d+\s*$", line, re.IGNORECASE):
            continue
        if re.match(r"^Trang\s+\d+\s*$", line, re.IGNORECASE):
            continue
        if re.match(r"^[\w.-]+\([^)]*\)\s*-\s*\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}$", line):
            continue
        lines.append(line)

    counts = Counter(lines)
    meaningful_lines = [
        line
        for line in lines
        if not (counts[line] >= 3 and len(line) < 160)
    ]
    return "\n".join(meaningful_lines)


def _fallback_text(path):
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace").strip()
    if text:
        return text
    return f"# {path.name}\n\nKhong the chuyen doi noi dung file nay. Hay cai docling de xu ly dinh dang nay."
