from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from invoice_extract_cli.gemini_client import iter_models_from_response, model_metadata_to_public_dict


class _FakeModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_iter_models_from_response_accepts_dict():
    response = {"models": [{"name": "models/gemini-2.5-flash"}]}
    models = iter_models_from_response(response)
    assert len(models) == 1


def test_model_metadata_to_public_dict_extracts_limits_and_methods():
    fake = _FakeModel(
        name="models/gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        description="Fast model",
        input_token_limit=1048576,
        output_token_limit=8192,
        supported_generation_methods=["generateContent"],
    )
    result = model_metadata_to_public_dict(fake)
    assert result["name"] == "models/gemini-2.5-flash"
    assert result["input_token_limit"] == 1048576
    assert result["output_token_limit"] == 8192
    assert result["supported_generation_methods"] == ["generateContent"]
