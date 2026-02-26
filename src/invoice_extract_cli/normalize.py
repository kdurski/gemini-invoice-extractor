from __future__ import annotations

import re
import unicodedata
from datetime import datetime

_COMMON_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d-%b-%Y",
    "%d-%B-%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%m-%d-%Y",
)

_POLISH_TRANSLITERATION = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "Ą": "A",
        "Ć": "C",
        "Ę": "E",
        "Ł": "L",
        "Ń": "N",
        "Ó": "O",
        "Ś": "S",
        "Ź": "Z",
        "Ż": "Z",
    }
)


def normalize_invoice_date(invoice_date_iso: str | None, invoice_date_raw: str | None) -> str | None:
    for candidate in (invoice_date_iso, invoice_date_raw):
        normalized = normalize_date(candidate)
        if normalized:
            return normalized
    return None


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None

    text = " ".join(value.strip().split())
    if not text:
        return None

    for fmt in _COMMON_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    # Prefer unambiguous slash/dash numeric parsing; default to MM/DD/YYYY for ambiguous forms.
    numeric_match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if numeric_match:
        first, second, year = (int(numeric_match.group(i)) for i in (1, 2, 3))
        if year < 100:
            year += 2000 if year < 70 else 1900
        if first > 12:
            month, day = second, first
        elif second > 12:
            month, day = first, second
        else:
            month, day = first, second
        try:
            return datetime(year=year, month=month, day=day).date().isoformat()
        except ValueError:
            return None

    embedded_match = re.search(
        r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Za-z]{3,9} \d{1,2}, \d{4}|\d{1,2} [A-Za-z]{3,9} \d{4})\b",
        text,
    )
    if embedded_match:
        return normalize_date(embedded_match.group(1))

    return None


def sanitize_short_description(value: str | None, max_words: int = 5) -> str:
    if not value:
        return "item"

    text = _ascii_fold(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w]
    if not words:
        return "item"
    return " ".join(words[:max_words])


def count_words(value: str | None) -> int:
    if not value:
        return 0
    return len([w for w in value.split() if w])


def make_filename_stub(invoice_date: str | None, short_description: str | None) -> str:
    date_part = invoice_date or "unknown-date"
    desc = sanitize_short_description(short_description)
    desc_part = desc.replace(" ", "_")
    return f"{date_part}_{desc_part}"


def _ascii_fold(value: str) -> str:
    # Preserve Polish letters during transliteration before generic accent stripping.
    translated = value.translate(_POLISH_TRANSLITERATION)
    normalized = unicodedata.normalize("NFKD", translated)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))
