"""DocumentMapperAgent: detect canonical sections from page headings."""

from __future__ import annotations

from document_intelligence.agents import DocumentMapperAgent, map_document
from document_intelligence.schemas.document import DocumentPage


def _page(n: int, text: str) -> DocumentPage:
    return DocumentPage(
        document_id="mapper-fixture",
        page_number=n,
        text=text,
        char_count=len(text),
        needs_ocr=False,
    )


def test_mapper_detects_canonical_sections() -> None:
    pages = [
        _page(1, "OBJETO DEL SERVICIO\n\nServicio de consultoria.\n"),
        _page(2, "EXPERIENCIA DEL POSTOR\n\nExperiencia minima de diez anos."),
        _page(3, "ENTREGABLES\n\nInforme impreso en formato A3."),
        _page(4, "Continuacion del entregable."),
        _page(5, "PLAZO DE EJECUCION\n\nNoventa dias calendario."),
    ]
    tdr_map = map_document("doc-001", pages)
    labels = [s.name for s in tdr_map.sections]
    assert "Objeto y finalidad" in labels
    assert "Experiencia del postor" in labels
    assert "Entregables" in labels
    assert "Plazos" in labels


def test_mapper_section_page_ranges_are_dense() -> None:
    pages = [
        _page(1, "OBJETO DEL SERVICIO\n\nblabla"),
        _page(2, "Continuacion sin heading."),
        _page(3, "ENTREGABLES\n\nInforme.")
    ]
    tdr_map = map_document("doc-002", pages)
    objeto = next(s for s in tdr_map.sections if s.name == "Objeto y finalidad")
    assert objeto.page_start == 1
    assert objeto.page_end == 2


def test_mapper_unmatched_pages_are_recorded() -> None:
    pages = [_page(1, "Texto introductorio sin heading reconocible."), _page(2, "Mas texto.")]
    tdr_map = map_document("doc-003", pages)
    assert tdr_map.sections == []
    assert tdr_map.unmatched_pages == [1, 2]


def test_mapper_agent_callable_returns_same_result() -> None:
    pages = [_page(1, "OBJETO DEL SERVICIO\n\nfoo")]
    agent = DocumentMapperAgent()
    assert agent("doc-004", pages) == map_document("doc-004", pages)
