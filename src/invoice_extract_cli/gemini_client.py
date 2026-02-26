from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .models import GeminiResponseSchema


class GeminiClientError(RuntimeError):
    pass


class GeminiInvoiceExtractor:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.0-flash",
        timeout_seconds: int = 30,
        locale: str = "pl",
    ):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.locale = (locale or "pl").strip().lower()
        self._client: Any | None = None
        self._types: Any | None = None

        if not self.api_key:
            raise GeminiClientError("INVOICE_EXTRACT_GEMINI_API_KEY is not set")

    def extract_from_text(self, text: str) -> GeminiResponseSchema:
        clipped_text = text[:60000]
        payload = f"{build_text_prompt(self.locale)}\n\nINVOICE_TEXT_START\n{clipped_text}\nINVOICE_TEXT_END\n"
        response_text = self._generate_content([payload])
        return parse_gemini_response_text(response_text)

    def extract_from_images(self, images: list[bytes]) -> GeminiResponseSchema:
        if not images:
            raise GeminiClientError("No images were provided for Gemini vision extraction")

        client, types = self._ensure_client()
        if types is None or not hasattr(types, "Part"):
            raise GeminiClientError("Installed google-genai SDK does not support image parts API")

        image_parts = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images]
        response_text = self._generate_content(
            [build_vision_prompt(self.locale), *image_parts],
            client=client,
            types=types,
        )
        return parse_gemini_response_text(response_text)

    def _ensure_client(self) -> tuple[Any, Any]:
        if self._client is not None:
            return self._client, self._types

        try:
            from google import genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment-specific
            raise GeminiClientError(
                "google-genai is not installed. Run: asdf exec uv sync --extra dev"
            ) from exc

        types = getattr(genai, "types", None)
        try:
            client = genai.Client(api_key=self.api_key)
        except Exception as exc:  # pragma: no cover - network/auth setup specific
            raise GeminiClientError(f"Failed to initialize Gemini client: {exc}") from exc

        self._client = client
        self._types = types
        return client, types

    def _generate_content(self, contents: list[Any], client: Any | None = None, types: Any | None = None) -> str:
        client = client or self._ensure_client()[0]
        if types is None:
            _, types = self._ensure_client()

        config = self._build_config(types)

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "contents": contents,
            }
            if config is not None:
                kwargs["config"] = config
            response = client.models.generate_content(**kwargs)
        except Exception as exc:  # pragma: no cover - network/API-specific
            raise GeminiClientError(f"Gemini API request failed: {exc}") from exc

        text = _response_to_text(response)
        if not text:
            raise GeminiClientError("Gemini returned an empty response")
        return text

    def list_models(
        self,
        *,
        only_gemini: bool = True,
        name_contains: str | None = None,
    ) -> dict[str, Any]:
        client, _ = self._ensure_client()
        try:
            response = client.models.list()
        except Exception as exc:  # pragma: no cover - network/API-specific
            raise GeminiClientError(f"Failed to list Gemini models: {exc}") from exc

        items: list[dict[str, Any]] = []
        filter_text = (name_contains or "").strip().lower()
        for raw_model in iter_models_from_response(response):
            model_info = model_metadata_to_public_dict(raw_model)
            searchable = f"{model_info.get('name', '')} {model_info.get('display_name', '')}".lower()
            if only_gemini and "gemini" not in searchable:
                continue
            if filter_text and filter_text not in searchable:
                continue
            items.append(model_info)

        items.sort(key=lambda item: item.get("name") or "")
        return {
            "source": "gemini_api",
            "count": len(items),
            "quota_note": (
                "The public models list typically exposes model metadata and token limits, "
                "but not project/account quota usage or remaining quota."
            ),
            "models": items,
        }

    def _build_config(self, types: Any | None) -> Any | None:
        if types is None or not hasattr(types, "GenerateContentConfig"):
            return None

        kwargs = {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        }

        # Timeout support varies by SDK version; only include if supported.
        if self.timeout_seconds and "timeout" in getattr(types.GenerateContentConfig, "__annotations__", {}):
            kwargs["timeout"] = self.timeout_seconds

        try:
            return types.GenerateContentConfig(**kwargs)
        except Exception:
            return None


def parse_gemini_response_text(response_text: str) -> GeminiResponseSchema:
    try:
        payload = json.loads(extract_json_object(response_text))
    except json.JSONDecodeError as exc:
        raise GeminiClientError(f"Gemini did not return valid JSON: {exc}") from exc

    try:
        return GeminiResponseSchema.model_validate(payload)
    except ValidationError as exc:
        raise GeminiClientError(f"Gemini response schema validation failed: {exc}") from exc


def build_text_prompt(locale: str = "pl") -> str:
    return _build_prompt(
        "Extract invoice metadata from the provided invoice text.",
        locale=locale,
    )


def build_vision_prompt(locale: str = "pl") -> str:
    return _build_prompt(
        "Extract invoice metadata from the provided invoice page images (OCR and interpret).",
        locale=locale,
    )


def _build_prompt(task_intro: str, *, locale: str) -> str:
    language_rule = _language_rule(locale)
    return f"""{task_intro}

Return JSON only with this schema:
{{
  "invoice_date_raw": string | null,
  "invoice_date_iso": string | null,
  "short_description": string,
  "confidence": number,
  "notes": string | null
}}

Rules:
- Prefer invoice issue date over due date or service date when present.
- If ambiguous, choose the best guess, lower confidence, and explain in notes.
- short_description must describe the purchased item/service, not the vendor, and be 5 words or fewer.
- If the item/service is unclear, use a generic but useful label.
- {language_rule}
"""


def _language_rule(locale: str) -> str:
    normalized = (locale or "pl").strip().lower()
    if normalized.startswith("pl"):
        return "Write short_description in Polish whenever possible (e.g., 'filtr', 'kawa')."
    if normalized.startswith("en"):
        return "Write short_description in English."
    return f"Write short_description in locale '{normalized}' whenever possible."


def extract_json_object(text: str) -> str:
    stripped = text.strip()

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise GeminiClientError("Could not find JSON object in Gemini response")

    return stripped[start : end + 1]


def _response_to_text(response: Any) -> str | None:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text.strip():
                return part_text

    return None


def iter_models_from_response(response: Any) -> list[Any]:
    if response is None:
        return []
    if isinstance(response, list):
        return response
    if isinstance(response, tuple):
        return list(response)
    if isinstance(response, dict):
        models = response.get("models")
        if isinstance(models, list):
            return models
        return []
    if hasattr(response, "models"):
        models = getattr(response, "models")
        if isinstance(models, list):
            return models
    try:
        return list(response)
    except TypeError:
        return []


def model_metadata_to_public_dict(model: Any) -> dict[str, Any]:
    name = _field(model, "name")
    display_name = _field(model, "display_name", "displayName")
    description = _field(model, "description")
    input_token_limit = _field(model, "input_token_limit", "inputTokenLimit")
    output_token_limit = _field(model, "output_token_limit", "outputTokenLimit")
    supported_methods = _field(
        model,
        "supported_generation_methods",
        "supportedGenerationMethods",
    )
    version = _field(model, "version")
    state = _field(model, "state")
    quota_like = _field(model, "quotas", "quota", "rate_limits", "rateLimits")

    data: dict[str, Any] = {
        "name": name,
        "display_name": display_name,
        "description": description,
        "input_token_limit": _maybe_int(input_token_limit),
        "output_token_limit": _maybe_int(output_token_limit),
        "supported_generation_methods": _string_list_or_none(supported_methods),
        "version": _string_or_none(version),
        "state": _string_or_none(state),
    }
    if quota_like is not None:
        data["quota_metadata"] = _jsonable(quota_like)
    return data


def _field(obj: Any, *names: str) -> Any | None:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list_or_none(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return [str(value)]


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return _jsonable(vars(value))
        except Exception:
            pass
    return str(value)
