from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ExtractionMethod = Literal["pdf_text", "gemini_vision"]


class PagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    text_length: int = Field(ge=0)
    mime_type: str | None = None


class GeminiResponseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_date_raw: str | None = None
    invoice_date_iso: str | None = None
    short_description: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str | None = None

    @field_validator("short_description")
    @classmethod
    def _normalize_short_description(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("short_description must not be empty")
        return cleaned


class ProcessingDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method_selected: ExtractionMethod
    pages_examined: int = Field(ge=0)
    text_quality_score: float | None = None
    fallback_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_file: str
    invoice_date: str | None = None
    invoice_date_raw: str | None = None
    short_description: str
    short_description_words: int = Field(ge=0)
    filename_stub: str
    extraction_method: ExtractionMethod
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
