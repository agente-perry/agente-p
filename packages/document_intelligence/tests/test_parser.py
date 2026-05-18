"""PDF parser: real PyMuPDF read of a synthetic PDF."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence.parsing import PDFParseError, parse_pdf


def test_parse_synthetic_pdf(synthetic_pdf: Path) -> None:
    ref, pages = parse_pdf(synthetic_pdf)
    assert ref.document_id
    assert ref.file_size > 0
    assert len(pages) == 5
    assert pages[0].page_number == 1
    assert pages[-1].page_number == 5
    assert "OBJETO DEL SERVICIO" in pages[0].text
    assert "EXPERIENCIA DEL POSTOR" in pages[1].text
    assert not any(p.needs_ocr for p in pages)


def test_parse_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PDFParseError):
        parse_pdf(tmp_path / "nope.pdf")


def test_parse_rejects_non_pdf(tmp_path: Path) -> None:
    txt = tmp_path / "x.txt"
    txt.write_text("hello")
    with pytest.raises(PDFParseError):
        parse_pdf(txt)


def test_parse_strips_repeated_headers_and_footers(tmp_path: Path) -> None:
    """A PDF with a repeated header/footer on every page must come back stripped."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    path = tmp_path / "with_boilerplate.pdf"
    bodies = ["Alfa contenido.", "Beta contenido.", "Gamma contenido.", "Delta contenido."]
    header = "MUNICIPALIDAD DE LIMA"
    footer = "Boletin oficial 2026"
    doc = canvas.Canvas(str(path), pagesize=LETTER)
    for body in bodies:
        doc.drawString(72, 760, header)
        doc.drawString(72, 720, body)
        doc.drawString(72, 60, footer)
        doc.showPage()
    doc.save()

    _, pages = parse_pdf(path)
    for page, body in zip(pages, bodies, strict=True):
        assert header not in page.text
        assert footer not in page.text
        assert body in page.text


def test_parse_can_keep_boilerplate_when_disabled(tmp_path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    path = tmp_path / "raw_boilerplate.pdf"
    header = "ENCABEZADO REPETIDO"
    bodies = (
        "Contenido especifico A con suficiente texto util para no disparar OCR.",
        "Contenido especifico B con suficiente texto util para no disparar OCR.",
        "Contenido especifico C con suficiente texto util para no disparar OCR.",
        "Contenido especifico D con suficiente texto util para no disparar OCR.",
    )
    doc = canvas.Canvas(str(path), pagesize=LETTER)
    for body in bodies:
        doc.drawString(72, 760, header)
        doc.drawString(72, 720, body)
        doc.showPage()
    doc.save()

    _, pages = parse_pdf(path, strip_boilerplate=False)
    assert any(header in p.text for p in pages)
