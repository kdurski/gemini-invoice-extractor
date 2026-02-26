from __future__ import annotations

from invoice_extract_cli.pdf_ingest import looks_like_usable_text, score_text_quality


def test_score_text_quality_is_low_for_empty_text():
    assert score_text_quality("") == 0.0


def test_score_text_quality_detects_invoice_like_text():
    text = """
    Invoice
    Invoice Date: 2026-02-10
    Bill To: Example LLC
    Subtotal: 120.00
    Tax: 12.00
    Total: 132.00
    """
    score = score_text_quality(text)
    assert 0.0 <= score <= 1.0
    assert looks_like_usable_text(score)
