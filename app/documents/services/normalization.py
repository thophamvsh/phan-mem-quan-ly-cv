import re
import unicodedata


DOCUMENT_TYPE_CHOICES = (
    ("quy_trinh", "Quy trình"),
    ("quy_dinh", "Quy định"),
    ("quy_che", "Quy chế"),
    ("cong_van", "Công văn"),
    ("thong_tu", "Thông tư"),
    ("nghi_dinh", "Nghị định"),
    ("bao_cao", "Báo cáo"),
)

DOCUMENT_TYPE_ALIASES = {
    "quy trinh": "quy_trinh",
    "quy dinh": "quy_dinh",
    "quy che": "quy_che",
    "cong van": "cong_van",
    "thong tu": "thong_tu",
    "nghi dinh": "nghi_dinh",
    "bao cao": "bao_cao",
}


VIETNAMESE_MOJIBAKE_REPLACEMENTS = (
    ("Ä‘", "d"),
    ("Ã„â€˜", "d"),
)


def normalize_text(value):
    text = str(value or "").lower()
    for source, target in VIETNAMESE_MOJIBAKE_REPLACEMENTS:
        text = text.replace(source, target)
    text = text.replace("đ", "d")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`~]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_doc_type(value):
    text = normalize_text(value).replace("_", " ").replace("-", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return DOCUMENT_TYPE_ALIASES.get(text, text)


def canonicalize_doc_type(value):
    normalized = normalize_doc_type(value)
    if normalized in dict(DOCUMENT_TYPE_CHOICES):
        return normalized
    return str(value or "").strip()


def normalize_date_part(day, month):
    return f"{int(day)}/{int(month)}"


def normalize_number(value):
    text = normalize_text(value)
    text = text.replace(",", ".")
    return re.sub(r"\s+", "", text)
