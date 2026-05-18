"""Document-level schemas: file reference and parsed pages."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DocumentRef(BaseModel):
    """Stable reference to a source document on disk."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(description="Stable hash-based id derived from file path + size.")
    source_file: str = Field(description="Absolute or repo-relative path to the source file.")
    file_size: int = Field(ge=0)
    sha1: str | None = Field(default=None, description="Optional content hash for traceability.")

    @classmethod
    def from_path(cls, path: Path, *, document_id: str, sha1: str | None = None) -> DocumentRef:
        return cls(
            document_id=document_id,
            source_file=str(path),
            file_size=path.stat().st_size,
            sha1=sha1,
        )


class DocumentPage(BaseModel):
    """A single parsed page from a source PDF."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    page_number: int = Field(ge=1, description="1-indexed page number for auditable citations.")
    text: str = Field(description="Cleaned page text. May be empty when page is image-only.")
    char_count: int = Field(ge=0)
    needs_ocr: bool = Field(
        default=False,
        description="True when the page has no extractable text and likely needs OCR.",
    )
    ocr_applied: bool = Field(
        default=False,
        description="True when OCR was successfully applied and ``text`` comes from OCR.",
    )
    ocr_error: str | None = Field(
        default=None,
        description="Error message when OCR was attempted but failed for this page.",
    )
