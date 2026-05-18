"""PDF text extraction backed by PyMuPDF + optional OCR fallback.

The parser is deliberately small: extract per-page text, mark pages whose
text density is below ``low_text_threshold`` as ``needs_ocr=True``, and (when
``ocr_mode`` is not ``"off"``) hand those pages to the supplied adapter so
scanned PDFs can still feed the downstream pipeline.

OCR behaviour
-------------

- ``ocr_mode="off"``   parser ignores OCR. ``needs_ocr`` is still set on
  empty/low-text pages so callers can decide later.
- ``ocr_mode="auto"``  OCR is attempted only on pages with ``needs_ocr=True``.
- ``ocr_mode="force"`` OCR is attempted on every page.

When OCR is requested but the adapter is unavailable, every targeted page
receives ``ocr_error`` (no stacktrace), and the rest of the document still
parses cleanly.
"""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from document_intelligence.parsing.header_footer import strip_repeated_lines
from document_intelligence.parsing.ocr import (
    BaseOCRAdapter,
    NoopOCRAdapter,
    OCRMode,
)
from document_intelligence.parsing.text_cleaner import clean_page_text
from document_intelligence.schemas.document import DocumentPage, DocumentRef

_DEFAULT_LOW_TEXT_THRESHOLD = 50


class PDFParseError(RuntimeError):
    """Raised when a PDF cannot be opened or read."""


@dataclass(frozen=True)
class ParseSummary:
    """Aggregate diagnostics produced alongside the parsed pages."""

    pages_total: int
    pages_with_text: int
    pages_needing_ocr: int
    ocr_applied_pages: int
    ocr_failed_pages: int
    ocr_mode: OCRMode
    ocr_adapter: str
    ocr_available: bool
    ocr_unavailable_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages_total": self.pages_total,
            "pages_with_text": self.pages_with_text,
            "pages_needing_ocr": self.pages_needing_ocr,
            "ocr_applied_pages": self.ocr_applied_pages,
            "ocr_failed_pages": self.ocr_failed_pages,
            "ocr_mode": self.ocr_mode,
            "ocr_adapter": self.ocr_adapter,
            "ocr_available": self.ocr_available,
            "ocr_unavailable_reason": self.ocr_unavailable_reason,
        }


def _import_fitz() -> Any:
    try:
        import fitz  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised when extra missing
        raise PDFParseError(
            "PyMuPDF (fitz) is required to parse PDFs. "
            "Install with `pip install 'document-intelligence[pdf]'` or `pip install pymupdf`."
        ) from exc
    return fitz


def compute_document_id(path: Path) -> str:
    """Derive a stable document_id from absolute path + file size."""
    stat = path.stat()
    payload = f"{path.resolve()}::{stat.st_size}".encode()
    return hashlib.sha1(payload).hexdigest()[:16]


def _needs_ocr_for(text: str, threshold: int) -> bool:
    return len(text.strip()) < threshold


def parse_pdf(
    pdf_path: str | Path,
    *,
    strip_boilerplate: bool = True,
    ocr_mode: OCRMode = "off",
    ocr_adapter: BaseOCRAdapter | None = None,
    low_text_threshold: int = _DEFAULT_LOW_TEXT_THRESHOLD,
) -> tuple[DocumentRef, list[DocumentPage]]:
    """Parse a PDF into a ``DocumentRef`` plus one ``DocumentPage`` per page.

    See module docstring for OCR behaviour. Use :func:`parse_pdf_with_summary`
    when the caller also needs the aggregate ``ParseSummary``.
    """
    ref, pages, _summary = parse_pdf_with_summary(
        pdf_path,
        strip_boilerplate=strip_boilerplate,
        ocr_mode=ocr_mode,
        ocr_adapter=ocr_adapter,
        low_text_threshold=low_text_threshold,
    )
    return ref, pages


def parse_pdf_with_summary(
    pdf_path: str | Path,
    *,
    strip_boilerplate: bool = True,
    ocr_mode: OCRMode = "off",
    ocr_adapter: BaseOCRAdapter | None = None,
    low_text_threshold: int = _DEFAULT_LOW_TEXT_THRESHOLD,
) -> tuple[DocumentRef, list[DocumentPage], ParseSummary]:
    """Parse a PDF and return the ref, pages, and a parse summary."""
    path = Path(pdf_path)
    if not path.exists():
        raise PDFParseError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise PDFParseError(f"Expected a .pdf file, got: {path.suffix or '(no suffix)'}")

    fitz = _import_fitz()
    document_id = compute_document_id(path)
    pages: list[DocumentPage] = []

    try:
        with fitz.open(path) as doc:
            for index in range(len(doc)):
                raw = str(doc.load_page(index).get_text("text") or "")
                cleaned = clean_page_text(raw)
                needs_ocr = _needs_ocr_for(cleaned, low_text_threshold)
                pages.append(
                    DocumentPage(
                        document_id=document_id,
                        page_number=index + 1,
                        text="" if needs_ocr else cleaned,
                        char_count=len(cleaned),
                        needs_ocr=needs_ocr,
                    )
                )
    except PDFParseError:
        raise
    except Exception as exc:  # noqa: BLE001 — surface as PDFParseError
        raise PDFParseError(f"Failed to read PDF {path}: {exc}") from exc

    if strip_boilerplate:
        pages, _ = strip_repeated_lines(pages)
        # Re-evaluate needs_ocr after boilerplate stripping.
        pages = [
            page.model_copy(update={"needs_ocr": _needs_ocr_for(page.text, low_text_threshold)})
            for page in pages
        ]

    adapter: BaseOCRAdapter = ocr_adapter or NoopOCRAdapter()
    ocr_applied = 0
    ocr_failed = 0
    if ocr_mode != "off":
        new_pages: list[DocumentPage] = []
        for page in pages:
            should_ocr = ocr_mode == "force" or (ocr_mode == "auto" and page.needs_ocr)
            if not should_ocr:
                new_pages.append(page)
                continue
            result = adapter.ocr_page(path, page.page_number)
            if result.applied and result.text.strip():
                cleaned = clean_page_text(result.text)
                new_pages.append(
                    page.model_copy(
                        update={
                            "text": cleaned,
                            "char_count": len(cleaned),
                            "needs_ocr": _needs_ocr_for(cleaned, low_text_threshold),
                            "ocr_applied": True,
                            "ocr_error": None,
                        }
                    )
                )
                ocr_applied += 1
            else:
                new_pages.append(
                    page.model_copy(
                        update={
                            "ocr_applied": False,
                            "ocr_error": result.error or "OCR returned empty text",
                        }
                    )
                )
                if result.error:
                    ocr_failed += 1
        pages = new_pages

    pages_with_text = sum(1 for p in pages if not p.needs_ocr)
    pages_needing_ocr = sum(1 for p in pages if p.needs_ocr)
    summary = ParseSummary(
        pages_total=len(pages),
        pages_with_text=pages_with_text,
        pages_needing_ocr=pages_needing_ocr,
        ocr_applied_pages=ocr_applied,
        ocr_failed_pages=ocr_failed,
        ocr_mode=ocr_mode,
        ocr_adapter=adapter.name,
        ocr_available=adapter.available,
        ocr_unavailable_reason=adapter.unavailable_reason,
    )
    ref = DocumentRef.from_path(path, document_id=document_id)
    return ref, pages, summary
