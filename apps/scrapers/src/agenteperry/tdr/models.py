"""Typed models for the AgentePerry TDR pipeline."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class TdrSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TdrDocumentMetadata(BaseModel):
    external_id: str | None = None
    title: str
    entity_name: str | None = None
    procedure_code: str | None = None
    source_url: str | None = None
    file_url: str | None = None
    sector: str | None = None
    region: str | None = None
    district: str | None = None
    publication_date: date | None = None
    estimated_value: float | None = None
    local_path: Path | None = None


class TdrPage(BaseModel):
    tdr_id: str | None = None
    page_number: int = Field(ge=1)
    text_content: str


class TdrChunk(BaseModel):
    tdr_id: str | None = None
    chunk_index: int = Field(ge=0)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    text: str
    metadata: dict[str, object] = Field(default_factory=dict)


class TdrFlag(BaseModel):
    tdr_id: str | None = None
    chunk_id: str | None = None
    flag_code: str
    flag_name: str
    severity: TdrSeverity
    score_contribution: int = Field(ge=0, le=100)
    evidence_quote: str = Field(min_length=1)
    page_number: int = Field(ge=1)
    explanation: str
    detection_method: str = "rule"
    rule_id: str


class TdrEmbeddingInput(BaseModel):
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    embedding_model: str = "text-embedding-3-small"
