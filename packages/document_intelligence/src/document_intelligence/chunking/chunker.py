"""Cross-page chunker that preserves page provenance.

Unlike a per-page chunker, this concatenates pages into a single stream so chunks
can span page boundaries. Each chunk records ``page_start`` and ``page_end`` derived
from a sorted offset table so citations remain auditable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from document_intelligence.schemas.chunk import DocumentChunk
from document_intelligence.schemas.document import DocumentPage, DocumentRef

_HEADING_RE = re.compile(
    r"^\s*(?:[IVXLCDM]+\.\s+|[0-9]+(?:\.[0-9]+)*\s+)?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 /,\-]{4,})\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class _PageOffset:
    page_number: int
    char_start: int
    char_end: int


def _build_offset_table(pages: list[DocumentPage]) -> tuple[str, list[_PageOffset]]:
    parts: list[str] = []
    offsets: list[_PageOffset] = []
    cursor = 0
    for page in pages:
        body = page.text or ""
        start = cursor
        parts.append(body)
        cursor += len(body)
        # Separator between pages — kept short to avoid skewing chunk sizes much.
        if page is not pages[-1]:
            parts.append("\n\n")
            cursor += 2
        offsets.append(_PageOffset(page.page_number, start, cursor))
    return "".join(parts), offsets


def _page_range_for(span_start: int, span_end: int, offsets: list[_PageOffset]) -> tuple[int, int]:
    page_start = offsets[0].page_number
    page_end = offsets[-1].page_number
    for off in offsets:
        if off.char_start <= span_start < off.char_end:
            page_start = off.page_number
            break
    for off in offsets:
        if off.char_start < span_end <= off.char_end:
            page_end = off.page_number
            break
        if span_end > off.char_end:
            page_end = off.page_number
    return page_start, max(page_end, page_start)


def _rewind_to_boundary(text: str, lower: int, upper: int) -> int:
    """Prefer a paragraph break, then a sentence end, then a whitespace boundary."""
    # paragraph break ("\n\n")
    paragraph = text.rfind("\n\n", lower + 1, upper)
    if paragraph > lower + (upper - lower) // 2:
        return paragraph + 2
    # sentence end followed by whitespace
    for marker in (". ", ".\n", "? ", "! "):
        idx = text.rfind(marker, lower + 1, upper)
        if idx > lower + (upper - lower) // 2:
            return idx + len(marker)
    # any whitespace
    space = text.rfind(" ", lower + 1, upper)
    if space > lower:
        return space
    newline = text.rfind("\n", lower + 1, upper)
    if newline > lower:
        return newline
    return upper


def _last_heading_before(text: str, position: int) -> str | None:
    candidate: str | None = None
    for match in _HEADING_RE.finditer(text, 0, position):
        candidate = match.group(1).strip()
    return candidate


def chunk_document(
    ref: DocumentRef,
    pages: list[DocumentPage],
    *,
    max_chars: int = 1200,
    overlap_chars: int = 160,
) -> list[DocumentChunk]:
    """Split a parsed document into overlapping chunks with page provenance."""
    if max_chars < 200:
        raise ValueError("max_chars must be at least 200")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than max_chars")
    if not pages:
        return []

    text, offsets = _build_offset_table(pages)
    if not text.strip():
        return []

    chunks: list[DocumentChunk] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            end = _rewind_to_boundary(text, start, end)
        body = text[start:end].strip()
        if body:
            page_start, page_end = _page_range_for(start, end, offsets)
            chunk_index = len(chunks)
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{ref.document_id}::{chunk_index:05d}",
                    document_id=ref.document_id,
                    source_file=ref.source_file,
                    chunk_index=chunk_index,
                    page_start=page_start,
                    page_end=page_end,
                    text=body,
                    char_start=start,
                    char_end=end,
                    section_hint=_last_heading_before(text, start),
                )
            )
        if end >= length:
            break
        start = max(end - overlap_chars, end - 1)
    return chunks
