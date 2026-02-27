from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


CONFIG_SECTION = "invoice_extract"
DEFAULT_CONFIG_FILENAME = "invoice-extract.ini"
LOCAL_CONFIG_FILENAME = "invoice-extract.local.ini"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedCliSettings:
    config_path: Path | None
    gemini_api_key: str | None
    model: str
    locale: str
    max_pages: int
    ocr_mode: str
    dry_run: bool
    rename: bool
    filename_separator: str
    filename_suffix: str
    filename_date_separator: str
    timeout_seconds: int
    debug: bool


def resolve_cli_settings(
    *,
    config_path_override: Path | None = None,
    model: str | None = None,
    locale: str | None = None,
    max_pages: int | None = None,
    ocr_mode: str | None = None,
    dry_run: bool | None = None,
    rename: bool | None = None,
    filename_separator: str | None = None,
    filename_suffix: str | None = None,
    filename_date_separator: str | None = None,
    timeout_seconds: int | None = None,
    debug: bool | None = None,
) -> ResolvedCliSettings:
    config_paths = _resolve_config_paths(config_path_override)
    file_values = _read_config_files(config_paths)

    defaults: dict[str, object] = {
        "gemini_api_key": None,
        "model": "gemini-2.0-flash",
        "locale": "pl",
        "max_pages": 3,
        "ocr_mode": "auto",
        "dry_run": False,
        "rename": False,
        "filename_separator": "_",
        "filename_suffix": "",
        "filename_date_separator": "-",
        "timeout_seconds": 30,
        "debug": False,
    }

    merged: dict[str, object] = defaults.copy()
    merged.update(file_values)
    merged.update(_env_overrides())

    cli_overrides: dict[str, object] = {}
    if model is not None:
        cli_overrides["model"] = model
    if locale is not None:
        cli_overrides["locale"] = locale
    if max_pages is not None:
        cli_overrides["max_pages"] = max_pages
    if ocr_mode is not None:
        cli_overrides["ocr_mode"] = ocr_mode
    if dry_run is not None:
        cli_overrides["dry_run"] = dry_run
    if rename is not None:
        cli_overrides["rename"] = rename
    if filename_separator is not None:
        cli_overrides["filename_separator"] = filename_separator
    if filename_suffix is not None:
        cli_overrides["filename_suffix"] = filename_suffix
    if filename_date_separator is not None:
        cli_overrides["filename_date_separator"] = filename_date_separator
    if timeout_seconds is not None:
        cli_overrides["timeout_seconds"] = timeout_seconds
    if debug is not None:
        cli_overrides["debug"] = debug
    merged.update(cli_overrides)

    normalized = _validate_and_normalize(merged)
    effective_config_path = config_paths[-1] if config_paths else None
    return ResolvedCliSettings(config_path=effective_config_path, **normalized)


def _resolve_config_paths(config_path_override: Path | None) -> list[Path]:
    if config_path_override is not None:
        return [config_path_override]

    env_path = os.getenv("INVOICE_EXTRACT_CONFIG")
    if env_path:
        return [Path(env_path)]

    config_paths: list[Path] = []
    default_path = Path.cwd() / DEFAULT_CONFIG_FILENAME
    local_path = Path.cwd() / LOCAL_CONFIG_FILENAME
    if default_path.exists():
        config_paths.append(default_path)
    if local_path.exists():
        config_paths.append(local_path)
    return config_paths


def _read_config_files(config_paths: list[Path]) -> dict[str, object]:
    if not config_paths:
        return {}

    parser = configparser.ConfigParser()
    for config_path in config_paths:
        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")
        if not config_path.is_file():
            raise ConfigError(f"Config path is not a file: {config_path}")

        try:
            read_files = parser.read(config_path, encoding="utf-8")
        except configparser.Error as exc:
            raise ConfigError(f"Failed to parse config file '{config_path}': {exc}") from exc

        if not read_files:
            raise ConfigError(f"Failed to read config file: {config_path}")

    if not parser.has_section(CONFIG_SECTION):
        return {}

    section = parser[CONFIG_SECTION]
    values: dict[str, object] = {}

    if "gemini_api_key" in section:
        api_key = section.get("gemini_api_key", fallback="").strip()
        values["gemini_api_key"] = api_key or None
    if "model" in section:
        values["model"] = section.get("model", fallback="").strip()
    if "locale" in section:
        values["locale"] = section.get("locale", fallback="").strip()
    if "max_pages" in section:
        values["max_pages"] = _parse_int(section.get("max_pages", fallback=""), "max_pages")
    if "ocr_mode" in section:
        values["ocr_mode"] = section.get("ocr_mode", fallback="").strip()
    if "dry_run" in section:
        values["dry_run"] = _parse_bool(section.get("dry_run", fallback=""), "dry_run")
    if "rename" in section:
        values["rename"] = _parse_bool(section.get("rename", fallback=""), "rename")
    if "filename_separator" in section:
        values["filename_separator"] = section.get("filename_separator", fallback="").strip()
    if "filename_suffix" in section:
        values["filename_suffix"] = section.get("filename_suffix", fallback="")
    if "filename_date_separator" in section:
        values["filename_date_separator"] = section.get("filename_date_separator", fallback="").strip()
    if "timeout_seconds" in section:
        values["timeout_seconds"] = _parse_int(section.get("timeout_seconds", fallback=""), "timeout_seconds")
    if "debug" in section:
        values["debug"] = _parse_bool(section.get("debug", fallback=""), "debug")

    return values


def _env_overrides() -> dict[str, object]:
    env = os.environ
    values: dict[str, object] = {}

    if env.get("INVOICE_EXTRACT_GEMINI_API_KEY") is not None:
        values["gemini_api_key"] = env.get("INVOICE_EXTRACT_GEMINI_API_KEY") or None

    if env.get("INVOICE_EXTRACT_MODEL") is not None:
        values["model"] = env["INVOICE_EXTRACT_MODEL"]
    if env.get("INVOICE_EXTRACT_LOCALE") is not None:
        values["locale"] = env["INVOICE_EXTRACT_LOCALE"]
    if env.get("INVOICE_EXTRACT_MAX_PAGES") is not None:
        values["max_pages"] = _parse_int(env["INVOICE_EXTRACT_MAX_PAGES"], "INVOICE_EXTRACT_MAX_PAGES")
    if env.get("INVOICE_EXTRACT_OCR_MODE") is not None:
        values["ocr_mode"] = env["INVOICE_EXTRACT_OCR_MODE"]
    if env.get("INVOICE_EXTRACT_DRY_RUN") is not None:
        values["dry_run"] = _parse_bool(env["INVOICE_EXTRACT_DRY_RUN"], "INVOICE_EXTRACT_DRY_RUN")
    if env.get("INVOICE_EXTRACT_RENAME") is not None:
        values["rename"] = _parse_bool(env["INVOICE_EXTRACT_RENAME"], "INVOICE_EXTRACT_RENAME")
    if env.get("INVOICE_EXTRACT_FILENAME_SEPARATOR") is not None:
        values["filename_separator"] = env["INVOICE_EXTRACT_FILENAME_SEPARATOR"]
    if env.get("INVOICE_EXTRACT_FILENAME_SUFFIX") is not None:
        values["filename_suffix"] = env["INVOICE_EXTRACT_FILENAME_SUFFIX"]
    if env.get("INVOICE_EXTRACT_FILENAME_DATE_SEPARATOR") is not None:
        values["filename_date_separator"] = env["INVOICE_EXTRACT_FILENAME_DATE_SEPARATOR"]
    if env.get("INVOICE_EXTRACT_TIMEOUT_SECONDS") is not None:
        values["timeout_seconds"] = _parse_int(
            env["INVOICE_EXTRACT_TIMEOUT_SECONDS"],
            "INVOICE_EXTRACT_TIMEOUT_SECONDS",
        )
    if env.get("INVOICE_EXTRACT_DEBUG") is not None:
        values["debug"] = _parse_bool(env["INVOICE_EXTRACT_DEBUG"], "INVOICE_EXTRACT_DEBUG")

    return values


def _validate_and_normalize(values: dict[str, object]) -> dict[str, object]:
    model = str(values.get("model", "")).strip()
    if not model:
        raise ConfigError("model must not be empty")

    locale = str(values.get("locale", "")).strip().lower()
    if not locale:
        raise ConfigError("locale must not be empty")

    max_pages = int(values.get("max_pages", 0))
    if max_pages < 1:
        raise ConfigError("max_pages must be >= 1")

    ocr_mode = str(values.get("ocr_mode", "")).strip().lower()
    if ocr_mode not in {"auto", "gemini"}:
        raise ConfigError("ocr_mode must be 'auto' or 'gemini'")

    filename_separator = _normalize_filename_separator(values.get("filename_separator", "_"))
    filename_date_separator = _normalize_filename_date_separator(values.get("filename_date_separator", "-"))
    filename_suffix = _normalize_filename_suffix(values.get("filename_suffix", ""))

    timeout_seconds = int(values.get("timeout_seconds", 0))
    if timeout_seconds < 1:
        raise ConfigError("timeout_seconds must be >= 1")

    return {
        "gemini_api_key": _optional_str(values.get("gemini_api_key")),
        "model": model,
        "locale": locale,
        "max_pages": max_pages,
        "ocr_mode": ocr_mode,
        "dry_run": bool(values.get("dry_run", False)),
        "rename": bool(values.get("rename", False)),
        "filename_separator": filename_separator,
        "filename_suffix": filename_suffix,
        "filename_date_separator": filename_date_separator,
        "timeout_seconds": timeout_seconds,
        "debug": bool(values.get("debug", False)),
    }


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_bool(value: str, field_name: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"Invalid boolean for {field_name}: {value!r}")


def _parse_int(value: str, field_name: str) -> int:
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ConfigError(f"Invalid integer for {field_name}: {value!r}") from exc


def _normalize_filename_separator(value: object) -> str:
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
    if raw not in mapping:
        raise ConfigError("filename_separator must be one of: underscore, dash, space, _, -")
    return mapping[raw]


def _normalize_filename_date_separator(value: object) -> str:
    raw = str(value).strip().lower()
    mapping = {
        "dash": "-",
        "hyphen": "-",
        "-": "-",
        "dot": ".",
        ".": ".",
        "underscore": "_",
        "_": "_",
    }
    if raw not in mapping:
        raise ConfigError("filename_date_separator must be one of: dash, dot, underscore, -, ., _")
    return mapping[raw]


def _normalize_filename_suffix(value: object) -> str:
    text = str(value)
    cleaned = text.strip()
    cleaned = cleaned.replace("/", "-").replace("\\", "-")
    cleaned = "".join(ch for ch in cleaned if ch >= " " and ch != "\x7f")
    return cleaned
