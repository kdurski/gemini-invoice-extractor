from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import string


INVOICE_HINTS = (
    "invoice",
    "invoice date",
    "bill to",
    "total",
    "subtotal",
    "amount due",
    "due date",
    "tax",
)


class PdfIngestError(RuntimeError):
    pass


class PdfLibraryMissingError(PdfIngestError):
    pass


class PasswordProtectedPdfError(PdfIngestError):
    pass


@dataclass(frozen=True)
class PdfTextExtraction:
    page_texts: list[str]
    combined_text: str
    quality_score: float
    pages_examined: int


def validate_input_pdf_path(pdf_path: Path) -> Path:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if not pdf_path.is_file():
        raise IsADirectoryError(f"Path is not a file: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {pdf_path.name}")
    return pdf_path


def extract_embedded_text(pdf_path: Path, max_pages: int = 3) -> PdfTextExtraction:
    fitz = _import_fitz()
    max_pages = max(1, max_pages)
    try:
        with fitz.open(pdf_path) as doc:
            if getattr(doc, "needs_pass", False):
                raise PasswordProtectedPdfError(f"PDF is password-protected: {pdf_path}")

            page_texts: list[str] = []
            page_count = min(len(doc), max_pages)
            for index in range(page_count):
                page = doc[index]
                text = page.get_text("text") or ""
                page_texts.append(text)
    except PasswordProtectedPdfError:
        raise
    except Exception as exc:  # pragma: no cover - depends on PyMuPDF exception types
        raise PdfIngestError(f"Failed to read PDF '{pdf_path}': {exc}") from exc

    combined_text = "\n".join(t.strip() for t in page_texts if t.strip())
    return PdfTextExtraction(
        page_texts=page_texts,
        combined_text=combined_text,
        quality_score=score_text_quality(combined_text),
        pages_examined=len(page_texts),
    )


def render_pdf_pages_to_png_bytes(pdf_path: Path, max_pages: int = 3, dpi: int = 150) -> list[bytes]:
    fitz = _import_fitz()
    max_pages = max(1, max_pages)
    dpi = max(72, dpi)
    scale = dpi / 72.0

    rendered_pages: list[bytes] = []
    try:
        with fitz.open(pdf_path) as doc:
            if getattr(doc, "needs_pass", False):
                raise PasswordProtectedPdfError(f"PDF is password-protected: {pdf_path}")

            for index in range(min(len(doc), max_pages)):
                page = doc[index]
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                rendered_pages.append(pix.tobytes("png"))
    except PasswordProtectedPdfError:
        raise
    except Exception as exc:  # pragma: no cover - depends on PyMuPDF exception types
        raise PdfIngestError(f"Failed to render PDF '{pdf_path}': {exc}") from exc

    if not rendered_pages:
        raise PdfIngestError(f"PDF has no pages: {pdf_path}")

    return rendered_pages


def score_text_quality(text: str) -> float:
    if not text:
        return 0.0

    stripped = text.strip()
    if not stripped:
        return 0.0

    length_score = min(len(stripped) / 1500.0, 1.0)

    printable_chars = sum(1 for c in stripped if c in string.printable)
    printable_ratio = printable_chars / max(len(stripped), 1)

    lowered = stripped.lower()
    hints_found = sum(1 for hint in INVOICE_HINTS if hint in lowered)
    hint_score = min(hints_found / 4.0, 1.0)

    alpha_num_ratio = (
        sum(1 for c in stripped if c.isalnum()) / max(len(stripped), 1)
    )

    score = (
        (0.45 * length_score)
        + (0.20 * printable_ratio)
        + (0.25 * hint_score)
        + (0.10 * alpha_num_ratio)
    )
    return max(0.0, min(score, 1.0))


def looks_like_usable_text(quality_score: float, min_score: float = 0.45) -> bool:
    return quality_score >= min_score


def _import_fitz():
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise PdfLibraryMissingError(
            "PyMuPDF is not installed. Run: asdf exec uv sync --extra dev"
        ) from exc
    return fitz
