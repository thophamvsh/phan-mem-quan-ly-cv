import re
import unicodedata


def normalize_text(value):
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower()


def normalized_words(value):
    normalized = normalize_text(value)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split())


def has_phrase(normalized_text, phrase):
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", normalized_text))


def clean_display_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()
