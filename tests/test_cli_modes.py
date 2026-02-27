from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pydantic")

from invoice_extract_cli.cli import (
    build_renamed_path,
    format_detection_summary,
    format_rename_message,
    perform_rename,
)
from invoice_extract_cli.models import ExtractionResult


def test_build_renamed_path_preserves_extension():
    source = Path("/tmp/invoice.pdf")
    target = build_renamed_path(source, "2026-02-10_kawa")
    assert target.name == "2026-02-10_kawa.pdf"


def test_format_rename_message():
    source = Path("/tmp/a.pdf")
    target = Path("/tmp/b.pdf")
    assert format_rename_message(source, target) == 'renaming "a.pdf" to "b.pdf"'


def test_format_detection_summary_includes_core_fields():
    source = Path("/tmp/source.pdf")
    target = Path("/tmp/2026-02-10_kawa.pdf")
    result = ExtractionResult(
        source_file="source.pdf",
        invoice_date="2026-02-10",
        invoice_date_raw="10 Feb 2026",
        short_description="kawa",
        short_description_words=1,
        filename_stub="2026-02-10_kawa",
        extraction_method="pdf_text",
        confidence=0.9,
        warnings=["ambiguous date candidate"],
    )
    lines = format_detection_summary(result, source, target)
    assert 'Found invoice date: "2026-02-10"' in lines
    assert 'Found item description: "kawa"' in lines
    assert 'Suggested filename: "2026-02-10_kawa.pdf"' in lines
    assert any(line.startswith("Warnings: ") for line in lines)


def test_perform_rename_moves_file(tmp_path: Path):
    source = tmp_path / "a.pdf"
    target = tmp_path / "b.pdf"
    source.write_bytes(b"%PDF-1.4")
    perform_rename(source, target)
    assert not source.exists()
    assert target.exists()
