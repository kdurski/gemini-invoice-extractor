from __future__ import annotations

from pathlib import Path

import pytest

from invoice_extract_cli.pdf_ingest import validate_input_pdf_path


def test_validate_input_pdf_path_rejects_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_input_pdf_path(tmp_path / "missing.pdf")


def test_validate_input_pdf_path_rejects_non_pdf(tmp_path: Path):
    path = tmp_path / "invoice.txt"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_input_pdf_path(path)


def test_validate_input_pdf_path_accepts_pdf(tmp_path: Path):
    path = tmp_path / "invoice.pdf"
    path.write_bytes(b"%PDF-1.4")
    assert validate_input_pdf_path(path) == path
