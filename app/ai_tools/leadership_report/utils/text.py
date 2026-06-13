import unicodedata


def normalize_text(value):
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def normalize_title(value):
    normalized = unicodedata.normalize("NFD", str(value or "").replace("đ", "d").replace("Đ", "D"))
    without_marks = "".join(character for character in normalized if unicodedata.category(character) != "Mn")
    return " ".join(without_marks.casefold().split())
