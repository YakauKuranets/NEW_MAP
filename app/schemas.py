"""Pydantic v2 contracts for strict API input/output validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    """Base strict schema: forbids unknown fields and strips strings."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class TelemetryCreateSchema(StrictSchema):
    """Contract for telemetry point creation requests."""

    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    alt: float | None = Field(default=None, ge=-1000, le=100000)
    battery: int | None = Field(default=None, ge=0, le=100)
    status: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)


class IncidentCreateSchema(StrictSchema):
    """Contract for incident creation requests."""

    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    level: int = Field(ge=1, le=5)
    location: str = Field(min_length=1, max_length=255)


class AiVoiceResultSchema(StrictSchema):
    """Contract for AI voice processing results (OpenAI response payload)."""

    transcript: str = Field(min_length=1, max_length=12000)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    confidence: float | None = Field(default=None, ge=0, le=1)
    intent: str | None = Field(default=None, min_length=1, max_length=128)
    entities: dict[str, Any] = Field(default_factory=dict)
    model: str | None = Field(default=None, min_length=1, max_length=128)


class IncidentChatSendSchema(StrictSchema):
    """Contract for posting incident chat messages."""

    text: str = Field(min_length=1, max_length=4000)
    author_id: str = Field(min_length=1, max_length=128)
