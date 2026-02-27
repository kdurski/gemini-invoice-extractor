from __future__ import annotations

from pathlib import Path

import pytest

from invoice_extract_cli.config import ConfigError, resolve_cli_settings


def test_resolve_cli_settings_reads_ini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "invoice-extract.ini"
    cfg.write_text(
        "\n".join(
            [
                "[invoice_extract]",
                "model = gemini-x",
                "locale = pl",
                "max_pages = 5",
                "ocr_mode = gemini",
                "dry_run = true",
                "rename = false",
                "filename_separator = space",
                "filename_suffix = (KD)",
                "filename_date_separator = dot",
                "timeout_seconds = 42",
                "debug = yes",
            ]
        ),
        encoding="utf-8",
    )

    settings = resolve_cli_settings()
    assert settings.config_path == cfg
    assert settings.model == "gemini-x"
    assert settings.locale == "pl"
    assert settings.max_pages == 5
    assert settings.ocr_mode == "gemini"
    assert settings.dry_run is True
    assert settings.rename is False
    assert settings.filename_separator == " "
    assert settings.filename_suffix == "(KD)"
    assert settings.filename_date_separator == "."
    assert settings.timeout_seconds == 42
    assert settings.debug is True


def test_env_overrides_ini(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    cfg = tmp_path / "custom.ini"
    cfg.write_text(
        "[invoice_extract]\nmodel = gemini-from-file\nmax_pages = 2\nrename = false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("INVOICE_EXTRACT_MODEL", "gemini-from-env")
    monkeypatch.setenv("INVOICE_EXTRACT_LOCALE", "en")
    monkeypatch.setenv("INVOICE_EXTRACT_MAX_PAGES", "9")
    monkeypatch.setenv("INVOICE_EXTRACT_RENAME", "true")
    monkeypatch.setenv("INVOICE_EXTRACT_FILENAME_SEPARATOR", "dash")
    monkeypatch.setenv("INVOICE_EXTRACT_FILENAME_SUFFIX", "(KD)")
    monkeypatch.setenv("INVOICE_EXTRACT_FILENAME_DATE_SEPARATOR", "dot")

    settings = resolve_cli_settings(config_path_override=cfg)
    assert settings.model == "gemini-from-env"
    assert settings.locale == "en"
    assert settings.max_pages == 9
    assert settings.rename is True
    assert settings.filename_separator == "-"
    assert settings.filename_suffix == "(KD)"
    assert settings.filename_date_separator == "."


def test_cli_overrides_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INVOICE_EXTRACT_MAX_PAGES", "7")
    monkeypatch.setenv("INVOICE_EXTRACT_DEBUG", "false")

    settings = resolve_cli_settings(max_pages=3, debug=True)
    assert settings.max_pages == 3
    assert settings.debug is True


def test_default_locale_is_polish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    settings = resolve_cli_settings()
    assert settings.locale == "pl"
    assert settings.filename_separator == "_"
    assert settings.filename_suffix == ""
    assert settings.filename_date_separator == "-"


def test_invalid_bool_in_config_raises(tmp_path: Path):
    cfg = tmp_path / "bad.ini"
    cfg.write_text("[invoice_extract]\ndry_run = maybe\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        resolve_cli_settings(config_path_override=cfg)


def test_invalid_filename_separator_raises(tmp_path: Path):
    cfg = tmp_path / "bad-separator.ini"
    cfg.write_text("[invoice_extract]\nfilename_separator = dot\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        resolve_cli_settings(config_path_override=cfg)


def test_filename_separator_accepts_literal_space(tmp_path: Path):
    cfg = tmp_path / "space.ini"
    cfg.write_text("[invoice_extract]\nfilename_separator = space\n", encoding="utf-8")
    settings = resolve_cli_settings(config_path_override=cfg)
    assert settings.filename_separator == " "


def test_local_ini_overrides_base_ini(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "invoice-extract.ini").write_text(
        "[invoice_extract]\nmodel = base-model\nlocale = pl\ndry_run = false\nmax_pages = 2\n",
        encoding="utf-8",
    )
    local_cfg = tmp_path / "invoice-extract.local.ini"
    local_cfg.write_text(
        "[invoice_extract]\nmodel = local-model\ndry_run = true\nmax_pages = 4\n",
        encoding="utf-8",
    )

    settings = resolve_cli_settings()
    assert settings.model == "local-model"
    assert settings.dry_run is True
    assert settings.max_pages == 4
    assert settings.locale == "pl"
    assert settings.config_path == local_cfg
