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
    return make_filename_stub_with_options(
        invoice_date=invoice_date,
        short_description=short_description,
    )


def make_filename_stub_with_options(
    invoice_date: str | None,
    short_description: str | None,
    *,
    filename_separator: str = "_",
    filename_suffix: str = "",
    filename_date_separator: str = "-",
) -> str:
    sep = normalize_filename_separator(filename_separator)
    date_sep = normalize_filename_date_separator(filename_date_separator)
    date_part = format_invoice_date_for_filename(invoice_date, date_separator=date_sep)

    desc = sanitize_short_description(short_description)
    desc_words = [w for w in desc.split() if w]
    desc_part = sep.join(desc_words) if desc_words else "item"

    base = f"{date_part}{sep}{desc_part}"
    suffix = sanitize_filename_suffix(filename_suffix)
    if suffix:
        if suffix.startswith(sep) or suffix.startswith(" "):
            return f"{base}{suffix}"
        return f"{base}{sep}{suffix}"
    return base


def format_invoice_date_for_filename(invoice_date: str | None, *, date_separator: str = "-") -> str:
    if not invoice_date:
        return "unknown-date"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", invoice_date):
        return invoice_date.replace("-", date_separator)
    return invoice_date


def normalize_filename_separator(value: str | None) -> str:
    if value is None:
        raw = "_"
    else:
        text = str(value)
        if text == " ":
            return " "
        raw = text.strip().lower()
    mapping = {
        "underscore": "_",
        "_": "_",
        "dash": "-",
        "hyphen": "-",
        "-": "-",
        "space": " ",
        " ": " ",
    }
    return mapping.get(raw, "_")


def normalize_filename_date_separator(value: str | None) -> str:
    raw = (value or "-").strip().lower()
    mapping = {
        "dash": "-",
        "hyphen": "-",
        "-": "-",
        "dot": ".",
        ".": ".",
        "underscore": "_",
        "_": "_",
    }
    return mapping.get(raw, "-")


def sanitize_filename_suffix(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if not cleaned:
        return ""
    # Keep user intent (e.g., "(KD)") but strip path separators/control chars.
    cleaned = cleaned.replace("/", "-").replace("\\", "-")
    cleaned = "".join(ch for ch in cleaned if ch >= " " and ch != "\x7f")
    return cleaned


def _ascii_fold(value: str) -> str:
    # Preserve Polish letters during transliteration before generic accent stripping.
    translated = value.translate(_POLISH_TRANSLITERATION)
    normalized = unicodedata.normalize("NFKD", translated)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))
