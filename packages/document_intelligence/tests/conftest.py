"""Test fixtures: synthetic PDFs and document pages."""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence.schemas.document import DocumentPage, DocumentRef

_SAMPLE_PAGES = [
    (
        "OBJETO DEL SERVICIO\n\n"
        "Contratacion del servicio de consultoria para el diseno tecnico "
        "del sistema integral de monitoreo ambiental."
    ),
    (
        "EXPERIENCIA DEL POSTOR\n\n"
        "El postor debe acreditar experiencia minima de diez anos en proyectos "
        "del mismo sector y haber ejecutado contratos por un monto acumulado no "
        "menor a quince millones de soles en los ultimos tres anos."
    ),
    (
        "ENTREGABLES\n\n"
        "El informe final debera presentarse impreso en formato A3 y en dos "
        "ejemplares originales. No se requiere base de datos estructurada ni "
        "dataset en formato CSV."
    ),
    (
        "PLAZO DE EJECUCION\n\n"
        "El plazo total es de noventa dias calendario contados desde el dia "
        "siguiente de la suscripcion del contrato."
    ),
    (
        "CRITERIOS DE EVALUACION\n\n"
        "La propuesta sera evaluada conforme al juicio del comite tecnico. "
        "Se valorara la calidad general y la afinidad institucional."
    ),
]


@pytest.fixture
def sample_pages() -> tuple[DocumentRef, list[DocumentPage]]:
    """In-memory document used by chunker / index tests (no PDF needed)."""
    document_id = "fixture0000000001"
    pages = [
        DocumentPage(
            document_id=document_id,
            page_number=i + 1,
            text=body,
            char_count=len(body),
            needs_ocr=False,
        )
        for i, body in enumerate(_SAMPLE_PAGES)
    ]
    ref = DocumentRef(
        document_id=document_id,
        source_file="/virtual/fixture.pdf",
        file_size=1234,
    )
    return ref, pages


@pytest.fixture
def synthetic_pdf(tmp_path: Path) -> Path:
    """Build a real multi-page PDF for parser tests using reportlab."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed; run with --extra dev")

    path = tmp_path / "synthetic.pdf"
    doc = canvas.Canvas(str(path), pagesize=LETTER)
    for body in _SAMPLE_PAGES:
        y = 740
        for line in body.split("\n"):
            doc.drawString(72, y, line)
            y -= 18
        doc.showPage()
    doc.save()
    return path
