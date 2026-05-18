"""CLI surface for OCR flags on inspect-pdf and analyze."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from document_intelligence.cli import main


def _build_scanned_pdf(tmp_path: Path) -> Path:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")
    pdf = tmp_path / "scanned.pdf"
    doc = canvas.Canvas(str(pdf), pagesize=LETTER)
    for _ in range(2):
        doc.rect(72, 72, 200, 200, stroke=1, fill=0)
        doc.showPage()
    doc.save()
    return pdf


def test_inspect_pdf_accepts_ocr_flag(tmp_path: Path) -> None:
    pdf = _build_scanned_pdf(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["inspect-pdf", str(pdf), "--ocr", "off"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["page_count"] == 2
    assert payload["ocr_mode"] == "off"
    assert payload["pages_needing_ocr"] == 2
    assert payload["pages_with_text"] == 0
    assert "ocr_available" in payload
    for page in payload["pages"]:
        assert "ocr_applied" in page
        assert "ocr_error" in page


def test_inspect_pdf_with_auto_reports_unavailable_when_no_tesseract(
    tmp_path: Path,
) -> None:
    pdf = _build_scanned_pdf(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["inspect-pdf", str(pdf), "--ocr", "auto"])
    # Should never crash; payload reports availability state honestly.
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ocr_mode"] == "auto"
    if not payload["ocr_available"]:
        assert payload["ocr_unavailable_reason"]
        assert payload["ocr_applied_pages"] == 0


def test_analyze_accepts_ocr_flag(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")
    pdf = tmp_path / "text.pdf"
    doc = canvas.Canvas(str(pdf), pagesize=LETTER)
    body = "OBJETO DEL SERVICIO\nServicio integral con texto suficiente para parseo normal."
    y = 740
    for line in body.splitlines():
        doc.drawString(72, y, line)
        y -= 18
    doc.showPage()
    doc.save()

    runner = CliRunner()
    out_path = tmp_path / "analysis.json"
    result = runner.invoke(
        main,
        [
            "analyze",
            str(pdf),
            "--question",
            "Detecta senales de baja trazabilidad",
            "--ocr",
            "off",
            "--output",
            str(out_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert "disclaimer" in payload
    assert "flags" in payload
    assert "parse_summary" in payload
    assert payload["parse_summary"]["ocr_mode"] == "off"
    assert "pages_needing_ocr" in payload["parse_summary"]
