"""Header / footer dedup: detect repeated boilerplate, leave body alone."""

from __future__ import annotations

from document_intelligence.parsing import detect_repeated_lines, strip_repeated_lines
from document_intelligence.schemas.document import DocumentPage


def _page(n: int, text: str) -> DocumentPage:
    return DocumentPage(
        document_id="hf-fixture-0001",
        page_number=n,
        text=text,
        char_count=len(text),
        needs_ocr=False,
    )


def test_detect_repeated_header_and_footer() -> None:
    body_a = "Contenido especifico A."
    body_b = "Contenido especifico B con datos."
    body_c = "Contenido especifico C distinto."
    body_d = "Contenido especifico D final."
    header = "MUNICIPALIDAD DE LIMA - LICITACION 001-2026"
    footer = "Pagina confidencial - Uso interno"
    pages = [
        _page(1, f"{header}\n{body_a}\n{footer}"),
        _page(2, f"{header}\n{body_b}\n{footer}"),
        _page(3, f"{header}\n{body_c}\n{footer}"),
        _page(4, f"{header}\n{body_d}\n{footer}"),
    ]
    report = detect_repeated_lines(pages)
    assert header in report.headers
    assert footer in report.footers


def test_strip_removes_only_boilerplate_keeps_body() -> None:
    header = "REPUBLICA DEL PERU - MINISTERIO X"
    footer = "Boletin oficial 2026"
    bodies = ["Alfa proyecto.", "Beta proyecto.", "Gamma proyecto.", "Delta proyecto."]
    pages = [_page(i + 1, f"{header}\n{body}\n{footer}") for i, body in enumerate(bodies)]
    cleaned, report = strip_repeated_lines(pages)
    assert report.pages_modified == 4
    for cleaned_page, body in zip(cleaned, bodies, strict=True):
        assert header not in cleaned_page.text
        assert footer not in cleaned_page.text
        assert body in cleaned_page.text


def test_unique_first_last_lines_are_kept() -> None:
    pages = [
        _page(1, "Titulo unico A\nContenido."),
        _page(2, "Titulo unico B\nOtro contenido."),
        _page(3, "Titulo unico C\nMas contenido."),
    ]
    cleaned, report = strip_repeated_lines(pages)
    assert report.headers == []
    assert report.footers == []
    for cleaned_page, original in zip(cleaned, pages, strict=True):
        assert cleaned_page.text == original.text


def test_short_document_skips_dedup() -> None:
    pages = [_page(1, "X\nbody1"), _page(2, "X\nbody2")]
    report = detect_repeated_lines(pages, min_pages=3)
    assert report.headers == []
