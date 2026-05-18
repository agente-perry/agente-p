"""Models for OCR pipeline outputs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PdfOcrClass:
    TEXTUAL = "textual"
    MIXED = "mixed"
    SCANNED = "scanned"
    UNSUPPORTED = "unsupported"


class OcrPageStatus:
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


class OcrDocumentStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    SKIPPED = "skipped"


class PdfClassification(BaseModel):
    pdf_path: str
    extension: str
    pages_total: int = Field(ge=0)
    pages_with_text: int = Field(ge=0)
    pages_without_text: int = Field(ge=0)
    coverage_pct: float = Field(ge=0)
    classification: str
    needs_ocr: bool
    recommended_action: str
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class OcrPageResult(BaseModel):
    page_number: int = Field(ge=1)
    status: str
    text: str
    text_length: int = Field(ge=0)
    provider: str
    model: str
    latency_ms: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")


class OcrManifest(BaseModel):
    document_id: str
    ocid: str | None = None
    source_pdf_path: str
    source_pdf_sha256: str
    ocr_provider: str
    ocr_model: str
    pages_total: int = Field(ge=0)
    pages_attempted: int = Field(ge=0)
    pages_succeeded: int = Field(ge=0)
    pages_failed: int = Field(ge=0)
    status: str
    coverage_before_pct: float = Field(ge=0)
    coverage_after_pct: float = Field(ge=0)
    output_dir: str
    started_at: str
    finished_at: str | None = None
    errors_count: int = Field(ge=0)

    def to_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")
