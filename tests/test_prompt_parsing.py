from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from invoice_extract_cli.gemini_client import extract_json_object, parse_gemini_response_text


def test_extract_json_object_from_fenced_block():
    text = """```json
    {"invoice_date_raw":"10 Feb 2026","invoice_date_iso":"2026-02-10","short_description":"monitor arm","confidence":0.9,"notes":null}
    ```"""
    payload = extract_json_object(text)
    assert payload.startswith("{")
    assert payload.endswith("}")


def test_parse_gemini_response_text_validates_schema():
    response = parse_gemini_response_text(
        '{"invoice_date_raw":"10 Feb 2026","invoice_date_iso":"2026-02-10","short_description":"monitor arm","confidence":0.88,"notes":"due date also present"}'
    )
    assert response.invoice_date_iso == "2026-02-10"
    assert response.short_description == "monitor arm"
