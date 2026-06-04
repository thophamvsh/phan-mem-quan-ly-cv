import re
import unicodedata


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
    return normalize_text(value).replace("_", " ").strip()


def normalize_date_part(day, month):
    return f"{int(day)}/{int(month)}"


def normalize_number(value):
    text = normalize_text(value)
    text = text.replace(",", ".")
    return re.sub(r"\s+", "", text)
