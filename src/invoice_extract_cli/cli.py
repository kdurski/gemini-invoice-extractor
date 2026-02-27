from __future__ import annotations

import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import typer

from .config import ConfigError, resolve_cli_settings
from .gemini_client import GeminiClientError, GeminiInvoiceExtractor
from .models import ExtractionResult
from .normalize import count_words, make_filename_stub_with_options, normalize_invoice_date, sanitize_short_description
from .pdf_ingest import (
    PasswordProtectedPdfError,
    PdfIngestError,
    extract_embedded_text,
    looks_like_usable_text,
    render_pdf_pages_to_png_bytes,
    validate_input_pdf_path,
)

class OcrMode(str, Enum):
    AUTO = "auto"
    GEMINI = "gemini"


EXIT_BAD_INPUT = 2
EXIT_PDF_ERROR = 3
EXIT_API_ERROR = 4
EXIT_INTERNAL = 10


def invoice_extract_command(
    pdf_path: Optional[Path] = typer.Argument(None, exists=False, help="Path to the invoice PDF"),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Path to INI config file (default: auto-discover invoice-extract.ini + invoice-extract.local.ini)",
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Gemini model name"),
    locale: Optional[str] = typer.Option(
        None,
        "--locale",
        help="Preferred language for short description (default: pl)",
    ),
    list_models: bool = typer.Option(
        False,
        "--list-models",
        help="List available Gemini models and token limits (if exposed by API), then exit",
    ),
    all_models: bool = typer.Option(
        False,
        "--all-models",
        help="Include non-Gemini models when using --list-models",
    ),
    model_filter: Optional[str] = typer.Option(
        None,
        "--model-filter",
        help="Filter model names/display names when using --list-models",
    ),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", min=1, help="Maximum number of pages to inspect"),
    ocr_mode: Optional[OcrMode] = typer.Option(None, "--ocr-mode", case_sensitive=False),
    dry_run: Optional[bool] = typer.Option(
        None,
        "--dry-run/--no-dry-run",
        help='Print "renaming X to Y" without renaming the file',
    ),
    rename: Optional[bool] = typer.Option(
        None,
        "--rename/--no-rename",
        help="Perform actual file rename to the generated filename",
    ),
    filename_separator: Optional[str] = typer.Option(
        None,
        "--filename-separator",
        help="Filename separator: underscore|dash|space (or _, -, space)",
    ),
    filename_suffix: Optional[str] = typer.Option(
        None,
        "--filename-suffix",
        help='Optional filename suffix, e.g. "(KD)"',
    ),
    filename_date_separator: Optional[str] = typer.Option(
        None,
        "--filename-date-separator",
        help="Date separator in filename: dash|dot|underscore (or -, ., _)",
    ),
    timeout_seconds: Optional[int] = typer.Option(
        None,
        "--timeout-seconds",
        min=1,
        help="Gemini timeout in seconds",
    ),
    debug: Optional[bool] = typer.Option(None, "--debug/--no-debug", help="Emit diagnostics to stderr"),
) -> None:
    try:
        settings = resolve_cli_settings(
            config_path_override=config,
            model=model,
            locale=locale,
            max_pages=max_pages,
            ocr_mode=ocr_mode.value if ocr_mode is not None else None,
            dry_run=dry_run,
            rename=rename,
            filename_separator=filename_separator,
            filename_suffix=filename_suffix,
            filename_date_separator=filename_date_separator,
            timeout_seconds=timeout_seconds,
            debug=debug,
        )
        if settings.config_path:
            _debug(settings.debug, f"Loaded config from {settings.config_path}")

        if list_models:
            output = run_list_models(
                api_key=settings.gemini_api_key,
                model=settings.model,
                timeout_seconds=settings.timeout_seconds,
                locale=settings.locale,
                only_gemini=not all_models,
                name_contains=model_filter,
                debug=settings.debug,
            )
            if settings.debug:
                typer.echo(json.dumps(output, indent=2, ensure_ascii=True))
            return

        if pdf_path is None:
            raise ValueError("Missing PDF path. Provide <pdf_path> or use --list-models.")
        if settings.dry_run and settings.rename:
            raise ValueError("Options --dry-run and --rename are mutually exclusive.")

        source_path = pdf_path.resolve()
        result = run_invoice_extraction(
            pdf_path=pdf_path,
            api_key=settings.gemini_api_key,
            model=settings.model,
            locale=settings.locale,
            max_pages=settings.max_pages,
            ocr_mode=OcrMode(settings.ocr_mode),
            filename_separator=settings.filename_separator,
            filename_suffix=settings.filename_suffix,
            filename_date_separator=settings.filename_date_separator,
            timeout_seconds=settings.timeout_seconds,
            debug=settings.debug,
        )

        target_path = build_renamed_path(source_path, result.filename_stub)
        if settings.dry_run:
            typer.echo(format_rename_message(source_path, target_path))
        elif settings.rename:
            perform_rename(source_path, target_path)
        elif not settings.debug:
            for line in format_detection_summary(result, source_path, target_path):
                typer.echo(line)
            if can_prompt_for_confirmation():
                should_rename = typer.confirm(
                    f'Rename "{source_path.name}" to "{target_path.name}"?',
                    default=True,
                )
                if should_rename:
                    perform_rename(source_path, target_path)
                else:
                    typer.echo("Skipped rename.")
            else:
                typer.echo('Non-interactive mode detected. Use "--rename" to apply rename.')
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        _emit_error(str(exc), EXIT_BAD_INPUT)
    except FileExistsError as exc:
        _emit_error(str(exc), EXIT_BAD_INPUT)
    except ConfigError as exc:
        _emit_error(str(exc), EXIT_BAD_INPUT)
    except (PasswordProtectedPdfError, PdfIngestError) as exc:
        _emit_error(str(exc), EXIT_PDF_ERROR)
    except GeminiClientError as exc:
        _emit_error(str(exc), EXIT_API_ERROR)
    except Exception as exc:  # pragma: no cover - safety net
        _emit_error(f"Unexpected error: {exc}", EXIT_INTERNAL)

    output = result.model_dump()
    if settings.debug:
        typer.echo(json.dumps(output, indent=2, ensure_ascii=True))


def run_invoice_extraction(
    pdf_path: Path,
    api_key: str | None,
    model: str,
    locale: str,
    max_pages: int,
    ocr_mode: OcrMode,
    filename_separator: str,
    filename_suffix: str,
    filename_date_separator: str,
    timeout_seconds: int,
    debug: bool = False,
) -> ExtractionResult:
    validated_path = validate_input_pdf_path(pdf_path)

    _debug(
        debug,
        (
            f"Using model={model}, locale={locale}, max_pages={max_pages}, ocr_mode={ocr_mode.value}, "
            f"filename_separator={filename_separator!r}, filename_suffix={filename_suffix!r}, "
            f"filename_date_separator={filename_date_separator!r}"
        ),
    )

    extractor = GeminiInvoiceExtractor(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        locale=locale,
    )

    warnings: list[str] = []
    extraction_method = "gemini_vision"
    invoice_date_raw: str | None = None

    if ocr_mode == OcrMode.AUTO:
        text_extraction = extract_embedded_text(validated_path, max_pages=max_pages)
        _debug(
            debug,
            f"Embedded text pages={text_extraction.pages_examined} quality={text_extraction.quality_score:.2f}",
        )

        if text_extraction.combined_text and looks_like_usable_text(text_extraction.quality_score):
            extraction_method = "pdf_text"
            gemini_response = extractor.extract_from_text(text_extraction.combined_text)
        else:
            warnings.append(
                f"Falling back to Gemini vision due to low text quality ({text_extraction.quality_score:.2f})"
            )
            images = render_pdf_pages_to_png_bytes(validated_path, max_pages=max_pages)
            _debug(debug, f"Rendered {len(images)} page image(s) for Gemini vision fallback")
            gemini_response = extractor.extract_from_images(images)
    else:
        images = render_pdf_pages_to_png_bytes(validated_path, max_pages=max_pages)
        _debug(debug, f"Rendered {len(images)} page image(s) for Gemini vision mode")
        gemini_response = extractor.extract_from_images(images)

    invoice_date_raw = gemini_response.invoice_date_raw
    invoice_date = normalize_invoice_date(gemini_response.invoice_date_iso, gemini_response.invoice_date_raw)

    if (gemini_response.invoice_date_iso or gemini_response.invoice_date_raw) and not invoice_date:
        warnings.append("Could not normalize invoice date returned by Gemini")

    short_description = sanitize_short_description(gemini_response.short_description, max_words=5)
    if count_words(short_description) == 0:
        short_description = "item"
        warnings.append("Gemini returned an empty short description; defaulted to 'item'")

    if gemini_response.notes:
        warnings.append(gemini_response.notes)

    filename_stub = make_filename_stub_with_options(
        invoice_date,
        short_description,
        filename_separator=filename_separator,
        filename_suffix=filename_suffix,
        filename_date_separator=filename_date_separator,
    )

    result = ExtractionResult(
        source_file=validated_path.name,
        invoice_date=invoice_date,
        invoice_date_raw=invoice_date_raw,
        short_description=short_description,
        short_description_words=count_words(short_description),
        filename_stub=filename_stub,
        extraction_method=extraction_method,
        confidence=max(0.0, min(float(gemini_response.confidence), 1.0)),
        warnings=warnings,
    )
    return result


def run_list_models(
    *,
    api_key: str | None,
    model: str,
    locale: str,
    timeout_seconds: int,
    only_gemini: bool = True,
    name_contains: str | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    _debug(
        debug,
        f"Listing Gemini models (only_gemini={only_gemini}, model_filter={name_contains or ''})",
    )
    extractor = GeminiInvoiceExtractor(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        locale=locale,
    )
    return extractor.list_models(only_gemini=only_gemini, name_contains=name_contains)


def build_renamed_path(source_path: Path, filename_stub: str) -> Path:
    return source_path.with_name(f"{filename_stub}{source_path.suffix}")


def format_rename_message(source_path: Path, target_path: Path) -> str:
    return f'renaming "{source_path.name}" to "{target_path.name}"'


def perform_rename(source_path: Path, target_path: Path) -> None:
    if source_path == target_path:
        typer.echo(f'File already has target name: "{source_path.name}"')
        return
    if target_path.exists():
        raise FileExistsError(
            f'Cannot rename "{source_path.name}" to "{target_path.name}" because destination already exists.'
        )
    source_path.rename(target_path)
    typer.echo(f'Renamed "{source_path.name}" to "{target_path.name}"')


def format_detection_summary(result: ExtractionResult, source_path: Path, target_path: Path) -> list[str]:
    date_text = result.invoice_date or "unknown"
    lines = [
        f'Found invoice date: "{date_text}"',
        f'Found item description: "{result.short_description}"',
        f'Suggested filename: "{target_path.name}"',
    ]
    if result.warnings:
        lines.append(f'Warnings: {" | ".join(result.warnings)}')
    return lines


def can_prompt_for_confirmation() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _debug(enabled: bool, message: str) -> None:
    if enabled:
        typer.echo(f"[debug] {message}", err=True)


def _emit_error(message: str, code: int) -> None:
    payload: dict[str, Any] = {"error": message, "exit_code": code}
    typer.echo(json.dumps(payload, ensure_ascii=True), err=True)
    raise typer.Exit(code=code)


def main() -> None:
    typer.run(invoice_extract_command)


if __name__ == "__main__":
    main()
