"""
Date parsing and normalization utilities
"""

from datetime import date
from typing import Optional


def parse_dmy_to_date(value: str) -> Optional[date]:
    """
    Parse 'DD/MM/YYYY' or 'D/M/YYYY' (and similar) to date.
    Returns None if invalid/empty.
    """
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        parts = s.split("/")
        if len(parts) != 3:
            return None
        d, m, y = (int(parts[0]), int(parts[1]), int(parts[2]))
        return date(y, m, d)
    except Exception:
        return None


def normalize_date(date_str) -> Optional[date]:
    """
    Parse date and return as date object, handling various formats
    Supports: DD/MM/YYYY, YYYY-MM-DD
    """
    if not date_str:
        return None
    try:
        parts = str(date_str).strip().split('/')
        if len(parts) == 3:
            day, month, year = parts
            return date(int(year), int(month), int(day))
    except (ValueError, AttributeError):
        pass

    # Try YYYY-MM-DD format
    if '-' in str(date_str):
        try:
            from datetime import datetime
            return datetime.strptime(str(date_str).strip(), '%Y-%m-%d').date()
        except (ValueError, AttributeError):
            pass
    return None


def parse_date(date_str: str) -> Optional[object]:
    """
    Parse date từ nhiều format (returns datetime, not date)
    Supports: DD/MM/YYYY, YYYY-MM-DD
    Handles 2-digit years (assumes 2000+ if < 50, else 1900+)
    """
    from datetime import datetime
    if not date_str:
        return None
    date_str = str(date_str).strip()

    # Format DD/MM/YYYY
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            try:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if year < 100:
                    year = 2000 + year if year < 50 else 1900 + year
                return datetime(year, month, day)
            except (ValueError, TypeError):
                pass

    # Format YYYY-MM-DD
    if "-" in date_str:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            pass

    return None
