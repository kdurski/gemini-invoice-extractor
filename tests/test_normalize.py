from __future__ import annotations

from invoice_extract_cli.normalize import (
    count_words,
    make_filename_stub,
    normalize_date,
    normalize_invoice_date,
    sanitize_short_description,
)


def test_normalize_date_handles_iso():
    assert normalize_date("2026-02-10") == "2026-02-10"


def test_normalize_date_handles_textual_format():
    assert normalize_date("10 Feb 2026") == "2026-02-10"


def test_normalize_invoice_date_prefers_iso():
    assert normalize_invoice_date("2026-02-10", "02/10/2026") == "2026-02-10"


def test_sanitize_short_description_enforces_word_limit_and_filename_safety():
    value = sanitize_short_description("Ultra-Wide Monitor Arm (Black Edition)!!!", max_words=5)
    assert value == "ultra wide monitor arm black"
    assert count_words(value) == 5


def test_make_filename_stub_uses_fallbacks():
    assert make_filename_stub(None, None) == "unknown-date_item"


def test_sanitize_short_description_transliterates_polish_chars():
    value = sanitize_short_description("Ładowarka USB-C do kawy? żart", max_words=5)
    assert value == "ladowarka usb c do kawy"
