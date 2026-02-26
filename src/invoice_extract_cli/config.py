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
    pretty: bool
    timeout_seconds: int
    debug: bool


def resolve_cli_settings(
    *,
    config_path_override: Path | None = None,
    model: str | None = None,
    locale: str | None = None,
    max_pages: int | None = None,
    ocr_mode: str | None = None,
    pretty: bool | None = None,
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
        "pretty": False,
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
    if pretty is not None:
        cli_overrides["pretty"] = pretty
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
    if "pretty" in section:
        values["pretty"] = _parse_bool(section.get("pretty", fallback=""), "pretty")
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
    if env.get("INVOICE_EXTRACT_PRETTY") is not None:
        values["pretty"] = _parse_bool(env["INVOICE_EXTRACT_PRETTY"], "INVOICE_EXTRACT_PRETTY")
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

    timeout_seconds = int(values.get("timeout_seconds", 0))
    if timeout_seconds < 1:
        raise ConfigError("timeout_seconds must be >= 1")

    return {
        "gemini_api_key": _optional_str(values.get("gemini_api_key")),
        "model": model,
        "locale": locale,
        "max_pages": max_pages,
        "ocr_mode": ocr_mode,
        "pretty": bool(values.get("pretty", False)),
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
