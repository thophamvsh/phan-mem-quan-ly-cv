import re

from documents.services.normalization import (
    normalize_date_part,
    normalize_number,
    normalize_text,
)


STOPWORDS = {
    "anh",
    "ban",
    "cai",
    "cho",
    "cua",
    "duoc",
    "gi",
    "hoi",
    "khong",
    "la",
    "mot",
    "nao",
    "neu",
    "nhu",
    "noi",
    "the",
    "thi",
    "trong",
    "va",
    "ve",
}

DATE_RANGE_RE = re.compile(
    r"(\d{1,2})\s*/\s*(\d{1,2})\s*(?:den\s+ngay|den|toi\s+ngay|toi|-)\s*(\d{1,2})\s*/\s*(\d{1,2})"
)
ARTICLE_RE = re.compile(r"\b(?:dieu|article)\s+(\d+[a-z]?)\b")
SECTION_RE = re.compile(r"\b(?:muc|phan)\s+([ivx]+|\d+(?:\.\d+)*[a-z]?)\b")
NUMBER_RE = re.compile(r"\b\d+(?:[,.]\d+)?\s*(?:m|m3/s|m³/s|kwh|%)?\b")


def generate_date_variants(date_str):
    """
    Given a date string like '1/9', generate variants like:
    ['1/9', '01/09', '01/9', '1/09']
    """
    if not date_str or "/" not in date_str:
        return [date_str] if date_str else []
    try:
        parts = date_str.split("/")
        if len(parts) == 2:
            d_val = int(parts[0])
            m_val = int(parts[1])
            variants = {
                f"{d_val}/{m_val}",
                f"{d_val:02d}/{m_val:02d}",
                f"{d_val:02d}/{m_val}",
                f"{d_val}/{m_val:02d}",
            }
            return list(variants)
    except Exception:
        pass
    return [date_str]


def extract_date_ranges(text):
    normalized = normalize_text(text)
    ranges = []
    for match in DATE_RANGE_RE.finditer(normalized):
        ranges.append(
            {
                "start": normalize_date_part(match.group(1), match.group(2)),
                "end": normalize_date_part(match.group(3), match.group(4)),
                "text": match.group(0),
                "position": match.start(),
            }
        )
    return ranges


def extract_article_refs(text):
    normalized = normalize_text(text)
    return [f"dieu {match.group(1)}" for match in ARTICLE_RE.finditer(normalized)]


def extract_section_refs(text):
    normalized = normalize_text(text)
    return [match.group(1) for match in SECTION_RE.finditer(normalized)]


def extract_numbers(text):
    return sorted(
        {
            normalize_number(match.group(0))
            for match in NUMBER_RE.finditer(str(text or ""))
            if normalize_number(match.group(0))
        }
    )


def extract_terms(text):
    normalized = normalize_text(text)
    return [
        term
        for term in re.findall(r"[a-z0-9]+", normalized)
        if len(term) >= 3 and term not in STOPWORDS
    ]


def detect_factory(text):
    from documents.models import Document

    normalized = normalize_text(text)
    if any(term in normalized for term in ("song hinh", "songhinh", "songinh")):
        return Document.FACTORY_SONGHINH
    if any(term in normalized for term in ("vinh son", "vinhson")):
        return Document.FACTORY_VINHSON
    if any(term in normalized for term in ("thuong kon tum", "thuongkontum", "kontum", "tkt")):
        return Document.FACTORY_THUONGKONTUM
    return ""


def extract_phrases(text):
    normalized = normalize_text(text)
    phrases = []
    for phrase in (
        "quy dinh nhiem vu trong mua lu",
        "nhiem vu trong mua lu",
        "quy dinh nhiem vu trong mua can",
        "nhiem vu trong mua can",
        "nguyen tac van hanh",
        "thoi tiet binh thuong",
        "thoi tiet mua lu",
    ):
        if phrase in normalized:
            phrases.append(phrase)
    return phrases


def parse_query(query):
    normalized = normalize_text(query)
    return {
        "raw": query or "",
        "normalized": normalized,
        "terms": extract_terms(query),
        "phrases": extract_phrases(query),
        "date_ranges": extract_date_ranges(query),
        "article_refs": extract_article_refs(query),
        "section_refs": extract_section_refs(query),
        "numbers": extract_numbers(query),
        "factory": detect_factory(query),
    }
