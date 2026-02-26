# Invoice PDF CLI

CLI tool that reads a PDF invoice, extracts text (or falls back to page-image OCR via Gemini vision), and returns JSON with:

- invoice date
- short purchased-item description (5 words max)

## Requirements

- Python managed by `asdf`
- [`uv`](https://docs.astral.sh/uv/)
- `INVOICE_EXTRACT_GEMINI_API_KEY` environment variable

## Setup

```bash
asdf install
asdf exec uv sync --extra dev
export INVOICE_EXTRACT_GEMINI_API_KEY="your_api_key"
```

## Usage

```bash
asdf exec uv run invoice-extract /path/to/invoice.pdf --pretty
```

List available Gemini models (best-effort token limits; account quotas usually not exposed):

```bash
asdf exec uv run invoice-extract --list-models --pretty
```

Filter model list:

```bash
asdf exec uv run invoice-extract --list-models --model-filter flash --pretty
```

Include non-Gemini models too:

```bash
asdf exec uv run invoice-extract --list-models --all-models --pretty
```

## Configuration (`.ini` + ENV overrides)

The CLI will automatically read:

- `./invoice-extract.ini`
- then `./invoice-extract.local.ini` (local override, if present)

Or you can pass a custom file with `--config` (or `INVOICE_EXTRACT_CONFIG`), which bypasses the automatic pair.

Precedence:

- CLI flags
- `INVOICE_EXTRACT_*` environment variables
- `.ini` config file
- local `.ini` override (`invoice-extract.local.ini`, when using auto-discovery)
- built-in defaults

Supported env overrides:

- `INVOICE_EXTRACT_GEMINI_API_KEY`
- `INVOICE_EXTRACT_MODEL`
- `INVOICE_EXTRACT_LOCALE`
- `INVOICE_EXTRACT_MAX_PAGES`
- `INVOICE_EXTRACT_OCR_MODE`
- `INVOICE_EXTRACT_PRETTY`
- `INVOICE_EXTRACT_TIMEOUT_SECONDS`
- `INVOICE_EXTRACT_DEBUG`
- `INVOICE_EXTRACT_CONFIG`

Example:

```bash
export INVOICE_EXTRACT_MODEL=gemini-2.0-flash
export INVOICE_EXTRACT_LOCALE=pl
export INVOICE_EXTRACT_OCR_MODE=auto
export INVOICE_EXTRACT_PRETTY=true
asdf exec uv run invoice-extract /path/to/invoice.pdf
```

`locale` defaults to `pl`, so the tool asks Gemini to produce `short_description` in Polish whenever possible (for example `filtr`, `kawa`).

Example output:

```json
{
  "source_file": "invoice.pdf",
  "invoice_date": "2026-02-10",
  "invoice_date_raw": "10 Feb 2026",
  "short_description": "monitor arm",
  "short_description_words": 2,
  "filename_stub": "2026-02-10_monitor_arm",
  "extraction_method": "pdf_text",
  "confidence": 0.87,
  "warnings": []
}
```

## Notes

- `--ocr-mode auto` (default) tries embedded PDF text first, then falls back to Gemini vision.
- `--ocr-mode gemini` skips text extraction and uses Gemini vision directly.
- `--list-models` lists models from the Gemini API and prints token limits when available. Project/account quota usage is usually not available from this endpoint.
- v1 does not rename files; it returns a `filename_stub` for downstream scripts.
