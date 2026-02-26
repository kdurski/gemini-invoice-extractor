from __future__ import annotations

from invoice_extract_cli.gemini_client import build_text_prompt, build_vision_prompt


def test_polish_locale_prompt_requests_polish_description():
    prompt = build_text_prompt("pl")
    assert "Write short_description in Polish whenever possible" in prompt


def test_english_locale_prompt_requests_english_description():
    prompt = build_vision_prompt("en")
    assert "Write short_description in English." in prompt
