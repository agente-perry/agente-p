"""OCR adapter + parser integration: off/auto/force modes with mock adapters."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence.parsing import (
    NoopOCRAdapter,
    OCRResult,
    get_default_ocr_adapter,
)
from document_intelligence.parsing.pdf_parser import parse_pdf_with_summary


class FakeOCRAdapter:
    """Deterministic in-memory OCR adapter for tests.

    Returns a canned text per page number, marks the call as applied, and
    records every invocation so tests can assert call counts.
    """

    name = "fake"
    available = True
    unavailable_reason: str | None = None

    def __init__(self, text_by_page: dict[int, str] | None = None) -> None:
        self._text_by_page = text_by_page or {}
        self.calls: list[int] = []

    def ocr_page(self, pdf_path: Path, page_number: int) -> OCRResult:  # noqa: ARG002
        self.calls.append(page_number)
        text = self._text_by_page.get(
            page_number,
            "Texto OCR sintetico para la pagina con suficientes caracteres reales.",
        )
        return OCRResult(text=text, applied=True)


class UnavailableOCRAdapter:
    """Simulates an OCR adapter that cannot run (e.g. tesseract not installed)."""

    name = "unavailable-fake"
    available = False
    unavailable_reason = "fake adapter intentionally unavailable"

    def ocr_page(self, pdf_path: Path, page_number: int) -> OCRResult:  # noqa: ARG002
        return OCRResult(text="", applied=False, error=self.unavailable_reason)


def _scanned_pdf(tmp_path: Path) -> Path:
    """Build a PDF whose pages are image-only (no extractable text)."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")
    path = tmp_path / "scanned.pdf"
    doc = canvas.Canvas(str(path), pagesize=LETTER)
    # Draw shapes only; no drawString. PyMuPDF returns "" for these pages.
    for _ in range(3):
        doc.rect(72, 72, 200, 200, stroke=1, fill=0)
        doc.showPage()
    doc.save()
    return path


def _mixed_pdf(tmp_path: Path) -> Path:
    """Page 1 has text, pages 2-3 are image-only."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")
    path = tmp_path / "mixed.pdf"
    doc = canvas.Canvas(str(path), pagesize=LETTER)
    long_text = "Texto extraible con caracteres suficientes para superar el umbral predeterminado del parser."
    doc.drawString(72, 740, long_text)
    doc.showPage()
    for _ in range(2):
        doc.rect(72, 72, 200, 200, stroke=1, fill=0)
        doc.showPage()
    doc.save()
    return path


def test_off_marks_needs_ocr_without_applying(tmp_path: Path) -> None:
    pdf = _scanned_pdf(tmp_path)
    adapter = FakeOCRAdapter()
    _ref, pages, summary = parse_pdf_with_summary(pdf, ocr_mode="off", ocr_adapter=adapter)
    assert all(p.needs_ocr for p in pages)
    assert all(not p.ocr_applied for p in pages)
    assert adapter.calls == []
    assert summary.pages_needing_ocr == 3
    assert summary.ocr_applied_pages == 0
    assert summary.ocr_mode == "off"


def test_auto_applies_only_to_needs_ocr_pages(tmp_path: Path) -> None:
    pdf = _mixed_pdf(tmp_path)
    adapter = FakeOCRAdapter()
    _ref, pages, summary = parse_pdf_with_summary(pdf, ocr_mode="auto", ocr_adapter=adapter)
    # Page 1 already had text → no OCR call. Pages 2,3 → OCR called.
    assert set(adapter.calls) == {2, 3}
    assert pages[0].ocr_applied is False
    assert all(p.ocr_applied for p in pages[1:])
    assert summary.ocr_applied_pages == 2
    assert summary.ocr_mode == "auto"


def test_force_applies_to_every_page(tmp_path: Path) -> None:
    pdf = _mixed_pdf(tmp_path)
    adapter = FakeOCRAdapter()
    _ref, pages, summary = parse_pdf_with_summary(pdf, ocr_mode="force", ocr_adapter=adapter)
    assert sorted(adapter.calls) == [1, 2, 3]
    assert all(p.ocr_applied for p in pages)
    assert summary.ocr_applied_pages == 3
    assert summary.ocr_mode == "force"


def test_unavailable_adapter_does_not_crash(tmp_path: Path) -> None:
    pdf = _scanned_pdf(tmp_path)
    adapter = UnavailableOCRAdapter()
    _ref, pages, summary = parse_pdf_with_summary(pdf, ocr_mode="auto", ocr_adapter=adapter)
    assert summary.ocr_available is False
    assert summary.ocr_unavailable_reason
    assert summary.ocr_applied_pages == 0
    assert summary.ocr_failed_pages == 3
    for page in pages:
        assert page.ocr_applied is False
        assert page.ocr_error is not None


def test_default_adapter_reports_actionable_reason_when_unavailable() -> None:
    """When tesseract is missing the default adapter must explain why."""
    adapter = get_default_ocr_adapter()
    assert hasattr(adapter, "available")
    assert hasattr(adapter, "ocr_page")
    if not adapter.available:
        assert adapter.unavailable_reason
        actionable = adapter.unavailable_reason.lower()
        assert (
            "tesseract" in actionable
            or "pytesseract" in actionable
            or "pillow" in actionable
            or "pymupdf" in actionable
        ), f"reason is not actionable: {adapter.unavailable_reason!r}"
        result = adapter.ocr_page(Path("/dev/null"), 1)
        assert result.applied is False
        assert result.error


def test_noop_adapter_explicit(tmp_path: Path) -> None:
    pdf = _scanned_pdf(tmp_path)
    _ref, pages, summary = parse_pdf_with_summary(
        pdf, ocr_mode="auto", ocr_adapter=NoopOCRAdapter()
    )
    assert summary.ocr_available is False
    assert summary.ocr_applied_pages == 0
    assert summary.ocr_unavailable_reason
    assert all(not p.ocr_applied for p in pages)
