# Invoice PDF CLI

CLI tool that reads a PDF invoice, extracts text (or falls back to page-image OCR via Gemini vision), and can print JSON diagnostics in debug mode with:

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
asdf exec uv run invoice-extract /path/to/invoice.pdf --debug
```

List available Gemini models (best-effort token limits; account quotas usually not exposed):

```bash
asdf exec uv run invoice-extract --list-models --debug
```

Filter model list:

```bash
asdf exec uv run invoice-extract --list-models --model-filter flash --debug
```

Include non-Gemini models too:

```bash
asdf exec uv run invoice-extract --list-models --all-models --debug
```

Dry-run rename preview:

```bash
asdf exec uv run invoice-extract /path/to/invoice.pdf --dry-run
```

Actual rename:

```bash
asdf exec uv run invoice-extract /path/to/invoice.pdf --rename
```

Example with your preferred style (`2026.02.09 ... (KD).pdf`):

```bash
asdf exec uv run invoice-extract /path/to/invoice.pdf \
  --rename \
  --filename-separator space \
  --filename-date-separator dot \
  --filename-suffix "(KD)"
```

## Configuration (`.ini` + ENV overrides)

The CLI will automatically read:

- `./invoice-extract.ini`
- then `./invoice-extract.local.ini` (local override, if present)

Or you can pass a custom file with `--config` (or `INVOICE_EXTRACT_CONFIG`), which bypasses the automatic pair.

Precedence:

- CLI flags
- `INVOICE_EXTRACT_*` environment variables
- `invoice-extract.local.ini` (auto-discovery mode only)
- `invoice-extract.ini` (auto-discovery mode only)
- built-in defaults

Supported env overrides:

- `INVOICE_EXTRACT_GEMINI_API_KEY`
- `INVOICE_EXTRACT_MODEL`
- `INVOICE_EXTRACT_LOCALE`
- `INVOICE_EXTRACT_MAX_PAGES`
- `INVOICE_EXTRACT_OCR_MODE`
- `INVOICE_EXTRACT_DRY_RUN`
- `INVOICE_EXTRACT_RENAME`
- `INVOICE_EXTRACT_FILENAME_SEPARATOR`
- `INVOICE_EXTRACT_FILENAME_SUFFIX`
- `INVOICE_EXTRACT_FILENAME_DATE_SEPARATOR`
- `INVOICE_EXTRACT_TIMEOUT_SECONDS`
- `INVOICE_EXTRACT_DEBUG`
- `INVOICE_EXTRACT_CONFIG`

Example:

```bash
export INVOICE_EXTRACT_MODEL=gemini-2.0-flash
export INVOICE_EXTRACT_LOCALE=pl
export INVOICE_EXTRACT_OCR_MODE=auto
export INVOICE_EXTRACT_FILENAME_SEPARATOR=space
export INVOICE_EXTRACT_FILENAME_DATE_SEPARATOR=dot
export INVOICE_EXTRACT_FILENAME_SUFFIX="(KD)"
export INVOICE_EXTRACT_DEBUG=true
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
- With no `--debug`, `--dry-run`, or `--rename`, the CLI prints a short summary and interactively asks whether to rename (default answer: `Y`).
- `--dry-run` prints `renaming "X" to "Y"` and does not modify files.
- `--rename` performs the actual rename to `<filename_stub>.pdf`.
- JSON output is printed only when `--debug` is enabled, and is always pretty-printed.
- `--filename-separator` controls separators between date/description/suffix.
- `--filename-date-separator` controls only date formatting in filename (`2026-02-09` vs `2026.02.09`).
- `--filename-suffix` appends suffix text (for example `(KD)`).
- `--list-models` lists models from the Gemini API and prints token limits when available. Project/account quota usage is usually not available from this endpoint.
