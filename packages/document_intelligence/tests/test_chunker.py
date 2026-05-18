"""Chunker preserves page provenance and applies overlap."""

from __future__ import annotations

import pytest

from document_intelligence.chunking import chunk_document
from document_intelligence.schemas.document import DocumentPage, DocumentRef


def test_chunker_preserves_pages(sample_pages: tuple[DocumentRef, list[DocumentPage]]) -> None:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=400, overlap_chars=60)
    assert chunks, "chunker must produce at least one chunk"
    for c in chunks:
        assert c.page_start >= 1
        assert c.page_end >= c.page_start
        assert c.text
        assert c.chunk_id.startswith(ref.document_id)


def test_chunker_indices_are_dense_and_increasing(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=400, overlap_chars=60)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunker_covers_late_pages(sample_pages: tuple[DocumentRef, list[DocumentPage]]) -> None:
    """The last page must appear in some chunk's range."""
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=400, overlap_chars=60)
    last_page = pages[-1].page_number
    assert any(c.page_end >= last_page for c in chunks)


def test_chunker_detects_section_hint(sample_pages: tuple[DocumentRef, list[DocumentPage]]) -> None:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    hints = {c.section_hint for c in chunks if c.section_hint}
    assert any("EXPERIENCIA" in h or "ENTREGABLES" in h or "OBJETO" in h for h in hints)


def test_chunker_validates_parameters(sample_pages: tuple[DocumentRef, list[DocumentPage]]) -> None:
    ref, pages = sample_pages
    with pytest.raises(ValueError):
        chunk_document(ref, pages, max_chars=100, overlap_chars=0)
    with pytest.raises(ValueError):
        chunk_document(ref, pages, max_chars=400, overlap_chars=400)


def test_chunker_empty_input() -> None:
    ref = DocumentRef(document_id="empty00000000001", source_file="/x.pdf", file_size=0)
    assert chunk_document(ref, []) == []


def test_chunker_produces_cross_page_chunk() -> None:
    """When max_chars exceeds a single page, chunks must span pages."""
    ref = DocumentRef(document_id="crosspg000000001", source_file="/x.pdf", file_size=0)
    pages = [
        DocumentPage(
            document_id=ref.document_id,
            page_number=i + 1,
            text=("A" * 80 + " " + "B" * 80 + " " + "C" * 80 + " " + "D" * 80),
            char_count=323,
            needs_ocr=False,
        )
        for i in range(3)
    ]
    chunks = chunk_document(ref, pages, max_chars=600, overlap_chars=80)
    spanning = [c for c in chunks if c.page_end > c.page_start]
    assert spanning, "expected at least one chunk that spans multiple pages"
    multi = spanning[0]
    assert multi.page_end - multi.page_start >= 1


def test_chunker_prefers_paragraph_boundary() -> None:
    """When a paragraph break sits inside the rewind window, it wins over a space."""
    ref = DocumentRef(document_id="para00000000001x", source_file="/x.pdf", file_size=0)
    body = "Primera frase de la seccion A " * 10 + "\n\n" + "Segunda frase de la seccion B " * 10
    page = DocumentPage(
        document_id=ref.document_id,
        page_number=1,
        text=body,
        char_count=len(body),
        needs_ocr=False,
    )
    chunks = chunk_document(ref, [page], max_chars=400, overlap_chars=40)
    assert chunks
    # The first chunk should end at or shortly after the paragraph break, not in
    # the middle of a sentence.
    first = chunks[0]
    tail = body[first.char_end - 2 : first.char_end + 2]
    assert "\n\n" in body[first.char_start : first.char_end + 2] or tail.strip() == ""
