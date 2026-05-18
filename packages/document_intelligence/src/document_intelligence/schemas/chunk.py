"""Chunk schema — atomic unit for retrieval and analysis."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentChunk(BaseModel):
    """A semantic chunk of a document with page provenance preserved."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(description="Stable id: f'{document_id}::{chunk_index:05d}'.")
    document_id: str
    source_file: str
    chunk_index: int = Field(ge=0)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)
    section_hint: str | None = Field(
        default=None,
        description="Heuristic label from upstream headings, e.g. 'EXPERIENCIA DEL POSTOR'.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
